#!/usr/bin/env python3
"""Run one distinct PVT case under a shared campaign deadline and native cap."""
import argparse
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import time
from compile_local_C_operators_v2 import digest,save
from run_DCO_domain_point_v3 import live_engines
from assess_compact_numerical_holdout_v2 import assess

parser=argparse.ArgumentParser();parser.add_argument('--plan',type=Path,required=True)
parser.add_argument('--campaign',type=Path,required=True);parser.add_argument('--admission-lock-fd',type=int,required=True);args=parser.parse_args()
root=Path(__file__).resolve().parents[2]
observed=os.fstat(args.admission_lock_fd);expected=(root/'build/timing400/guarded_native_admission.lock').stat()
assert (observed.st_dev,observed.st_ino)==(expected.st_dev,expected.st_ino), 'wrong inherited admission lock'
plan=json.loads(args.plan.read_text());owner=json.loads((args.campaign/'owner.json').read_text())
deadline=owner['deadline_uptime'];out=args.plan.parent/'run_002';out.mkdir(exist_ok=False)
pins=dict(plan['input_sha256'])
for p in [Path(__file__),args.plan,args.campaign/'owner.json',Path(__file__).with_name('assess_compact_numerical_holdout_v2.py')]:
    pins[str(p.resolve())]=digest(p)
child=None

def status(state,**extra):
    save(out/'status.json',dict(state=state,runner_pid=os.getpid(),deadline_uptime=deadline,
        release_qualified=False,adopted=False,**extra))

def stop():
    if child is not None and child.poll() is None:
        os.killpg(child.pid,signal.SIGTERM)
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()

def limits():
    resource.setrlimit(resource.RLIMIT_AS,(6*1024**3,6*1024**3))
    remaining=max(1,int(deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
    resource.setrlimit(resource.RLIMIT_CPU,(remaining,remaining+1))

try:
    status('checking_frozen_case_inputs')
    for path,sha in pins.items():assert digest(Path(path))==sha,path
    deck=args.plan.parent/'batch.cir';binary=Path('/opt/xyce/bin/Xyce')
    while time.clock_gettime(time.CLOCK_BOOTTIME)<deadline:
        with os.fdopen(os.dup(args.admission_lock_fd),'a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            active=live_engines()
            mem={line.split(':',1)[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()}
            if len(active)<4 and mem['MemAvailable']>=8*1024**3:
                command=[str(binary),'-linsolv','KLU','-quiet','-o',str(out/'batch'),str(deck)]
                with (out/'run.log').open('x') as log:
                    before=time.clock_gettime(time.CLOCK_BOOTTIME)
                    child=subprocess.Popen(command,cwd=out,stdout=log,stderr=subprocess.STDOUT,
                        start_new_session=True,preexec_fn=limits,
                        env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'))
                save(out/'launch.json',dict(pid=child.pid,runner_pid=os.getpid(),command=command,
                    observed_utc=datetime.now(timezone.utc).isoformat(),native_before=active,
                    maximum_native_workers=4,address_space_limit_GiB=6,deadline_uptime=deadline,
                    input_sha256=pins,automatic_identical_retry=False,release_qualified=False))
                status('native_running',native_pid=child.pid);break
        status('queued_for_shared_native_capacity',observed_native_pids=active)
        time.sleep(1)
    if child is None:raise TimeoutError('campaign ended before admission')
    try:code=child.wait(timeout=max(.001,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
    except subprocess.TimeoutExpired:stop();raise TimeoutError('campaign ended during native execution')
    save(out/'native_exit.json',dict(native_exit=code,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-before,
        release_qualified=False))
    if code:
        status('native_nonpass',native_exit=code)
    else:
        assess(plan,pins,out,deadline)
except TimeoutError as error:
    stop();status('timeout_inconclusive',reason=str(error))
except Exception as error:
    stop();save(out/'runner_failure.json',dict(error_type=type(error).__name__,message=str(error),release_qualified=False))
    status('runner_nonpass');raise
finally:stop()
