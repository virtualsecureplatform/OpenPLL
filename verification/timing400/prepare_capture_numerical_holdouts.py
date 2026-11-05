#!/usr/bin/env python3
"""Freeze independent numerical controls at observed capture brackets."""
from copy import deepcopy
from datetime import datetime,timezone
import difflib
import json
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest,save
from characterize_compact_propagation import SUPPLIES
from prepare_compact_capture_boundaries import pwl

root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
review_path=base/'capture_aperture_refinement_review_001/assessment.json';review=json.loads(review_path.read_text())
assert review['source_observation_integrity_passing']==90 and review['matching_control_outcomes']==36
assert not review['invalid_observations'] and not review['unmatched_control_edges']
for p,sha in review['input_sha256'].items():assert digest(Path(p))==sha,p
old=base/'compact_capture_boundaries_fs125_001';recent=base/'capture_aperture_refinement_fs125_001'
old_plan_path=old/'plan.json';new_plan_path=recent/'plan.json';old_plan=json.loads(old_plan_path.read_text());new_plan=json.loads(new_plan_path.read_text())
deadline=new_plan['shared_deadline_uptime'];assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
source_cases={}
for plan_path,receipt_path in [(old_plan_path,old/'run_001/assessment.json'),(new_plan_path,recent/'run_002/assessment.json')]:
    plan=json.loads(plan_path.read_text())
    for index,c in enumerate(plan['fixtures']):source_cases[c['master'],c['kind'],c['offset_ps']]=(c,plan_path,receipt_path,index)
cases=[]
for group in review['groups']:
    assert len(group['observed_transition_brackets'])==1
    bracket=group['observed_transition_brackets'][0]
    for offset in sorted({-1000,1000,bracket['left_ps'],bracket['right_ps']}):
        c,plan_path,receipt_path,index=source_cases[group['master'],group['kind'],offset]
        case=deepcopy(c);case.update(purpose='numerical_boundary_holdout',source_plan=str(plan_path),source_receipt=str(receipt_path),source_case_index=index)
        cases.append(case)
assert len(cases)==72 and sum(c['sentinel'] for c in cases)==36
pins=dict(new_plan['input_sha256'])
for p in (Path(__file__).resolve(),review_path,old_plan_path,new_plan_path,old/'run_001/assessment.json',recent/'run_002/assessment.json',recent/'batch.cir'):
    pins[str(p)]=digest(p)
for p,sha in pins.items():assert digest(Path(p))==sha,p
text=(recent/'batch.cir').read_text();prefix=text[:text.index('VCLK_0 ')]
assert prefix.count('.options timeint reltol=1e-5 abstol=1e-10')==1
out=base/'capture_numerical_holdouts_fs125_001';out.mkdir(exist_ok=False)
profiles=[('subset_baseline',2,'1e-5','1e-10'),('timestep_only',1,'1e-5','1e-10'),
    ('relative_tolerance_only',2,'1e-6','1e-10'),('absolute_tolerance_only',2,'1e-5','1e-11')]
prepared=[];baseline=None
for label,step,rel,absolute in profiles:
    folder=out/label;folder.mkdir()
    lines=prefix.replace('.options timeint reltol=1e-5 abstol=1e-10',f'.options timeint reltol={rel} abstol={absolute}').splitlines()
    columns=[]
    for index,c in enumerate(cases):
        aliases={**SUPPLIES,'CLK':f'CLK_{index}','D':f'D_{index}','Q':f'Q_{index}',c['control_pin']:f'R_{index}'}
        for channel,points in [('CLK',c['clock']),('D',c['data']),('R',c['control'])]:lines.append(f'V{channel}_{index} {channel}_{index} 0 '+pwl(points))
        lines.extend([f'XDUT_{index} '+' '.join(aliases[p] for p in c['ports'])+' '+c['master'],f'CLOAD_{index} Q_{index} 0 5f'])
        columns.extend(f'V({name}_{index})' for name in ('CLK','D','R','Q'))
    lines.extend([f'.tran 2p 28n 0 {step}p','.print tran FORMAT=STD PRECISION=16 '+' '.join(columns),'.end'])
    circuit='\n'.join(lines)+'\n';deck=folder/'batch.cir';deck.write_text(circuit)
    if baseline is None:baseline=lines
    else:
        changed=[(a,b) for a,b in zip(baseline,lines,strict=True) if a!=b];assert len(changed)==1
        assert changed[0][0].startswith('.tran ' if label=='timestep_only' else '.options timeint ')
        (folder/'single_parameter.patch').write_text(''.join(difflib.unified_diff([x+'\n' for x in baseline],[x+'\n' for x in lines],fromfile='subset_baseline',tofile=label)))
    plan_path=folder/'plan.json';save(plan_path,dict(input_sha256={**pins,str(deck):digest(deck)},fixtures=cases,waveform_columns=columns,
        pvt=new_plan['pvt'],stop_ns=28,max_step_ps=step,reltol=float(rel),abstol=float(absolute),output_precision=16,
        independent_control=label,shared_deadline_uptime=deadline,inherited_campaign_owner=new_plan['inherited_campaign_owner'],
        budget_restarted=False,original_batch_comparison_includes_context_and_print_precision=True,
        setup_hold_recovery_removal_qualified=False,release_qualified=False))
    prepared.append(dict(label=label,plan=str(plan_path),plan_sha256=digest(plan_path)))
save(out/'plan.json',dict(input_sha256=pins,cases=prepared,fixtures_per_case=72,separated_controls_per_case=36,
    shared_deadline_uptime=deadline,inherited_campaign_owner=new_plan['inherited_campaign_owner'],prepared_utc=datetime.now(timezone.utc).isoformat(),
    budget_restarted=False,maximum_case_workers=1,maximum_native_workers=4,automatic_identical_retry=False,
    baseline_required_before_numerical_controls=True,native_started=False,release_qualified=False))
print('Prepared4 independent capture controls, 72 fixtures each, with inherited deadline')
