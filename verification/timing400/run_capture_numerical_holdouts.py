#!/usr/bin/env python3
"""Run one capture numerical control at a time under the inherited deadline."""
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from compile_local_C_operators_v2 import digest,save
from run_DCO_domain_point_v3 import live_engines
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001';out=base/'capture_numerical_holdouts_fs125_001'
plan_path=out/'plan.json';plan=json.loads(plan_path.read_text());deadline=plan['shared_deadline_uptime']
proof=base/'capture_numerical_holdout_preparation_checks_001/assessment.json';checked=json.loads(proof.read_text())
assert checked['native_PWL_sources_verified']==864 and checked['synthetic_separated_controls_passing']==36
assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
worker=Path(__file__).with_name('run_capture_numerical_holdout_case.py').resolve()
pins={str(p):digest(p) for p in (Path(__file__).resolve(),plan_path,proof,worker,Path(plan['inherited_campaign_owner']))}
assert not (out/'owner.json').exists()
save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,
    inherited_owner=plan['inherited_campaign_owner'],budget_restarted=False,maximum_case_workers=1,maximum_native_workers=4,
    automatic_identical_retry=False,input_sha256=pins))
results=[];baseline_valid=False
for item in plan['cases']:
    if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
        results.append(dict(item,state='deadline_before_case'));continue
    if item['label']!='subset_baseline' and not baseline_valid:
        results.append(dict(item,state='blocked_invalid_subset_baseline'));continue
    path=Path(item['plan']);assert digest(path)==item['plan_sha256']
    child=None
    with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        while time.clock_gettime(time.CLOCK_BOOTTIME)<deadline:
            active=live_engines();mem={line.split(':',1)[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()}
            save(out/'status.json',dict(state='reserving_next_slot_for_capture_control',case=item['label'],observed_native_pids=active,
                deadline_uptime=deadline,release_qualified=False))
            if len(active)<4 and mem['MemAvailable']>=8*1024**3:
                command=[sys.executable,str(worker),'--plan',str(path),'--campaign',str(out),'--admission-lock-fd',str(lock.fileno())]
                with (path.parent/'worker.log').open('x') as log:
                    child=subprocess.Popen(command,cwd=root,stdout=log,stderr=subprocess.STDOUT,pass_fds=(lock.fileno(),),start_new_session=True,
                        env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'))
                save(path.parent/'worker_owner.json',dict(worker_pid=child.pid,command=command,deadline_uptime=deadline));break
            time.sleep(min(5,max(.01,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    if child is None:
        results.append(dict(item,state='deadline_before_admission'));continue
    # Parent closes admission, while the child retains it until native launch.
    # Foreground parent waits to preserve the SIF mount for all descendants.
    save(out/'status.json',dict(state='capture_control_running_or_preparing',case=item['label'],worker_pid=child.pid,deadline_uptime=deadline,release_qualified=False))
    code=child.wait();receipt=path.parent/'run_001/assessment.json';state=path.parent/'run_001/status.json'
    result=dict(item,worker_exit=code,state=json.loads(state.read_text())['state'] if state.exists() else 'missing_worker_state',
        assessment=str(receipt) if receipt.exists() else None,assessment_sha256=digest(receipt) if receipt.exists() else None)
    results.append(result);save(out/'case_results.json',results)
    if item['label']=='subset_baseline' and receipt.exists():
        r=json.loads(receipt.read_text());baseline_valid=r['observation_integrity_passing']==72 and r['separated_controls_passing']==36
save(out/'assessment.json',dict(cases=results,input_sha256=pins,subset_baseline_valid=baseline_valid,
    all_controls_have_terminal_receipts=len(results)==4 and all(r.get('assessment') for r in results),
    numerical_domain_enclosure_qualified=False,setup_hold_recovery_removal_qualified=False,release_qualified=False,adopted=False))
save(out/'status.json',dict(state='terminal_capture_numerical_campaign',deadline_uptime=deadline,release_qualified=False))
