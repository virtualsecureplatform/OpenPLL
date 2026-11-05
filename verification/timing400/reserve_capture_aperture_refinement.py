#!/usr/bin/env python3
"""Reserve admission for the never-launched capture refinement, then release it."""
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
folder=base/'capture_aperture_refinement_fs125_001';prior=folder/'run_001';plan=folder/'plan.json'
owner=json.loads((prior/'owner.json').read_text());pid=owner['runner_pid'];identity=process(pid)
assert identity['live'] and any(x.endswith('run_capture_aperture_refinement.py') for x in identity['argv'])
deadline=owner['deadline_uptime'];assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
out=base/'capture_aperture_priority_reservation_001';out.mkdir(exist_ok=False)
runner=Path(__file__).with_name('run_reserved_capture_aperture_refinement.py').resolve();child=None
with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    assert process(pid)['argv']==identity['argv']
    assert json.loads((prior/'status.json').read_text())['state']=='queued_for_shared_native_capacity'
    assert not (prior/'launch.json').exists() and not (prior/'native_exit.json').exists() and not (prior/'run.log').exists()
    active=live_engines();assert len(active)<=4
    assert not any(any(str(prior) in arg for arg in process(p)['argv']) for p in active)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,
        prior_worker_identity=identity,budget_restarted=False,input_sha256={str(p):digest(p) for p in (Path(__file__).resolve(),runner,plan,prior/'owner.json')}))
    os.kill(pid,signal.SIGTERM);until=time.monotonic()+10
    while process(pid)['live'] and time.monotonic()<until:time.sleep(.1)
    assert not process(pid)['live']
    handoff=dict(prior_worker_pid=pid,prior_worker_terminal=True,prior_native_cases_started=0,original_output=str(prior),
        replacement_output=str(folder/'run_002'),deadline_uptime=deadline,native_case_retried=False,
        active_native_processes_interrupted=False,admission_released_after_launch=True,
        reason='Capture refinement informs missing setup/hold and reset constraints; avoid starvation behind full sequential campaign')
    save(out/'handoff.json',handoff);save(folder/'pre_native_priority_handoff.json',handoff)
    while time.clock_gettime(time.CLOCK_BOOTTIME)<deadline:
        active=live_engines();mem={line.split(':',1)[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()}
        save(out/'status.json',dict(state='reserving_next_native_slot',observed_native_pids=active,deadline_uptime=deadline,release_qualified=False))
        if len(active)<4 and mem['MemAvailable']>=8*1024**3:
            command=[sys.executable,str(runner),'--admission-lock-fd',str(lock.fileno())]
            with (out/'worker.log').open('x') as log:
                child=subprocess.Popen(command,cwd=root,stdout=log,stderr=subprocess.STDOUT,pass_fds=(lock.fileno(),),start_new_session=True,
                    env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'))
            save(out/'replacement_owner.json',dict(runner_pid=child.pid,command=command,deadline_uptime=deadline))
            break
        time.sleep(min(5,max(.01,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
# Child owns admission until its native launch. Parent foreground persists for
# container lifetime without holding other slots for the whole transient.
if child is None:
    save(out/'status.json',dict(state='deadline_before_admission_inconclusive',release_qualified=False))
else:
    save(out/'status.json',dict(state='foreground_wait_for_capture_refinement',replacement_runner_pid=child.pid,release_qualified=False))
    code=child.wait()
    save(out/'assessment.json',dict(replacement_worker_exit=code,deadline_extended=False,prior_native_cases_started=0,
        active_native_processes_interrupted=False,admission_released_after_launch=True,release_qualified=False))
    save(out/'status.json',dict(state='capture_refinement_terminal',replacement_worker_exit=code,release_qualified=False))
