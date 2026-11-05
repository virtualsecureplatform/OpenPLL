#!/usr/bin/env python3
"""Reserve a short native control sequence under the current DCO deadline."""
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process
from run_DCO_domain_point_v3 import live_engines
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
build=base/'wire_preconditioned_Xyce_compact_caps_001';proof=build/'assessment.json';built=json.loads(proof.read_text())
assert built['experimental_build_completed'] and digest(Path(built['binary']))==built['binary_sha256']
builder=json.loads((build/'owner.json').read_text())['runner_pid'];assert not process(builder)['live']
deadline=json.loads((base/'DCO_domain_nom_tt27_c0_f247_80ns_bounded_reuse_gear_001/owner.json').read_text())['deadline_uptime']
assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
out=base/'compact_constant_cap_control_reservation_001';out.mkdir(exist_ok=False)
runner=Path(__file__).with_name('check_compact_constant_cap_native_controls.py').resolve()
save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,
    budget_restarted=False,source_build_runner_pid=builder,input_sha256={str(p):digest(p) for p in (Path(__file__).resolve(),runner,proof)}))
child=None
with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    while time.clock_gettime(time.CLOCK_BOOTTIME)<deadline:
        active=live_engines();mem={line.split(':',1)[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()}
        save(out/'status.json',dict(state='reserving_next_native_slot',observed_native_pids=active,deadline_uptime=deadline,release_qualified=False))
        if len(active)<4 and mem['MemAvailable']>=8*1024**3:
            command=[sys.executable,str(runner),'--build-runner-pid',str(builder),'--output',str(base/'compact_constant_cap_native_controls_001'),'--admission-lock-fd',str(lock.fileno())]
            with (out/'worker.log').open('x') as log:
                child=subprocess.Popen(command,cwd=root,stdout=log,stderr=subprocess.STDOUT,pass_fds=(lock.fileno(),),start_new_session=True,
                    env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'))
            save(out/'replacement_owner.json',dict(runner_pid=child.pid,command=command,deadline_uptime=deadline));break
        time.sleep(min(5,max(.01,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    if child is None:save(out/'status.json',dict(state='deadline_before_admission_inconclusive',release_qualified=False))
    else:
        save(out/'status.json',dict(state='reserved_small_control_sequence_running',child_pid=child.pid,release_qualified=False))
        code=child.wait()
        save(out/'assessment.json',dict(control_worker_exit=code,deadline_extended=False,active_native_interrupted=False,release_qualified=False))
        save(out/'status.json',dict(state='control_sequence_terminal',control_worker_exit=code,release_qualified=False))
