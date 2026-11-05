#!/usr/bin/env python3
"""Guarded handoff after the changed connected-mesh threaded controls.

Never overlap two full DCO instances. Preserve a prior run with viable observed
throughput. Inherit the campaign's original absolute deadline.
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
        text = path.read_text()
        lines = text.splitlines()
        if text and not text.endswith('\n'):
            lines.pop()  # A live writer may be partway through its last row.
        for line in lines[1:]:
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
    controls = base / 'stock_threaded_active_wait_controls_001'
    control_identity = process(args.controls_runner_pid)
    assert json.loads((controls / 'owner.json').read_text())['runner_pid'] == args.controls_runner_pid
    if control_identity['live']:
        assert control_identity['argv'][1] == 'verification/timing400/check_stock_threaded_active_wait_control.py'
    else:
        assert (controls / 'assessment.json').exists()
    prepared = base / 'DCO_domain_nom_tt27_c0_f247_80ns_corrected_ground_prepared_001'
    prior = base / 'DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_002'
    build = base / 'stock_threaded_Xyce_002'
    args.output.mkdir(exist_ok=False)
    pins = {str(path.resolve()): digest(path) for path in [Path(__file__).resolve(), owner,
        controls / 'owner.json', prepared / 'input_manifest.json', prepared / 'assessment.json']}
    save(args.output / 'owner.json', dict(runner_pid=os.getpid(), original_owner=str(owner.resolve()),
        started_utc=datetime.now(timezone.utc).isoformat(), deadline_uptime=deadline,
        budget_restarted=False, control_runner_identity=control_identity))
    save(args.output / 'preparation_manifest.json', dict(input_sha256=pins,
        require_control_pass=True, require_bounded_prior_throughput_observation=True,
        minimum_throughput_observation_s=120, preserve_if_at_measurement_window=True,
        preserve_if_projected_finish_within_twice_remaining_budget=True,
        maximum_full_DCO_instances=1, original_deadline_uptime=deadline))
    def status(state, **extra):
        save(args.output / 'status.json', dict(state=state, runner_pid=os.getpid(),
            deadline_uptime=deadline, release_qualified=False, adopted=False, **extra))
    control_proof = controls / 'assessment.json'
    observations = []
    def observe(force=False):
        now = time.clock_gettime(time.CLOCK_BOOTTIME)
        if observations and not force and now - observations[-1]['uptime'] < 30:
            return
        observed_rows = rows(Path(str(prior / 'point.cir') + '.prn'))
        observations.append(dict(uptime=now, observed_utc=datetime.now(timezone.utc).isoformat(),
            samples=len(observed_rows), max_simulation_time_s=max((row[0] for row in observed_rows), default=0.)))
        save(args.output / 'prior_throughput_observations.json', observations)
    observe()
    status('waiting_for_identified_threaded_controls', control_runner=control_identity)
    while not control_proof.exists():
        observe()
        if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            status('timeout_inconclusive'); return
        identity = process(args.controls_runner_pid)
        if not identity['live'] or identity['argv'] != control_identity['argv']:
            status('controls_unavailable', observed_runner=identity); return
        observed = json.loads((controls / 'status.json').read_text())
        if observed['state'] in ['build_unavailable', 'timeout_inconclusive', 'native_control_nonpass']:
            status('controls_unavailable', control_status=observed); return
        time.sleep(5)
    control = json.loads(control_proof.read_text())
    assert control['connected_mesh_threaded_controls_passed']
    assert control['OpenMP_wait_policy'] == 'ACTIVE'
    assert control['original_tiny_parallel_control_failed'] and not control['tiny_failure_cause_proven']
    assert all(case['native_exit'] == 0 for case in control['cases'])
    threaded_cases = [case for case in control['cases'] if case['solver'] == 'SHYLU_BASKER']
    assert [case['requested_OpenMP_threads'] for case in threaded_cases] == [1, 8]
    for case in threaded_cases:
        assert case['control_equivalence_passed']
        assert case['requested_OpenMP_threads'] <= case['observed_peak_process_threads'] <= case['requested_OpenMP_threads'] + 2
    built = json.loads((build / 'assessment.json').read_text())
    assert built['stock_threaded_build_completed'] and not built['source_code_modified']
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
    threaded_option = '.options LINSOL TYPE=SHYLU_BASKER TR_PARTITION=0 TR_AMD=0'
    deck.write_text(original.replace(option, threaded_option))
    # The prior serial case uses exactly this prepared circuit plus its KLU
    # option. Check byte identity after changing only that one solver line.
    assert (prior / 'point.cir').read_text().replace(option + ' KLU_REPIVOT=0', threaded_option) == deck.read_text()
    for path in [deck, control_proof, build / 'assessment.json', binary]:
        pins[str(path.resolve())] = digest(path)
    params = json.loads((prepared / 'input_manifest.json').read_text())['parameters']
    save(args.output / 'input_manifest.json', dict(input_sha256=pins, parameters=params,
        physical_C_model_convention_changed_from_prior_run=False,
        unmodified_stock_threaded_simulator=True, solver='SHYLU_BASKER', requested_OpenMP_threads=8,
        physical_R_and_device_cards_unchanged=True, prior_ground_mapping_and_initial_bias_unchanged=True,
        original_tiny_parallel_control_failed=True, failure_cause_proven=False,
        connected_mesh_control_equivalence_required=True, OpenMP_wait_policy='ACTIVE',
        original_deadline_uptime=deadline, budget_restarted=False, identical_native_retry=False,
        performance_change_not_isolated_from_C_model_change=False))
    before = process(args.replace_native_pid)
    prior_deck = prior / 'point.cir'
    expected = [str(base / 'stock_serial_Xyce_001/xyce-install/bin/Xyce'), '-quiet', '-o', str(prior_deck.resolve()), str(prior_deck.resolve())]
    if not before['live'] or before['argv'] != expected:
        status('replacement_deferred_prior_process_changed', prior=before); return
    prior_rows = rows(Path(str(prior_deck) + '.prn'))
    if any(row[0] > 0 for row in prior_rows):
        # Do not extrapolate only from the expensive initial factorization.
        # Observe actual post-initialization progress for at least two minutes.
        while time.clock_gettime(time.CLOCK_BOOTTIME) - observations[0]['uptime'] < 120:
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                status('timeout_inconclusive'); return
            current = process(args.replace_native_pid)
            if not current['live'] or current['argv'] != expected:
                status('replacement_deferred_prior_process_changed', prior=current); return
            status('observing_prior_throughput_before_replacement')
            time.sleep(5)
            observe()
        observe(force=True)
        last_time = observations[-1]['max_simulation_time_s']
        recent = [row for row in observations if row['uptime'] >= observations[-1]['uptime'] - 600]
        rates = [(b['max_simulation_time_s'] - a['max_simulation_time_s']) / (b['uptime'] - a['uptime'])
                 for a, b in zip(recent, recent[1:]) if b['uptime'] - a['uptime'] >= 20]
        assert rates and all(rate >= 0 for rate in rates)
        fastest = max(rates)
        remaining_budget = deadline - time.clock_gettime(time.CLOCK_BOOTTIME)
        projected = (params['duration_ns'] * 1e-9 - last_time) / fastest if fastest > 0 else None
        throughput = dict(observation_span_s=observations[-1]['uptime'] - observations[0]['uptime'],
            prior_last_time_s=last_time, fastest_observed_rate_simulation_s_per_wall_s=fastest,
            projected_remaining_s=projected, remaining_budget_s=remaining_budget,
            prediction_is_diagnostic_not_a_runtime_bound=True)
        save(args.output / 'prior_throughput_decision.json', throughput)
        if last_time >= params['measure_start_ns'] * 1e-9 or (
                projected is not None and projected <= 2 * remaining_budget):
            status('replacement_deferred_prior_has_viable_progress', **throughput); return
    assert os.getpgid(args.replace_native_pid) == args.replace_native_pid
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    receipt = prior / 'stopped_for_controlled_stock_threaded_solver_comparison.json'
    assert not receipt.exists()
    save(receipt, dict(pid=args.replace_native_pid, argv=before['argv'],
        proc_stat=(Path('/proc') / str(args.replace_native_pid) / 'stat').read_text(),
        reason='Native threaded controls passed; prior has no positive-time sample or observed inadequate throughput; byte-identical physical circuit and numerical settings prepared with a different stock solver',
        new_manifest=str((args.output / 'input_manifest.json').resolve()),
        original_deadline_uptime=deadline, budget_restarted=False, identical_native_retry=False,
        physical_C_convention_and_all_circuit_cards_unchanged=True,
        throughput_observation=str((args.output / 'prior_throughput_observations.json').resolve()),
        partial_waveform_preserved=True,
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
                        env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='8',
                            KOKKOS_NUM_THREADS='8', OMP_DYNAMIC='FALSE', OMP_WAIT_POLICY='ACTIVE', OMP_PROC_BIND='FALSE'))
                status('native_stock_threaded_point_running', native_pid=child.pid)
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
        physical_C_convention_unchanged=True, solver_and_requested_OpenMP_threads_changed=True,
        runtime_model_eligible=False, release_qualified=False, adopted=False,
        deadline_uptime=deadline, input_sha256=pins,
        artifacts={str(p.resolve()): digest(p) for p in [args.output / 'native.log', wave] if p.exists()}))
    status('completed_diagnostic' if metrics else 'native_or_oscillation_nonpass', native_exit=code, metrics=metrics)


if __name__ == '__main__':
    main()
