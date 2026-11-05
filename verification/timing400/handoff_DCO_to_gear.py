#!/usr/bin/env python3
"""One documented changed-method handoff; preserve the existing DCO deadline."""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    prior = base / 'DCO_domain_nom_tt27_c0_f247_80ns_wire_preconditioned_002'
    prepared = base / 'DCO_gear_method_fallback_prepared_001'
    observer = base / 'DCO_wire_preconditioned_runtime_observer_001'
    runner = Path(__file__).with_name('run_DCO_gear_fallback_v2.py').resolve()
    owner = json.loads((prior / 'owner.json').read_text())
    deadline = owner['deadline_uptime']
    source_runner = owner['runner_pid']
    state = json.loads((prior / 'status.json').read_text())
    source_native = state['native_pid']
    expected_native, expected_runner = process(source_native), process(source_runner)
    assert expected_native['live'] and expected_runner['live']
    assert str(prior / 'point.cir') in expected_native['argv']
    assert any(arg.endswith('run_DCO_wire_preconditioned_point_v2.py') for arg in expected_runner['argv'])
    prepared_plan = json.loads((prepared / 'plan.json').read_text())
    assert prepared_plan['deadline_uptime'] == deadline
    for path, sha in prepared_plan['input_sha256'].items():
        assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
        assert digest(Path(path)) == sha, path
    history_bytes = (observer / 'observations.jsonl').read_bytes()
    observations = [json.loads(line) for line in history_bytes.splitlines()]
    latest = observations[-1]
    assert latest['source_native_pid'] == source_native and latest['source_native_live']
    assert latest['post_reset_rising_edges'] >= 2 and latest['post_reset_falling_edges'] >= 2
    assert time.clock_gettime(time.CLOCK_BOOTTIME)-latest['uptime'] < 90
    window = [row for row in observations if row['uptime'] >= latest['uptime']-900]
    elapsed = window[-1]['uptime']-window[0]['uptime']
    advance = window[-1]['simulation_time_s']-window[0]['simulation_time_s']
    assert elapsed >= 750 and advance >= .4e-9
    rates = [(b['simulation_time_s']-a['simulation_time_s'])/(b['uptime']-a['uptime'])
             for a, b in zip(window, window[1:])]
    required = (80e-9-latest['simulation_time_s'])/(deadline-time.clock_gettime(time.CLOCK_BOOTTIME))
    assert max(rates) < .6*required
    audit = base / 'wire_preconditioned_native_controls_checks_002/assessment.json'
    assert json.loads(audit.read_text())['completed_native_control_audit_passed']
    out = base / 'DCO_TRAP_to_GEAR_runtime_handoff_001'
    out.mkdir(exist_ok=False)
    (out / 'retained_observer_history.jsonl').write_bytes(history_bytes)
    save(out / 'owner.json', dict(runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(), deadline_uptime=deadline,
        budget_restarted=False, source_native_pid=source_native, source_runner_pid=source_runner))
    save(out / 'decision.json', dict(input_sha256={str(p): digest(p) for p in
        (Path(__file__).resolve(), runner, prepared / 'plan.json', audit,
         out / 'retained_observer_history.jsonl')},
        source_native_identity=expected_native, source_runner_identity=expected_runner,
        observation_window_s=elapsed, observation_window_advance_ns=advance*1e9,
        best_observed_interval_rate_ns_per_min=max(rates)*60e9,
        required_average_rate_ns_per_min=required*60e9,
        throughput_remains_startup_affected=True, definitive_finish_ETA_claimed=False,
        reason='Observed cyclic TRAP throughput remains far below the average needed '
               'to finish80ns under the existing deadline; select validated method-only Gear trial.',
        method_change_selected=True, physical_circuit_unchanged=True,
        numerical_tolerances_unchanged=True, deadline_uptime=deadline,
        release_qualified=False, adopted=False))
    with (base.parent / 'guarded_native_admission.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        assert process(source_native) == expected_native and process(source_runner) == expected_runner
        save(out / 'status.json', dict(state='stopping_identified_TRAP_native_for_method_handoff',
            native_pid=source_native, deadline_uptime=deadline, release_qualified=False))
        assert os.getpgid(source_native) == source_native
        os.killpg(source_native, signal.SIGTERM)
        stop_deadline = min(deadline, time.clock_gettime(time.CLOCK_BOOTTIME)+10)
        while process(source_native)['live'] and time.clock_gettime(time.CLOCK_BOOTTIME) < stop_deadline:
            time.sleep(.2)
        if process(source_native)['live']:
            assert process(source_native)['argv'] == expected_native['argv']
            os.killpg(source_native, signal.SIGKILL)
        assert not process(source_native)['live']
        finish_deadline = min(deadline, time.clock_gettime(time.CLOCK_BOOTTIME)+180)
        receipt_path = prior / 'assessment.json'
        while process(source_runner)['live'] and time.clock_gettime(time.CLOCK_BOOTTIME) < finish_deadline:
            save(out / 'status.json', dict(state='waiting_for_prior_terminal_receipt_under_admission_lock',
                deadline_uptime=deadline, release_qualified=False))
            time.sleep(1)
        assert not process(source_runner)['live'] and receipt_path.exists()
        receipt = json.loads(receipt_path.read_text())
        assert not receipt['completed_full_native_transient']
        handoff = out / 'handoff.json'
        save(handoff, dict(source_point=str(prior), source_native_pid=source_native,
            source_runner_pid=source_runner, prior_assessment_sha256=digest(receipt_path),
            deadline_uptime=deadline, method_change_selected=True,
            reason='Explicit runtime handoff; prior signal exit is a controlled interruption, '
                   'not evidence of physical oscillation failure. Partial data remains inconclusive.',
            decision_sha256=digest(out / 'decision.json'), release_qualified=False))
        with (out / 'gear_worker.log').open('x') as log:
            replacement = subprocess.Popen([sys.executable, str(runner), '--handoff', str(handoff),
                '--admission-lock-fd', str(lock.fileno())], cwd=root,
                stdout=log, stderr=subprocess.STDOUT, pass_fds=(lock.fileno(),),
                start_new_session=True,
                env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1'))
        save(out / 'replacement_owner.json', dict(runner_pid=replacement.pid,
            deadline_uptime=deadline, inherited_admission_lock=True, budget_restarted=False))
        # Closing the parent's copy leaves the lock owned by the replacement.
    save(out / 'status.json', dict(state='changed_method_runner_started',
        replacement_runner_pid=replacement.pid, deadline_uptime=deadline,
        prior_native_stopped=True, prior_terminal_receipt_retained=True,
        release_qualified=False))
    print(json.dumps(dict(replacement_runner_pid=replacement.pid,
                          deadline_uptime=deadline, budget_restarted=False)))


if __name__ == '__main__':
    main()
