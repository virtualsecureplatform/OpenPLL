#!/usr/bin/env python3
"""Test connected RC/BSIM controls after a failed tiny parallel control.

This is a changed control circuit, not a retry or solver equivalence claim.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import numpy as np
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process
from run_DCO_domain_point_v3 import live_engines
from check_stock_threaded_solver_controls_v2 import read_wave, crossing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    base = Path(__file__).resolve().parents[2] / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    prior = base / 'stock_threaded_solver_controls_002'
    prior_status = json.loads((prior / 'status.json').read_text())
    assert not process(prior_status['runner_pid'])['live']
    assert not (prior / 'assessment.json').exists()
    build_proof = base / 'stock_threaded_Xyce_002/assessment.json'
    built = json.loads(build_proof.read_text())
    binary = Path(built['binary'])
    assert built['stock_threaded_build_completed'] and built['OpenMP_and_METIS_enabled']
    assert digest(binary) == built['binary_sha256']
    args.output.mkdir(exist_ok=False)
    save(args.output / 'owner.json', dict(runner_pid=os.getpid(), deadline_uptime=deadline,
        original_owner=str(owner), budget_restarted=False, changed_control_circuit=True))
    def status(state, **extra):
        save(args.output / 'status.json', dict(state=state, runner_pid=os.getpid(),
            deadline_uptime=deadline, release_qualified=False, adopted=False, **extra))
    status('preparing_connected_mesh_control')
    source = prior / 'threads_1/control.cir'
    original = source.read_text()
    additions = []
    # A connected 8x8 passive resistor mesh gives the partitioner a larger
    # component. Positive shunt C preserves passivity; original signed C stays.
    for index in range(64):
        additions.append(f'Cmesh{index} mesh{index} 0 10f')
        if index % 8 != 7:
            additions.append(f'RmeshH{index} mesh{index} mesh{index + 1} 1k')
        if index < 56:
            additions.append(f'RmeshV{index} mesh{index} mesh{index + 8} 1k')
    additions.extend(['RmeshA a mesh0 1meg', 'RmeshOut output mesh63 1meg'])
    assert original.count('.end') == 1
    mesh = original.replace('.end', '\n'.join(additions) + '\n.end')
    options = '.options LINSOL TYPE=SHYLU_BASKER TR_PARTITION=0 TR_AMD=0'
    assert mesh.count(options) == 1
    pins = {str(path.resolve()): digest(path) for path in [Path(__file__), owner,
        build_proof, binary, source, prior / 'threads_8/native.log',
        Path(__file__).with_name('check_stock_threaded_solver_controls_v2.py')]}
    save(args.output / 'input_manifest.json', dict(input_sha256=pins,
        added_passive_mesh_nodes=64, prior_tiny_parallel_control_failed=True,
        tiny_failure_cause_proven=False, deadline_uptime=deadline, budget_restarted=False))
    results, waves, artifacts = [], [], []
    for solver, threads in [('KLU', 1), ('SHYLU_BASKER', 1), ('SHYLU_BASKER', 8)]:
        folder = args.output / f'{solver}_{threads}'; folder.mkdir()
        deck = folder / 'control.cir'
        deck.write_text(mesh.replace(options, f'.options LINSOL TYPE={solver} TR_PARTITION=0 TR_AMD=0'))
        pins[str(deck.resolve())] = digest(deck)
        engine = Path('/opt/xyce/bin/Xyce') if solver == 'KLU' else binary
        pins[str(engine)] = digest(engine)
        while True:
            remaining = deadline - time.clock_gettime(time.CLOCK_BOOTTIME)
            if remaining <= 0:
                status('timeout_inconclusive'); return
            with (base.parent / 'guarded_native_admission.lock').open('a+') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                if len(live_engines()) < 4:
                    with (folder / 'native.log').open('x') as log:
                        start = time.monotonic()
                        child = subprocess.Popen([str(engine), '-quiet', '-o', str(deck.resolve()), str(deck.resolve())],
                            stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                            env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS=str(threads),
                                KOKKOS_NUM_THREADS=str(threads), OMP_DYNAMIC='FALSE',
                                OMP_WAIT_POLICY='PASSIVE', OMP_PROC_BIND='FALSE'))
                    status('native_control_running', solver=solver, threads=threads, native_pid=child.pid)
                    break
            time.sleep(1)
        end = time.monotonic() + min(120, remaining)
        peak = 0
        while child.poll() is None:
            try: peak = max(peak, len(list((Path('/proc') / str(child.pid) / 'task').iterdir())))
            except FileNotFoundError: pass
            if time.monotonic() >= end:
                os.killpg(child.pid, signal.SIGTERM)
                try: child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL); child.wait()
                status('timeout_inconclusive', solver=solver, threads=threads); return
            time.sleep(.01)
        results.append(dict(solver=solver, requested_OpenMP_threads=threads,
            native_exit=child.returncode, observed_peak_process_threads=peak,
            elapsed_s=time.monotonic() - start))
        save(args.output / 'native_receipts.json', results)
        if child.returncode != 0:
            status('native_control_nonpass', **results[-1]); return
        data = read_wave(Path(str(deck) + '.prn')); waves.append(data)
        artifacts.extend([folder / 'native.log', Path(str(deck) + '.prn')])
        if solver != 'KLU':
            grid = np.linspace(0, 8e-9, 8001); reference = waves[0]
            differences = [float(max(abs(np.interp(grid, reference[:, 0], reference[:, i]) -
                np.interp(grid, data[:, 0], data[:, i])))) for i in range(1, 5)]
            scale = max(float(max(abs(reference[:, 4]))), float(max(abs(data[:, 4]))), 1e-12)
            first, second = crossing(reference), crossing(data)
            assert len(first) == len(second)
            edge_error = max(abs(a - b) for a, b in zip(first, second))
            assert max(differences[:2]) < 1e-5 and differences[2] < 2e-3
            assert differences[3] < 1e-3 * scale + 1e-10 and edge_error < 1e-13
            assert threads <= peak <= threads + 2
            results[-1].update(voltage_differences_V=differences[:3],
                supply_current_difference_A=differences[3], rising_crossing_difference_s=edge_error,
                control_equivalence_passed=True)
    assert all(digest(Path(name)) == value for name, value in pins.items())
    save(args.output / 'assessment.json', dict(connected_mesh_threaded_controls_passed=True,
        cases=results, original_tiny_parallel_control_failed=True, tiny_failure_cause_proven=False,
        general_simulator_equivalence_qualified=False, full_DCO_performance_improvement_demonstrated=False,
        release_qualified=False, adopted=False, deadline_uptime=deadline, input_sha256=pins,
        artifacts={str(path.resolve()): digest(path) for path in artifacts}))
    status('completed_connected_mesh_controls')


if __name__ == '__main__':
    main()
