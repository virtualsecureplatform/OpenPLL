#!/usr/bin/env python3
"""Reserve the next slot for short critical-path controls; stop no native run."""
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
prior=base/'bounded_reuse_native_controls_001'
owner=json.loads((prior/'owner.json').read_text());pid=owner['runner_pid']
identity=process(pid)
assert identity['live'] and any(x.endswith('check_bounded_reuse_native_controls.py') for x in identity['argv'])
deadline=json.loads((base/'DCO_domain_nom_tt27_c0_f247_80ns_wire_preconditioned_gear_002/owner.json').read_text())['deadline_uptime']
assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
out=base/'bounded_reuse_controls_slot_reservation_001';out.mkdir(exist_ok=False)
runner=Path(__file__).with_name('check_bounded_reuse_native_controls_v2.py').resolve()
child=None
with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    status=json.loads((prior/'status.json').read_text())
    assert status['state']=='queued_for_shared_native_capacity' and status['case']=='candidate_names'
    receipts=json.loads((prior/'native_receipts.json').read_text())
    assert receipts and all(r.get('reused_completed_native_case') and 'stock' in r['case'] for r in receipts)
    assert not list(prior.glob('*/launch.json'))
    active=live_engines();assert len(active)<=4
    for native_pid in active:
        argv=process(native_pid)['argv'];assert not any(str(prior) in x for x in argv)
    assert process(pid)['argv']==identity['argv']
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        deadline_uptime=deadline,budget_restarted=False,prior_runner_identity=identity,
        input_sha256={str(p):digest(p) for p in (Path(__file__).resolve(),runner,prior/'owner.json',prior/'native_receipts.json')},
        active_native_processes_interrupted=False))
    os.kill(pid,signal.SIGTERM)
    stop_end=time.monotonic()+10
    while process(pid)['live'] and time.monotonic()<stop_end:time.sleep(.1)
    assert not process(pid)['live'],'queued controller did not terminate'
    handoff=dict(prior_runner_pid=pid,prior_runner_terminal=True,prior_native_cases_started=0,
        original_native_receipts_preserved=True,reason='Reserve next free slot for short critical-path solver controls',
        replacement_output=str(base/'bounded_reuse_native_controls_002'),deadline_uptime=deadline,
        automatic_identical_native_retry=False,active_native_processes_interrupted=False)
    save(out/'handoff.json',handoff);save(prior/'pre_native_scheduling_handoff.json',handoff)
    while time.clock_gettime(time.CLOCK_BOOTTIME)<deadline:
        active=live_engines()
        save(out/'status.json',dict(state='reserving_next_native_slot',observed_native_pids=active,
            deadline_uptime=deadline,release_qualified=False))
        if len(active)<4:
            command=[sys.executable,str(runner),'--build-runner-pid','203319','--output',
                str(base/'bounded_reuse_native_controls_002'),'--admission-lock-fd',str(lock.fileno())]
            with (out/'control_worker.log').open('x') as log:
                child=subprocess.Popen(command,cwd=root,stdout=log,stderr=subprocess.STDOUT,
                    start_new_session=True,pass_fds=(lock.fileno(),),
                    env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'))
            save(out/'replacement_owner.json',dict(runner_pid=child.pid,command=command,deadline_uptime=deadline))
            break
        time.sleep(min(5,max(.01,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    if child is not None:
        # Hold admission through this short sequence and keep the SIF foreground
        # alive. The child uses this same open-file description, never a new lock.
        save(out/'status.json',dict(state='reserved_control_sequence_running',replacement_runner_pid=child.pid,release_qualified=False))
        code=child.wait()
        save(out/'assessment.json',dict(replacement_exit=code,prior_native_cases_started=0,
            native_processes_interrupted=False,maximum_native_workers=4,deadline_extended=False,
            release_qualified=False))
        save(out/'status.json',dict(state='reserved_control_sequence_terminal',replacement_exit=code,release_qualified=False))
    else:
        save(out/'status.json',dict(state='deadline_before_admission_inconclusive',release_qualified=False))
