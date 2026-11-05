#!/usr/bin/env python3
"""Compare active-wait ShyLU using existing completed mesh reference controls."""
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


def compare(reference, data):
    grid = np.linspace(0, 8e-9, 8001)
    differences = [float(max(abs(np.interp(grid, reference[:, 0], reference[:, i]) -
        np.interp(grid, data[:, 0], data[:, i])))) for i in range(1, 5)]
    scale = max(float(max(abs(reference[:, 4]))), float(max(abs(data[:, 4]))), 1e-12)
    first, second = crossing(reference), crossing(data)
    assert len(first) == len(second)
    edge_error = max(abs(a - b) for a, b in zip(first, second))
    assert max(differences[:2]) < 1e-5 and differences[2] < 2e-3
    assert differences[3] < 1e-3 * scale + 1e-10 and edge_error < 1e-13
    return dict(voltage_differences_V=differences[:3], supply_current_difference_A=differences[3],
                rising_crossing_difference_s=edge_error, control_equivalence_passed=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    base = Path(__file__).resolve().parents[2] / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    prior = base / 'stock_threaded_mesh_controls_001'
    old_status = json.loads((prior / 'status.json').read_text())
    assert old_status['state'] == 'timeout_inconclusive' and not process(old_status['runner_pid'])['live']
    receipts = json.loads((prior / 'native_receipts.json').read_text())
    assert len(receipts) == 2 and all(row['native_exit'] == 0 for row in receipts)
    reference_path = prior / 'KLU_1/control.cir.prn'
    reference = read_wave(reference_path)
    one_path = prior / 'SHYLU_BASKER_1/control.cir.prn'
    one = read_wave(one_path)
    one_case = dict(receipts[1], **compare(reference, one))
    assert one_case['observed_peak_process_threads'] == 1
    built_path = base / 'stock_threaded_Xyce_002/assessment.json'
    built = json.loads(built_path.read_text()); binary = Path(built['binary'])
    assert built['stock_threaded_build_completed'] and digest(binary) == built['binary_sha256']
    args.output.mkdir(exist_ok=False)
    save(args.output / 'owner.json', dict(runner_pid=os.getpid(), deadline_uptime=deadline,
        original_owner=str(owner), budget_restarted=False, changed_OpenMP_wait_policy='ACTIVE'))
    def status(state, **extra):
        save(args.output / 'status.json', dict(state=state, runner_pid=os.getpid(),
            deadline_uptime=deadline, release_qualified=False, adopted=False, **extra))
    deck = args.output / 'control.cir'
    source = prior / 'SHYLU_BASKER_8/control.cir'
    deck.write_bytes(source.read_bytes())
    paths = [Path(__file__), owner, built_path, binary, source, deck, reference_path, one_path,
        prior / 'status.json', prior / 'native_receipts.json', prior / 'input_manifest.json',
        prior / 'SHYLU_BASKER_8/native.log',
        Path(__file__).with_name('check_stock_threaded_solver_controls_v2.py')]
    pins = {str(path.resolve()): digest(path) for path in paths}
    save(args.output / 'input_manifest.json', dict(input_sha256=pins, same_control_deck=True,
        OpenMP_wait_policy_changed_from='PASSIVE', OpenMP_wait_policy='ACTIVE',
        local_control_limit_s=300, prior_local_limit_s=120, deadline_uptime=deadline,
        budget_restarted=False, prior_timeout_is_inconclusive=True))
    status('waiting_native_admission')
    while True:
        remaining = deadline - time.clock_gettime(time.CLOCK_BOOTTIME)
        if remaining <= 0: status('timeout_inconclusive'); return
        with (base.parent / 'guarded_native_admission.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if len(live_engines()) < 4:
                with (args.output / 'native.log').open('x') as log:
                    start = time.monotonic()
                    child = subprocess.Popen([str(binary), '-quiet', '-o', str(deck.resolve()), str(deck.resolve())],
                        stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                        env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='8',
                            KOKKOS_NUM_THREADS='8', OMP_DYNAMIC='FALSE', OMP_WAIT_POLICY='ACTIVE',
                            OMP_PROC_BIND='FALSE'))
                status('native_active_wait_control_running', native_pid=child.pid); break
        time.sleep(1)
    end = time.monotonic() + min(300, remaining); peak = 0
    while child.poll() is None:
        try: peak = max(peak, len(list((Path('/proc') / str(child.pid) / 'task').iterdir())))
        except FileNotFoundError: pass
        if time.monotonic() >= end:
            os.killpg(child.pid, signal.SIGTERM)
            try: child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL); child.wait()
            status('timeout_inconclusive'); return
        time.sleep(.01)
    case = dict(solver='SHYLU_BASKER', requested_OpenMP_threads=8, native_exit=child.returncode,
        observed_peak_process_threads=peak, elapsed_s=time.monotonic() - start, OpenMP_wait_policy='ACTIVE')
    save(args.output / 'native_receipt.json', case)
    if child.returncode != 0: status('native_control_nonpass', **case); return
    data = read_wave(Path(str(deck) + '.prn'))
    case.update(compare(reference, data)); assert 8 <= peak <= 10
    assert all(digest(Path(name)) == value for name, value in pins.items())
    save(args.output / 'assessment.json', dict(connected_mesh_threaded_controls_passed=True,
        original_tiny_parallel_control_failed=True, tiny_failure_cause_proven=False,
        passive_wait_mesh_control_timed_out=True, cases=[receipts[0], one_case, case],
        OpenMP_wait_policy='ACTIVE', reused_completed_one_thread_and_KLU_controls=True,
        general_simulator_equivalence_qualified=False, full_DCO_performance_improvement_demonstrated=False,
        release_qualified=False, adopted=False, deadline_uptime=deadline, input_sha256=pins,
        artifacts={str(path.resolve()): digest(path) for path in
                   [args.output / 'native.log', Path(str(deck) + '.prn')]}))
    status('completed_active_wait_control')


if __name__ == '__main__':
    main()
