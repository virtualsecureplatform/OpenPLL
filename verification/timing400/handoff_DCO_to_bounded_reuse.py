#!/usr/bin/env python3
"""One solver-only trial with terminal old native, native GID gate and fixed deadline."""
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
prepared=base/'DCO_bounded_reuse_trial_prepared_001';plan=json.loads((prepared/'plan.json').read_text())
prior=Path(plan['source_point']);deadline=plan['deadline_uptime']
owner=json.loads((prior/'owner.json').read_text());state=json.loads((prior/'status.json').read_text())
source_runner=owner['runner_pid'];source_native=state['native_pid']
expected_native=process(source_native);expected_runner=process(source_runner)
assert expected_native['live'] and expected_runner['live']
assert expected_native['argv'][-1]==str(prior/'point.cir')
assert any(arg.endswith('run_DCO_gear_fallback_v3.py') for arg in expected_runner['argv'])
for p,sha in plan['input_sha256'].items():
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    assert digest(Path(p))==sha,p
observer=base/'DCO_Gear_runtime_observer_001';history_bytes=(observer/'observations.jsonl').read_bytes()
history=[json.loads(line) for line in history_bytes.splitlines()];latest=history[-1]
assert latest['source_native_pid']==source_native and latest['source_native_live']
assert latest['post_reset_falling_edges']>=4 and time.clock_gettime(time.CLOCK_BOOTTIME)-latest['uptime']<90
window=[row for row in history if row['uptime']>=latest['uptime']-900]
span=window[-1]['uptime']-window[0]['uptime'];advance=window[-1]['simulation_time_s']-window[0]['simulation_time_s']
assert span>=750 and advance>0
observed_rate=advance/span;required_rate=(80e-9-latest['simulation_time_s'])/(deadline-latest['uptime'])
assert observed_rate<.6*required_rate
out=base/'DCO_Gear_to_bounded_reuse_handoff_001';out.mkdir(exist_ok=False)
(out/'retained_observer_history.jsonl').write_bytes(history_bytes)
map_runner=Path(__file__).with_name('check_bounded_reuse_DCO_map.py').resolve()
runner=Path(__file__).with_name('run_DCO_bounded_reuse_trial.py').resolve()
save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,
    source_native_pid=source_native,source_runner_pid=source_runner,budget_restarted=False))
save(out/'decision.json',dict(input_sha256={str(p):digest(p) for p in
    (Path(__file__).resolve(),prepared/'plan.json',map_runner,runner,out/'retained_observer_history.jsonl',base/'bounded_reuse_native_controls_audit_002/assessment.json')},
    source_native_identity=expected_native,source_runner_identity=expected_runner,
    observed_ns_per_minute=observed_rate*60e9,required_ns_per_minute=required_rate*60e9,
    reason='Recent Gear throughput cannot finish80ns under the inherited deadline; native-correlated bounded factor reuse is a distinct solver trial.',
    solver_change_selected=True,physical_circuit_unchanged=True,integration_method_unchanged=True,numerical_tolerances_unchanged=True,
    deadline_uptime=deadline,full_DCO_speedup_proven=False,release_qualified=False,adopted=False))
replacement=None
with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    assert process(source_native)==expected_native and process(source_runner)==expected_runner
    save(out/'status.json',dict(state='stopping_identified_native_for_solver_trial',native_pid=source_native,release_qualified=False))
    assert os.getpgid(source_native)==source_native;os.killpg(source_native,signal.SIGTERM)
    end=min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+10)
    while process(source_native)['live'] and time.clock_gettime(time.CLOCK_BOOTTIME)<end:time.sleep(.2)
    if process(source_native)['live']:
        assert process(source_native)['argv']==expected_native['argv'];os.killpg(source_native,signal.SIGKILL)
    assert not process(source_native)['live']
    end=min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+180)
    while process(source_runner)['live'] and time.clock_gettime(time.CLOCK_BOOTTIME)<end:time.sleep(1)
    receipt=prior/'assessment.json'
    assert not process(source_runner)['live'] and receipt.exists()
    assert not json.loads(receipt.read_text())['completed_full_native_transient']
    handoff=out/'handoff.json'
    save(handoff,dict(source_point=str(prior),source_native_pid=source_native,source_runner_pid=source_runner,
        prior_assessment_sha256=digest(receipt),deadline_uptime=deadline,solver_change_selected=True,
        reason='Controlled solver handoff; partial native data remain inconclusive, not a physical oscillation failure.',
        decision_sha256=digest(out/'decision.json'),release_qualified=False))
    with (out/'map_worker.log').open('x') as log:
        child=subprocess.Popen([sys.executable,str(map_runner),'--handoff',str(handoff),'--admission-lock-fd',str(lock.fileno())],
            cwd=root,stdout=log,stderr=subprocess.STDOUT,pass_fds=(lock.fileno(),),start_new_session=True)
    save(out/'status.json',dict(state='verifying_new_binary_full_DCO_variable_map',map_runner_pid=child.pid,release_qualified=False))
    code=child.wait()
    mapping=base/'DCO_bounded_reuse_variable_map_001/assessment.json'
    if code!=0 or not mapping.exists() or not json.loads(mapping.read_text())['full_DCO_variable_map_verified']:
        save(out/'assessment.json',dict(native_map_exit=code,changed_solver_transient_started=False,prior_terminal_receipt_preserved=True,release_qualified=False))
        raise SystemExit('New solver DCO variable-map gate did not pass; no transient launched')
    with (out/'trial_worker.log').open('x') as log:
        replacement=subprocess.Popen([sys.executable,str(runner),'--handoff',str(handoff),'--admission-lock-fd',str(lock.fileno())],
            cwd=root,stdout=log,stderr=subprocess.STDOUT,pass_fds=(lock.fileno(),),start_new_session=True,
            env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'))
    save(out/'replacement_owner.json',dict(runner_pid=replacement.pid,deadline_uptime=deadline,inherited_admission_lock=True,budget_restarted=False))
# Parent closes its lock copy; child owns it through admission. Keep foreground
# alive while the trial runs so its SIF mount survives.
save(out/'status.json',dict(state='foreground_wait_for_solver_trial',replacement_runner_pid=replacement.pid,release_qualified=False))
code=replacement.wait()
save(out/'assessment.json',dict(replacement_exit=code,container_foreground_lifetime_preserved=True,
    deadline_uptime=deadline,budget_restarted=False,prior_native_retried=False,release_qualified=False,adopted=False))
save(out/'status.json',dict(state='solver_trial_terminal',replacement_exit=code,release_qualified=False))
