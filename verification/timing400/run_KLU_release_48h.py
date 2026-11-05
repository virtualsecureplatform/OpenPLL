#!/usr/bin/env python3
"""Run the unchanged, previously controlled DCO baseline under a new 48h owner."""
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import time

from compile_local_C_operators_v2 import digest, save
from run_DCO_domain_point_v3 import live_engines, model_files
from run_DCO_stock_threaded_point_v2 import rows

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'build/timing400/release_001'
OUT = BASE / 'KLU_release_48h_001'
OWNER = json.loads((OUT / 'owner.json').read_text())
DEADLINE = OWNER['deadline_uptime']
NATIVE_DEADLINE = DEADLINE - 300  # Reserve assessment time inside the budget.
child = None
pins = {}
started = None
pattern = re.compile(r'OpenPLL_wire_PC call=(\d+) alpha=(\S+) iterations=(\d+) scaled_true_relative_residual=(\S+) seconds=(\S+) status=(\d+)')


def status(state, **extra):
    save(OUT / 'status.json', dict(state=state, runner_pid=os.getpid(),
         observed_utc=datetime.now(timezone.utc).isoformat(),
         deadline_utc=OWNER['deadline_utc'], deadline_uptime=DEADLINE,
         release_qualified=False, **extra))


def stop():
    if child is not None and child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (48 * 1024**3, 48 * 1024**3))
    seconds = max(1, int(NATIVE_DEADLINE - time.clock_gettime(time.CLOCK_BOOTTIME)))
    resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds + 1))


