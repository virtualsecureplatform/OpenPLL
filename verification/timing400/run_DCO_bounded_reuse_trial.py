#!/usr/bin/env python3
"""Run a documented solver trial after terminal prior DCO and matching native IDs."""
import argparse
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
from record_qualification_progress_045 import process
from run_DCO_domain_point_v3 import live_engines
from run_DCO_stock_threaded_point_v2 import rows


def admission_lock(base, inherited_fd=None):
    path = base.parent / 'guarded_native_admission.lock'
    if inherited_fd is None:
        return path.open('a+')
    expected, observed = path.stat(), os.fstat(inherited_fd)
    assert (expected.st_dev, expected.st_ino) == (observed.st_dev, observed.st_ino), 'Wrong inherited admission lock'
    # An inherited descriptor shares the handoff controller's open-file lock.
    # Transfer ownership to this context, which releases it after admission.
    fcntl.flock(inherited_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return os.fdopen(inherited_fd, 'a+')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--handoff', type=Path)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--admission-lock-fd', type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    prepared = base / 'DCO_bounded_reuse_trial_prepared_001'
    plan_path = prepared / 'plan.json'
    plan = json.loads(plan_path.read_text())
    prior = Path(plan['source_point']); deadline = plan['deadline_uptime']
    prior_owner = json.loads((prior/'owner.json').read_text())
    prior_state = json.loads((prior/'status.json').read_text())
    native = process(prior_state.get('native_pid', -1)); runner = process(prior_owner['runner_pid'])
    if args.check_only:
        print(json.dumps(dict(check_only=True, native_started=False, prior_native=native,
            prior_runner=runner, deadline_uptime=deadline, candidate_binary=plan['binary'])))
        return
    assert args.handoff is not None
    assert not native['live'] and not runner['live']
    receipt_path=prior/'assessment.json'; handoff=json.loads(args.handoff.read_text())
    assert handoff['source_point']==str(prior) and handoff['source_runner_pid']==prior_owner['runner_pid']
    assert handoff['prior_assessment_sha256']==digest(receipt_path)
    assert handoff['deadline_uptime']==deadline and handoff['solver_change_selected']
    assert not process(handoff['source_native_pid'])['live']
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    audit_path=base/'bounded_reuse_native_controls_audit_002/assessment.json'
    audit=json.loads(audit_path.read_text())
    assert audit['completed_native_control_audit_passed'] and audit['separate_timestep_and_tolerance_holdouts_verified']
    mapping_path=base/'DCO_bounded_reuse_variable_map_001/assessment.json'
    assert json.loads(mapping_path.read_text())['full_DCO_variable_map_verified']
    build_path=base/'wire_preconditioned_Xyce_bounded_reuse_001/recovered_build_assessment.json'
    build=json.loads(build_path.read_text());binary=Path(build['binary'])
    assert build['experimental_build_completed'] and digest(binary)==build['binary_sha256']
    meta_path=base/'native_wire_preconditioner_metadata_001/assessment.json'
    meta=json.loads(meta_path.read_text());metadata=Path(meta['metadata_file'])
    assert digest(metadata)==meta['metadata_sha256']
    out=base/'DCO_domain_nom_tt27_c0_f247_80ns_bounded_reuse_gear_001'
    out.mkdir(exist_ok=False)
    deck = out / 'point.cir'
    deck.write_bytes((prepared / 'point.cir').read_bytes())
    pins = dict(plan['input_sha256'])
    for path in (Path(__file__).resolve(), args.handoff.resolve(), receipt_path, plan_path,
                 audit_path, mapping_path, build_path, binary, meta_path, metadata, deck,
                 Path(__file__).with_name('run_DCO_stock_threaded_point_v2.py'),
                 Path(__file__).with_name('run_DCO_domain_point_v3.py'),
                 Path(__file__).with_name('record_qualification_progress_045.py'),
                 Path(__file__).with_name('compile_local_C_operators_v2.py')):
        pins[str(path)] = digest(path)
    child = None

    def status(state, **extra):
        save(out / 'status.json', dict(state=state, runner_pid=os.getpid(),
            observed_utc=datetime.now(timezone.utc).isoformat(), deadline_uptime=deadline,
            release_qualified=False, adopted=False, **extra))

    def remaining():
        seconds = deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if seconds <= 0:
            raise TimeoutError('inherited DCO deadline reached')
        return seconds

    def stop():
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()

    def limits():
        resource.setrlimit(resource.RLIMIT_AS, (48*1024**3, 48*1024**3))
        seconds = max(1, int(remaining()))
        resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds+1))

    save(out / 'owner.json', dict(runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(), deadline_uptime=deadline,
        inherited_owner=str(prior / 'owner.json'), budget_restarted=False,
        method='GEAR', maximum_native_workers=4, simultaneous_large_DCO_runs_allowed=False))
    save(out / 'input_manifest.json', dict(input_sha256=pins, parameters=plan['parameters'],
        integration_method='GEAR', physical_circuit_unchanged=True,
        method_frequency_convergence_qualified=False, release_qualified=False))
    try:
        status('checking_frozen_inputs')
        for path, sha in pins.items():
            remaining()
            assert digest(Path(path)) == sha, path
        while True:
            remaining()
            with admission_lock(base, args.admission_lock_fd) as lock:
                args.admission_lock_fd = None
                fcntl.flock(lock, fcntl.LOCK_EX)
                active = live_engines()
                other_large = []
                for pid in active:
                    argv = process(pid).get('argv', [])
                    if any('DCO_domain_' in arg or 'wire_preconditioned_Xyce_' in arg for arg in argv):
                        other_large.append(pid)
                mem = {line.split(':', 1)[0]: int(line.split()[1])*1024
                       for line in Path('/proc/meminfo').read_text().splitlines()}
                if len(active) < 4 and not other_large and mem['MemAvailable'] >= 28*1024**3:
                    command = [str(binary), '-quiet', '-o', str(deck), str(deck)]
                    with (out / 'native.log').open('x') as log:
                        child = subprocess.Popen(command, cwd=out, stdout=log,
                            stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=limits,
                            env=dict(os.environ, OPENPLL_WIRE_PC=str(metadata),
                                     OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1'))
                    save(out / 'launch.json', dict(pid=child.pid, command=command,
                        native_before=active, deadline_uptime=deadline))
                    break
            status('queued_for_shared_native_capacity', observed_native_pids=active,
                   observed_other_large_DCO_pids=other_large)
            time.sleep(min(5, remaining()))
        wave = Path(str(deck)+'.prn')
        while child.poll() is None:
            remaining()
            data = rows(wave)
            status('native_experimental_point_running', native_pid=child.pid,
                   samples=len(data), simulation_time_s=data[-1][0] if data else 0)
            time.sleep(min(10, remaining()))
        data = rows(wave)
        completed = child.returncode == 0 and wave.exists()
        if completed:
            assert 'End of Xyce(TM) Simulation' in wave.read_text()
            assert data and data[-1][0] >= 80e-9*(1-1e-7)
            assert all(math.isfinite(v) for row in data for v in row)
            assert all(a[0] < b[0] for a, b in zip(data, data[1:]))
        edges = []
        for a, b in zip(data, data[1:]):
            if a[1] < .9 <= b[1]:
                edge = a[0]+(.9-a[1])*(b[0]-a[0])/(b[1]-a[1])
                if edge >= 20e-9:
                    edges.append(edge)
        metrics = dict(mhz=(len(edges)-1)/(edges[-1]-edges[0])*1e-6,
                       periods=len(edges)-1) if len(edges) >= 4 else None
        solves = []
        for line in (out / 'native.log').read_text().splitlines():
            match = re.fullmatch(r'OpenPLL_wire_PC call=(\d+) alpha=(\S+) iterations=(\d+) scaled_true_relative_residual=(\S+) seconds=(\S+) status=(\d+)', line)
            if match:
                solves.append((float(match[4]), int(match[6])))
        if completed:
            assert solves and all(math.isfinite(r) and r <= 1e-12 and code == 0 for r, code in solves)
        for path, sha in pins.items():
            remaining()
            assert digest(Path(path)) == sha, path
        artifacts = {str(p): digest(p) for p in (wave, out / 'native.log') if p.exists()}
        remaining()
        save(out / 'assessment.json', dict(input_sha256=pins, artifacts=artifacts,
            completed_full_native_transient=completed, native_exit=child.returncode,
            samples=len(data), simulation_time_s=data[-1][0] if data else None,
            metrics=metrics, adapter_linear_solves=len(solves),
            method_frequency_convergence_qualified=False, full_parent_loading_qualified=False,
            runtime_model_eligible=False, release_qualified=False, adopted=False))
        status('completed_native_diagnostic' if completed and metrics else 'native_or_oscillation_nonpass',
               native_exit=child.returncode, metrics=metrics)
    except TimeoutError as error:
        stop()
        status('timeout_inconclusive', reason=str(error))
    except Exception as error:
        stop()
        save(out / 'runner_failure.json', dict(error_type=type(error).__name__, message=str(error)))
        status('runner_nonpass')
        raise
    finally:
        stop()


if __name__ == '__main__':
    main()
