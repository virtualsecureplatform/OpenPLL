#!/usr/bin/env python3
"""Compare stock serial KLU modes against a retained golden native control.

Wait only on the identified existing build, under the original campaign
deadline. No full DCO replacement or engine/model adoption is performed.
"""
import argparse
from datetime import datetime, timezone
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


def read_wave(path):
    lines = path.read_text().splitlines()
    assert lines[0].split() == ['Index', 'TIME', 'V(A)', 'V(B)', 'V(OUTPUT)', 'I(VDD)']
    assert any('End of Xyce(TM) Simulation' in line for line in lines)
    rows = [line.split() for line in lines[1:] if len(line.split()) == 6]
    assert all(int(row[0]) == i for i, row in enumerate(rows))
    data = np.asarray([[float(v) for v in row[1:]] for row in rows])
    assert np.isfinite(data).all() and data[0, 0] == 0
    assert np.all(np.diff(data[:, 0]) > 0) and data[-1, 0] >= 8e-9 * (1 - 1e-8)
    return data


def crossing(data):
    edges = []
    for left, right in zip(data, data[1:]):
        if left[3] < .9 <= right[3]:
            edges.append(float(left[0] + (.9 - left[3]) * (right[0] - left[0]) / (right[3] - left[3])))
    assert edges
    return edges


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', required=True, type=Path)
    parser.add_argument('--build-runner-pid', required=True, type=int)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    builder = process(args.build_runner_pid)
    assert builder['live'] and builder['argv'][1] == 'verification/timing400/build_stock_serial_Xyce.py'
    assert builder['argv'][-1] == str(args.build)
    args.output.mkdir(exist_ok=False)
    save(args.output / 'owner.json', dict(runner_pid=os.getpid(), original_owner=str(owner.resolve()),
        started_utc=datetime.now(timezone.utc).isoformat(), deadline_uptime=deadline,
        budget_restarted=False, build_runner_identity=builder))
    def status(state, **extra):
        save(args.output / 'status.json', dict(state=state, runner_pid=os.getpid(),
            deadline_uptime=deadline, release_qualified=False, adopted=False, **extra))
    build_proof = args.build / 'assessment.json'
    status('waiting_for_identified_stock_serial_build', build_runner=builder)
    while not build_proof.exists():
        if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            status('timeout_inconclusive'); return
        current = process(args.build_runner_pid)
        if not current['live'] or current['argv'] != builder['argv']:
            status('build_unavailable', observed_builder=current); return
        state_path = args.build / 'status.json'
        if state_path.exists() and json.loads(state_path.read_text())['state'] in ['build_nonpass', 'timeout_inconclusive']:
            status('build_unavailable', build_status=json.loads(state_path.read_text())); return
        time.sleep(5)
    built = json.loads(build_proof.read_text())
    assert built['stock_serial_build_completed'] and not built['source_code_modified']
    assert not built['installed_golden_binary_modified']
    binary = Path(built['binary'])
    assert digest(binary) == built['binary_sha256']
    cache = (args.build / 'xyce-build/CMakeCache.txt').read_text()
    assert 'Xyce_PARALLEL_MPI:BOOL=OFF' in cache or 'Xyce_PARALLEL_MPI:BOOL=FALSE' in cache
    controls = base / 'zero_voltage_canonicalization_controls_001'
    reference_path = controls / 'assessment.json'
    reference = json.loads(reference_path.read_text())
    assert reference['native_voltage_constraint_canonicalization_controls_passed']
    pins = {**built['input_sha256'], **reference['input_sha256'], **reference['artifacts']}
    source = controls / 'canonical_ground/control.cir'
    for path in [Path(__file__).resolve(), owner, build_proof, binary, reference_path, source]:
        pins[str(path.resolve())] = digest(path)
    for name, value in pins.items():
        assert digest(Path(name)) == value, name
    reference_wave = read_wave(Path(str(source) + '.prn'))
    grid = np.linspace(0, 8e-9, 8001)
    reference_edges = crossing(reference_wave)
    pdk = Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice')
    original = source.read_text()
    option = '.options LINSOL TYPE=KLU TR_PARTITION=0 TR_AMD=0'
    assert original.count(option) == 1
    cases, artifacts = [], []
    for repivot in [1, 0]:
        folder = args.output / ('repivot_' + str(repivot))
        folder.mkdir()
        deck = folder / 'control.cir'
        deck.write_text(original.replace(option, option + ' KLU_REPIVOT=' + str(repivot)))
        pins[str(deck.resolve())] = digest(deck)
        while True:
            remaining = deadline - time.clock_gettime(time.CLOCK_BOOTTIME)
            if remaining <= 0:
                status('timeout_inconclusive'); return
            with (base.parent / 'guarded_native_admission.lock').open('a+') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                if len(live_engines()) < 4:
                    with (folder / 'native.log').open('x') as log:
                        start = time.monotonic()
                        child = subprocess.Popen([str(binary), '-quiet', '-o', str(deck.resolve()), str(deck.resolve())],
                            cwd=pdk, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                            env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'))
                    status('native_serial_control_running', repivot=repivot, native_pid=child.pid)
                    break
            time.sleep(1)
        try:
            code = child.wait(timeout=min(120, remaining))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGTERM)
            try: child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL); child.wait()
            status('timeout_inconclusive', repivot=repivot); return
        elapsed = time.monotonic() - start
        assert code == 0, (folder / 'native.log').read_text()[-2000:]
        data = read_wave(Path(str(deck) + '.prn'))
        errors = [float(max(abs(np.interp(grid, reference_wave[:, 0], reference_wave[:, i]) -
                               np.interp(grid, data[:, 0], data[:, i])))) for i in range(1, 5)]
        assert max(errors[:2]) < 1e-5 and errors[2] < 2e-3
        scale = max(float(max(abs(reference_wave[:, 4]))), float(max(abs(data[:, 4]))), 1e-12)
        assert errors[3] < 1e-3 * scale + 1e-10
        edges = crossing(data)
        assert len(edges) == len(reference_edges)
        edge_error = max(abs(a - b) for a, b in zip(edges, reference_edges))
        assert edge_error < 1e-13
        cases.append(dict(KLU_REPIVOT=repivot, native_exit=code, elapsed_s=elapsed,
            voltage_differences_V=errors[:3], supply_current_difference_A=errors[3],
            rising_crossing_difference_s=edge_error, control_equivalence_passed=True))
        artifacts.extend([folder / 'native.log', Path(str(deck) + '.prn')])
    assert all(digest(Path(name)) == value for name, value in pins.items())
    save(args.output / 'assessment.json', dict(stock_serial_signed_C_finite_R_BSIM_controls_passed=True,
        serial_KLU_repivot_option_modes_checked=[1, 0], cases=cases,
        full_DCO_performance_improvement_demonstrated=False,
        general_simulator_equivalence_qualified=False, DCO_timing_or_frequency_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False,
        deadline_uptime=deadline, input_sha256=pins,
        artifacts={str(path.resolve()): digest(path) for path in artifacts}))
    status('completed_control_equivalence_passed_full_DCO_performance_pending')


if __name__ == '__main__':
    main()
