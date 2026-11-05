#!/usr/bin/env python3
"""Guarded handoff to a corrected-C serial diagnostic after native controls.

Never overlap two full DCO instances. Do not interrupt a prior run that has
advanced in simulation time. Inherit the campaign's original absolute deadline.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process
from run_DCO_domain_point_v3 import live_engines


def rows(path):
    data = []
    if path.exists():
        for line in path.read_text().splitlines()[1:]:
            fields = line.split()
            if len(fields) == 4 and fields[0].isdigit():
                assert int(fields[0]) == len(data)
                data.append(tuple(float(value) for value in fields[1:]))
    return data


def stop(child):
    os.killpg(child.pid, signal.SIGTERM)
    try: child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL); child.wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--controls-runner-pid', required=True, type=int)
    parser.add_argument('--replace-native-pid', required=True, type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    control_identity = process(args.controls_runner_pid)
    assert control_identity['live'] and control_identity['argv'][1] == 'verification/timing400/check_stock_serial_factor_reuse.py'
    controls = base / 'stock_serial_factor_reuse_controls_001'
    prepared = base / 'DCO_domain_nom_tt27_c0_f247_80ns_corrected_ground_prepared_001'
    prior = base / 'DCO_domain_nom_tt27_c0_f247_80ns_canonical_ground_001'
    build = base / 'stock_serial_Xyce_001'
    args.output.mkdir(exist_ok=False)
    pins = {str(path.resolve()): digest(path) for path in [Path(__file__).resolve(), owner,
        controls / 'owner.json', prepared / 'input_manifest.json', prepared / 'assessment.json']}
    save(args.output / 'owner.json', dict(runner_pid=os.getpid(), original_owner=str(owner.resolve()),
        started_utc=datetime.now(timezone.utc).isoformat(), deadline_uptime=deadline,
        budget_restarted=False, control_runner_identity=control_identity))
    save(args.output / 'preparation_manifest.json', dict(input_sha256=pins,
        require_control_pass=True, stop_only_if_prior_has_no_positive_time_sample=True,
        maximum_full_DCO_instances=1, original_deadline_uptime=deadline))
    def status(state, **extra):
        save(args.output / 'status.json', dict(state=state, runner_pid=os.getpid(),
            deadline_uptime=deadline, release_qualified=False, adopted=False, **extra))
    control_proof = controls / 'assessment.json'
    status('waiting_for_identified_serial_controls', control_runner=control_identity)
    while not control_proof.exists():
        if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            status('timeout_inconclusive'); return
        identity = process(args.controls_runner_pid)
        if not identity['live'] or identity['argv'] != control_identity['argv']:
            status('controls_unavailable', observed_runner=identity); return
        observed = json.loads((controls / 'status.json').read_text())
        if observed['state'] in ['build_unavailable', 'timeout_inconclusive']:
            status('controls_unavailable', control_status=observed); return
        time.sleep(5)
    control = json.loads(control_proof.read_text())
    assert control['stock_serial_signed_C_finite_R_BSIM_controls_passed']
    built = json.loads((build / 'assessment.json').read_text())
    assert built['stock_serial_build_completed'] and not built['source_code_modified']
    binary = Path(built['binary'])
    assert digest(binary) == built['binary_sha256']
    preparation = json.loads((prepared / 'assessment.json').read_text())
    assert preparation['corrected_C_diagnostic_preparation_passed']
    assert preparation['all_noncapacitive_macro_statements_identical']
    for source in [control, preparation]:
        pins.update(source['input_sha256'])
        pins.update(source.get('artifacts', {}))
    for name, value in pins.items():
        assert digest(Path(name)) == value, name
    original = (prepared / 'point.cir').read_text()
    option = '.options LINSOL TYPE=KLU TR_PARTITION=0 TR_AMD=0'
    assert original.count(option) == 1
    assert '.tran 20p 80n 0 10p UIC' in original
    deck = args.output / 'point.cir'
    deck.write_text(original.replace(option, option + ' KLU_REPIVOT=0'))
    for path in [deck, control_proof, build / 'assessment.json', binary]:
        pins[str(path.resolve())] = digest(path)
    params = json.loads((prepared / 'input_manifest.json').read_text())['parameters']
    save(args.output / 'input_manifest.json', dict(input_sha256=pins, parameters=params,
        physical_C_model_convention_changed_from_prior_run=True,
        unmodified_stock_serial_simulator=True, KLU_REPIVOT=0,
        physical_R_and_device_cards_unchanged=True, prior_ground_mapping_and_initial_bias_unchanged=True,
        original_deadline_uptime=deadline, budget_restarted=False, identical_native_retry=False,
        performance_change_not_isolated_from_C_model_change=True))
    before = process(args.replace_native_pid)
    prior_deck = prior / 'point.cir'
    expected = ['/opt/xyce/bin/Xyce', '-quiet', '-o', str(prior_deck.resolve()), str(prior_deck.resolve())]
    if not before['live'] or before['argv'] != expected:
        status('replacement_deferred_prior_process_changed', prior=before); return
    prior_rows = rows(Path(str(prior_deck) + '.prn'))
    if any(row[0] > 0 for row in prior_rows):
        status('replacement_deferred_prior_has_transient_progress', prior_max_time_s=prior_rows[-1][0]); return
    assert os.getpgid(args.replace_native_pid) == args.replace_native_pid
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    receipt = prior / 'stopped_for_controlled_stock_serial_corrected_C_comparison.json'
    assert not receipt.exists()
    save(receipt, dict(pid=args.replace_native_pid, argv=before['argv'],
        proc_stat=(Path('/proc') / str(args.replace_native_pid) / 'stat').read_text(),
        reason='No positive-time sample; native serial controls passed; corrected-C diagnostic and unchanged full finite-R/device model prepared and pinned',
        new_manifest=str((args.output / 'input_manifest.json').resolve()),
        original_deadline_uptime=deadline, budget_restarted=False, identical_native_retry=False,
        performance_comparison_changes_C_convention_and_stock_serial_solver=True,
        physical_failure_inferred=False))
    os.killpg(args.replace_native_pid, signal.SIGTERM)
    end = time.monotonic() + 10
    while process(args.replace_native_pid)['live']:
        assert time.monotonic() < end, 'Prior full native instance did not stop'
        time.sleep(.1)
    while True:
        remaining = deadline - time.clock_gettime(time.CLOCK_BOOTTIME)
        if remaining <= 0:
            status('timeout_inconclusive'); return
        with (base.parent / 'guarded_native_admission.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            active = live_engines()
            if len(active) < 4:
                assert not process(args.replace_native_pid)['live']
                with (args.output / 'native.log').open('x') as log:
                    child = subprocess.Popen([str(binary), '-quiet', '-o', str(deck.resolve()), str(deck.resolve())],
                        cwd='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice',
                        stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                        env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'))
                status('native_stock_serial_corrected_C_point_running', native_pid=child.pid)
                break
        time.sleep(1)
    try: code = child.wait(timeout=remaining)
    except subprocess.TimeoutExpired:
        stop(child); status('timeout_inconclusive'); return
    wave = Path(str(deck) + '.prn')
    metrics = None
    if code == 0 and wave.exists():
        assert 'End of Xyce(TM) Simulation' in wave.read_text()
        data = rows(wave)
        assert data and all(math.isfinite(v) for row in data for v in row)
        assert all(a[0] < b[0] for a, b in zip(data, data[1:]))
        assert data[-1][0] >= params['duration_ns'] * 1e-9 * (1 - 1e-7)
        edges = []
        for a, b in zip(data, data[1:]):
            if a[1] < .9 <= b[1]:
                t = a[0] + (.9 - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                if t >= params['measure_start_ns'] * 1e-9: edges.append(t)
        if len(edges) >= 4:
            metrics = dict(mhz=(len(edges) - 1) / (edges[-1] - edges[0]) * 1e-6,
                periods=len(edges) - 1, output_min_V=min(row[1] for row in data),
                output_max_V=max(row[1] for row in data))
    assert all(digest(Path(name)) == value for name, value in pins.items())
    save(args.output / 'assessment.json', dict(native_exit=code, metrics=metrics,
        completed_diagnostic_oscillation=metrics is not None,
        finite_R_and_nonlinear_device_model_preserved=True,
        source_model_and_frequency_convergence_qualified=False,
        stock_serial_and_C_convention_both_changed=True,
        runtime_model_eligible=False, release_qualified=False, adopted=False,
        deadline_uptime=deadline, input_sha256=pins,
        artifacts={str(p.resolve()): digest(p) for p in [args.output / 'native.log', wave] if p.exists()}))
    status('completed_diagnostic' if metrics else 'native_or_oscillation_nonpass', native_exit=code, metrics=metrics)


if __name__ == '__main__':
    main()