def main():
    global child, started, pins
    status('checking_frozen_inputs')
    prior = BASE / 'DCO_domain_nom_tt27_c0_f247_80ns_bounded_reuse_gear_001'
    build = BASE / 'wire_preconditioned_Xyce_bounded_reuse_001/recovered_build_assessment.json'
    built = json.loads(build.read_text())
    binary = Path(built['binary'])
    assert built['experimental_build_completed'] and digest(binary) == built['binary_sha256']
    controls = BASE / 'bounded_reuse_native_controls_audit_002/assessment.json'
    audit = json.loads(controls.read_text())
    assert audit['completed_native_control_audit_passed']
    assert audit['separate_timestep_and_tolerance_holdouts_verified']
    mapping = BASE / 'DCO_bounded_reuse_variable_map_001/assessment.json'
    mapped = json.loads(mapping.read_text())
    assert mapped['full_DCO_variable_map_verified']
    # The exact same binary and deck already passed the native map gate.
    assert digest(binary) == mapped['input_sha256'][str(binary)]
    deck = OUT / 'point.cir'
    assert not deck.exists(), 'Campaign must never silently restart'
    deck.write_bytes((prior / 'point.cir').read_bytes())
    assert digest(deck) == digest(BASE / 'DCO_bounded_reuse_variable_map_001/point.cir')
    assert '.tran 20p 80n 0 10p UIC' in deck.read_text()
    assert '.options TIMEINT RELTOL=1e-05 ABSTOL=1e-09 METHOD=GEAR' in deck.read_text()
    metadata = BASE / 'native_wire_preconditioner_metadata_001/wire_C.bin'
    assert digest(metadata) == 'f78520d1da4cea105a624e95810dc5d3487688cbbb0c959819fac36b6c1da9f0'
    # Validate all physical models against the prior immutable baseline.
    previous = json.loads((prior / 'assessment.json').read_text())['input_sha256']
    files = model_files(deck, NATIVE_DEADLINE)
    for path in files:
        if path != deck:
            assert digest(path) == previous[str(path)], str(path)
    for path in (binary, metadata):
        assert digest(path) == previous[str(path)], str(path)
    for path in files + [Path(__file__).resolve(), build, binary, controls, mapping,
                         metadata, OUT / 'owner.json', prior / 'assessment.json',
                         Path(__file__).with_name('run_DCO_stock_threaded_point_v2.py'),
                         Path(__file__).with_name('run_DCO_domain_point_v3.py'),
                         Path(__file__).with_name('compile_local_C_operators_v2.py'),
                         ROOT / 'verification/active_release.json',
                         ROOT / 'verification/release_requirements_400mhz.json',
                         ROOT / 'verification/release_plan_400mhz.json',
                         ROOT / 'sky130/release_400mhz_targets.json',
                         ROOT / 'build/apptainer/openpll-release-modern.sif']:
        pins[str(path)] = digest(path)
    save(OUT / 'input_manifest.json', dict(input_sha256=pins, duration_ns=80,
         measurement_start_ns=20, maximum_step_ps=10, nominal_supply_v=1.8,
         corner='tt', temperature_C=27, coarse_code=0, fine_code=247,
         solver='KLU bounded-reuse preconditioner with GMRES and full residual gate',
         scaled_true_relative_residual_limit=1e-12, physical_deck_byte_identical=True,
         existing_native_map_gate_reused=True, automatic_identical_retry=False))
    env = dict(os.environ, OPENPLL_WIRE_PC=str(metadata), OMP_NUM_THREADS='1',
               OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    env.pop('OPENPLL_PACKED_CONSTANT_CAPS', None)
    command = [str(binary), '-quiet', '-o', str(deck), str(deck)]
    with (BASE.parent / 'guarded_native_admission.lock').open('a+') as lock:
        while True:
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= NATIVE_DEADLINE:
                raise TimeoutError('Campaign deadline before admission')
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                time.sleep(1)
                continue
            active = live_engines()
            mem = {line.split(':')[0]: int(line.split()[1])*1024
                   for line in Path('/proc/meminfo').read_text().splitlines()}
            if not active and mem['MemAvailable'] >= 40 * 1024**3:
                started = time.monotonic()
                with (OUT / 'native.log').open('x') as log:
                    child = subprocess.Popen(command, cwd=OUT, env=env, stdout=log,
                        stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=limits)
                save(OUT / 'launch.json', dict(pid=child.pid, command=command,
                     started_utc=datetime.now(timezone.utc).isoformat(),
                     observed_native_before=active, exclusive_large_case=True,
                     deadline_utc=OWNER['deadline_utc'], address_space_limit_GiB=48))
                break
            fcntl.flock(lock, fcntl.LOCK_UN)
            status('queued_for_exclusive_large_case', observed_native_pids=active)
            time.sleep(5)
    wave = Path(str(deck) + '.prn')
    count = 0
    max_residual = 0.
    invalid = 0
    last_activity = time.monotonic()
    last_signature = None
    reason = None
    with (OUT / 'native.log').open() as log:
        while True:
            for line in log:
                match = pattern.fullmatch(line.strip())
                if match:
                    residual, code = float(match[4]), int(match[6])
                    count += 1
                    if not math.isfinite(residual) or residual > 1e-12 or code != 0:
                        invalid += 1
                    max_residual = max(max_residual, residual)
            data = rows(wave)
            signature = (count, len(data), (OUT / 'native.log').stat().st_size)
            if signature != last_signature:
                last_activity = time.monotonic()
                last_signature = signature
            status('native_transient_running', native_pid=child.pid,
                   samples=len(data), simulation_time_s=data[-1][0] if data else 0,
                   completed_linear_solves=count, maximum_scaled_true_residual=max_residual,
                   invalid_linear_solves=invalid, native_elapsed_s=time.monotonic()-started)
            if child.poll() is not None:
                break
            if invalid:
                reason = 'numerical_residual_gate_failed'
            elif time.clock_gettime(time.CLOCK_BOOTTIME) >= NATIVE_DEADLINE:
                reason = '48_hour_campaign_budget_assessment_reserve'
            elif time.monotonic() - last_activity > 3600:
                reason = 'no_log_or_waveform_progress_for_one_hour'
            if reason:
                stop()
                continue  # Drain the log and waveform after the child stops.
            time.sleep(10)
    assert all(math.isfinite(v) for row in data for v in row)
    assert all(a[0] < b[0] for a, b in zip(data, data[1:]))
    complete = bool(child.returncode == 0 and data and data[-1][0] >= 80e-9*(1-1e-9)
                    and 'End of Xyce(TM) Simulation' in wave.read_text())
    edges = []
    for left, right in zip(data, data[1:]):
        if left[1] < .9 <= right[1]:
            edge = left[0] + (.9-left[1])*(right[0]-left[0])/(right[1]-left[1])
            if edge >= 20e-9:
                edges.append(edge)
    metrics = dict(mhz=(len(edges)-1)/(edges[-1]-edges[0])*1e-6,
                   periods=len(edges)-1) if len(edges) >= 4 else None
    for path, sha in pins.items():
        assert digest(Path(path)) == sha, path
    save(OUT / 'assessment.json', dict(input_sha256=pins,
         artifacts={str(p): digest(p) for p in (wave, OUT / 'native.log') if p.exists()},
         completed_full_native_transient=complete, native_exit=child.returncode,
         stop_reason=reason, samples=len(data), simulation_time_s=data[-1][0] if data else 0,
         adapter_linear_solves=count, maximum_scaled_true_residual=max_residual,
         invalid_linear_solves=invalid, full_residual_gate_passed=bool(count and not invalid),
         metrics=metrics, method_frequency_convergence_qualified=False,
         full_parent_loading_qualified=False, runtime_model_eligible=False,
         release_qualified=False, adopted=False))
    status('completed_native_baseline' if complete and not invalid and metrics
           else 'native_inconclusive_or_nonpass', native_exit=child.returncode,
           stop_reason=reason, simulation_time_s=data[-1][0] if data else 0,
           completed_linear_solves=count, metrics=metrics)


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        stop()
        save(OUT / 'runner_failure.json', dict(error_type=type(error).__name__, message=str(error)))
        status('runner_nonpass', reason=str(error))
        raise
    finally:
        stop()
