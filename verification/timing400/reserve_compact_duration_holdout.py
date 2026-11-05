#!/usr/bin/env python3
"""Prioritize the never-launched duration control; interrupt no native engine."""
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
from run_DCO_domain_point_v3 import live_engines
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
campaign=base/'selected_compact_numerical_holdouts_sf_m40_001';case=campaign/'duration_only'
prior=case/'run_001';plan=case/'plan.json'
pid=json.loads((case/'worker_owner.json').read_text())['worker_pid'];identity=process(pid)
assert identity['live'] and any(x.endswith('run_compact_numerical_holdout_case.py') for x in identity['argv'])
assert str(plan) in identity['argv']
deadline=json.loads((campaign/'owner.json').read_text())['deadline_uptime'];assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
out=base/'selected_duration_priority_reservation_001';out.mkdir(exist_ok=False)
runner=Path(__file__).with_name('run_reserved_compact_duration_holdout.py').resolve()
child=None
with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    assert process(pid)['argv']==identity['argv']
    assert json.loads((prior/'status.json').read_text())['state']=='queued_for_shared_native_capacity'
    assert not (prior/'launch.json').exists() and not (prior/'native_exit.json').exists() and not (prior/'run.log').exists()
    active=live_engines();assert len(active)<=4
    assert not any(any(str(prior) in arg for arg in process(p)['argv']) for p in active)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,
        prior_worker_identity=identity,budget_restarted=False,input_sha256={str(p):digest(p) for p in (Path(__file__).resolve(),runner,plan,campaign/'owner.json')}))
    os.kill(pid,signal.SIGTERM);until=time.monotonic()+10
    while process(pid)['live'] and time.monotonic()<until:time.sleep(.1)
    assert not process(pid)['live']
    handoff=dict(prior_worker_pid=pid,prior_native_cases_started=0,prior_worker_terminal=True,
        original_output=str(prior),replacement_output=str(case/'run_002'),deadline_uptime=deadline,
        reason='Reserve next free slot for short pending numerical duration control',native_case_retried=False,
        active_native_processes_interrupted=False)
    save(out/'handoff.json',handoff);save(case/'pre_native_priority_handoff.json',handoff)
    while time.clock_gettime(time.CLOCK_BOOTTIME)<deadline:
        active=live_engines()
        save(out/'status.json',dict(state='reserving_next_native_slot',observed_native_pids=active,deadline_uptime=deadline,release_qualified=False))
        if len(active)<4:
            command=[sys.executable,str(runner),'--plan',str(plan),'--campaign',str(campaign),'--admission-lock-fd',str(lock.fileno())]
            with (out/'worker.log').open('x') as log:
                child=subprocess.Popen(command,cwd=root,stdout=log,stderr=subprocess.STDOUT,pass_fds=(lock.fileno(),),start_new_session=True,
                    env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'))
            save(out/'replacement_owner.json',dict(runner_pid=child.pid,command=command,deadline_uptime=deadline))
            break
        time.sleep(min(5,max(.01,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    if child is None:
        save(out/'status.json',dict(state='deadline_before_admission_inconclusive',release_qualified=False))
    else:
        save(out/'status.json',dict(state='reserved_duration_control_running',replacement_runner_pid=child.pid,release_qualified=False))
        code=child.wait()
        save(out/'assessment.json',dict(replacement_worker_exit=code,deadline_extended=False,prior_native_cases_started=0,
            active_native_processes_interrupted=False,release_qualified=False))
        save(out/'status.json',dict(state='reserved_duration_control_terminal',replacement_worker_exit=code,release_qualified=False))
