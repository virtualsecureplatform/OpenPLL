#!/usr/bin/env python3
"""Fill missing sequential propagation points within the existing timing night.

This preserves 108 clock-to-Q/assertion fixtures and does not qualify setup/hold,
recovery/removal, interpolation, load/noise bounds or routed RC corners.
"""
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process

root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
out=base/'compact_sequential_15PVT_completion_001';out.mkdir(exist_ok=False)
shared_owner=base/'compact_nominal_15PVT_completion_001/owner.json'
shared=json.loads(shared_owner.read_text())
deadline=shared['deadline_uptime']
assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
    deadline_uptime=deadline,total_wall_limit_s=43200,maximum_case_workers=2,
    inherited_shared_owner=str(shared_owner),inherited_started_utc=shared['started_utc'],budget_restarted=False,
    maximum_total_native_workers=4,per_case_native_address_space_limit_GiB=6,
    automatic_identical_retry=False,existing_DCO_run_preserved=True))
def status(state,**extra):
    save(out/'status.json',dict(state=state,runner_pid=os.getpid(),deadline_uptime=deadline,
        release_qualified=False,adopted=False,**extra))
status('checking_retained_template_and_completed_PVT_inputs')
active=root/'verification/active_release.json';release=json.loads(active.read_text())
assert release['target_mhz']==400 and release['supply_v']==1.8 and release['pvt_points']==15
for key in ['requirements','plan','presets']:assert digest(root/release[key])==release['sha256'][key]
template=base/'compact_sequential_propagation_fs125_001/plan.json';plan=json.loads(template.read_text())
assert len(plan['fixtures'])==108 and len({c['master'] for c in plan['fixtures']})==6
assert plan['stop_ns']==64 and plan['max_step_ps']==2
for name,sha in plan['input_sha256'].items():assert digest(Path(name))==sha,name
existing=[('fs',125,template,base/'compact_sequential_propagation_fs125_001/audited_completion_001/assessment.json')]
reused=[]
for corner,temperature,prior_plan,receipt in existing:
    pp=json.loads(prior_plan.read_text());rr=json.loads(receipt.read_text())
    assert pp['fixtures']==plan['fixtures'] and pp['pvt']==dict(corner=corner,supply_v=1.8,temperature_c=temperature)
    assert rr['all_native_waveform_events_terminal'] and rr['fixtures']==108 and rr['passing']==108
    for name,sha in {**rr['input_sha256'],**rr['artifacts']}.items():assert digest(Path(name))==sha,name
    reused.append(dict(corner=corner,temperature_c=temperature,plan=str(prior_plan),assessment=str(receipt),
        assessment_sha256=digest(receipt),native_repeated=False))
worker=Path(__file__).with_name('run_compact_sequential_campaign_case.py')
parser=Path(__file__).with_name('assess_compact_sequential_campaign.py')
old_parser=Path(__file__).with_name('run_compact_sequential_propagation.py')
image=root/'build/apptainer/openpll-release-modern.sif'
pins={str(p.resolve()):digest(p) for p in [Path(__file__),worker,parser,old_parser,template,image,active,shared_owner]}
original=(template.parent/'batch.cir').read_text();lines=original.splitlines()
lib=lines[1];assert lib.startswith('.lib ') and lib.endswith(' fs')
temp='.options device temp=125';assert original.count(temp)==1
required={(c,t) for c in ['tt','ff','ss','sf','fs'] for t in [-40,27,125]}
complete={(c,t) for c,t,_,_ in existing};missing=required-complete;assert len(missing)==14
priority=[('ff',-40),('sf',-40),('sf',125)]
order=priority+sorted(missing-set(priority))
cases=[]
for corner,temperature in order:
    label=f'{corner}_{"m"+str(-temperature) if temperature<0 else "p"+str(temperature)}'
    folder=out/label;folder.mkdir()
    changed_lib=lib[:-2]+corner;changed_temp=f'.options device temp={temperature}'
    text=original.replace(lib,changed_lib,1).replace(temp,changed_temp,1)
    assert text.replace(changed_lib,lib,1).replace(changed_temp,temp,1)==original
    deck=folder/'batch.cir';deck.write_text(text)
    case_pins={**plan['input_sha256'],**pins,str(deck):digest(deck)}
    case_plan=dict(plan,input_sha256=case_pins,pvt=dict(corner=corner,supply_v=1.8,temperature_c=temperature),
        preparation_only_PVT_lines_changed=True,source_template=str(template),
        shared_campaign_deadline_uptime=deadline,physical_timing_qualified=False,release_qualified=False)
    prepared=folder/'plan.json';save(prepared,case_plan)
    cases.append(dict(label=label,corner=corner,temperature_c=temperature,plan=str(prepared),
        plan_sha256=digest(prepared),case_output=str(folder/'run_001')))
save(out/'plan.json',dict(input_sha256=pins,reused_completed_points=reused,missing_cases=cases,
    fixtures_per_PVT=108,sequential_masters=6,
    maximum_case_workers=2,maximum_total_native_workers=4,shared_deadline_uptime=deadline,
    qualification_scope='raw clock-to-Q/assertion propagation and output-slew observations only',
    sequential_constraints_qualified=False,physical_timing_qualified=False,release_qualified=False,adopted=False))
results=[]
def run(case):
    folder=Path(case['plan']).parent
    if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:return dict(case,state='campaign_deadline_before_case')
    with (folder/'worker.log').open('x') as log:
        child=subprocess.Popen([sys.executable,str(worker),'--plan',case['plan'],'--campaign',str(out)],
            cwd=root,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
            env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'))
        save(folder/'worker_owner.json',dict(worker_pid=child.pid,runner_pid=os.getpid(),deadline_uptime=deadline))
        # The worker enforces the shared deadline and stops its own native group.
        code=child.wait()
    receipt=Path(case['case_output'])/'assessment.json';statefile=Path(case['case_output'])/'status.json'
    observed=json.loads(statefile.read_text()) if statefile.exists() else None
    return dict(case,worker_exit=code,state=observed['state'] if observed else 'worker_unavailable',
        assessment=str(receipt) if receipt.exists() else None,assessment_sha256=digest(receipt) if receipt.exists() else None)
status('running_missing_PVT_campaign',reused_completed_points=1,new_cases=14)
with ThreadPoolExecutor(max_workers=2) as pool:
    pending={pool.submit(run,case):case for case in cases}
    for future in as_completed(pending):
        try:result=future.result()
        except Exception as error:result=dict(pending[future],state='worker_exception',error=repr(error))
        results.append(result);save(out/'case_results.json',results)
        status('running_missing_PVT_campaign',reused_completed_points=1,terminal_new_cases=len(results),new_cases=14)
newly_complete=0
for result in results:
    if result.get('assessment'):
        rr=json.loads(Path(result['assessment']).read_text())
        if rr.get('all_native_waveform_events_terminal') and rr.get('fixtures')==108:newly_complete+=1
for p,sha in pins.items():assert digest(Path(p))==sha,p
save(out/'assessment.json',dict(input_sha256=pins,reused_completed_points=reused,case_results=results,
    required_PVT_points=15,completed_raw_PVT_points=1+newly_complete,
    all_raw_propagation_PVT_points_completed=newly_complete==14,
    fixtures_per_PVT=108,qualified_timing_views=0,sequential_constraints_qualified=False,
    numerical_domain_enclosure_qualified=False,physical_timing_qualified=False,
    release_qualified=False,adopted=False))
status('completed_raw_PVT_campaign' if newly_complete==14 else 'incomplete_raw_PVT_campaign',completed_raw_PVT_points=1+newly_complete)
