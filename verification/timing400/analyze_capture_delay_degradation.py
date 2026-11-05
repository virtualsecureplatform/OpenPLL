#!/usr/bin/env python3
"""Measure delay degradation in retained sparse captures; choose no limit."""
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
from compile_local_C_operators_v2 import digest,save

root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
source=base/'completed_capture_aperture_analysis_001/assessment.json'
analysis=json.loads(source.read_text())
for p,sha in analysis['input_sha256'].items():assert digest(Path(p))==sha,p
pins={**analysis['input_sha256'],str(source):digest(source),str(Path(__file__).resolve()):digest(Path(__file__).resolve())}
assert analysis['fixtures']==198 and not analysis['delay_degradation_acceptance_criterion_selected']
plan=json.loads((base/'compact_capture_boundaries_fs125_001/plan.json').read_text())
groups=defaultdict(list)
for observed in analysis['observations']:
    fixture=plan['fixtures'][observed['case_index']]
    assert (fixture['master'],fixture['kind'],fixture['offset_ps'])==(observed['master'],observed['kind'],observed['input_minus_clock_ps'])
    groups[fixture['master'],fixture['kind']].append((fixture,observed))
records=[];summaries=[]
for (master,kind),items in sorted(groups.items()):
    baseline=[(c,r) for c,r in items if c['offset_ps']==-1000]
    assert len(baseline)==1
    c,r=baseline[0];direction='rising' if c['changed_value'] else 'falling'
    assert c['sentinel'] and r['outcome']=='changed_value' and r['post_test_output_edge_count']==1
    assert len(r['output_edge_minus_clock_ps'][direction])==1
    reference=r['output_edge_minus_clock_ps'][direction][0]
    assert reference>0 and math.isfinite(reference)
    selected=[]
    for case,row in items:
        record=dict(case_index=row['case_index'],master=master,kind=kind,
            input_minus_clock_ps=case['offset_ps'],outcome=row['outcome'],reference_delay_ps=reference,
            reference_case_index=r['case_index'],delay_comparable=False)
        edges=row['output_edge_minus_clock_ps'][direction]
        if row['outcome']=='changed_value' and row['post_test_output_edge_count']==1 and len(edges)==1:
            delay=edges[0];assert math.isfinite(delay)
            record.update(delay_comparable=True,output_edge_minus_clock_ps=delay,
                delay_change_ps=delay-reference,delay_ratio=delay/reference)
            selected.append(record)
        else:
            record['exclusion']='No unique expected-direction edge with changed final value; retain outcome without assigning delay'
        records.append(record)
    worst=max(selected,key=lambda row:row['delay_change_ps'])
    summaries.append(dict(master=master,kind=kind,comparable_samples=len(selected),
        reference_delay_ps=reference,maximum_observed_delay_change_ps=worst['delay_change_ps'],
        maximum_observed_delay_ratio=worst['delay_ratio'],worst_sample_case_index=worst['case_index'],
        worst_sample_input_minus_clock_ps=worst['input_minus_clock_ps']))
assert len(summaries)==18 and len(records)==198
for p,sha in pins.items():assert digest(Path(p))==sha,p
out=base/'capture_delay_degradation_fs125_001';out.mkdir(exist_ok=False)
with (out/'observations.csv').open('x',newline='') as stream:
    fields=['case_index','master','kind','input_minus_clock_ps','outcome','reference_case_index','reference_delay_ps','delay_comparable','output_edge_minus_clock_ps','delay_change_ps','delay_ratio','exclusion']
    writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(records)
save(out/'assessment.json',dict(input_sha256=pins,pvt=analysis['pvt'],summaries=summaries,records=records,
    full_clock_ramp_ps=200,full_changing_input_ramp_ps=200,external_load_pf=.005,
    numerical_uncertainty_qualified=False,delay_degradation_acceptance_criterion_selected=False,
    monotonicity_between_offsets_proven=False,setup_hold_recovery_removal_qualified=False,
    release_qualified=False,adopted=False,native_jobs_started=0,
    next='Include output-delay degradation alongside final logic outcome when interpreting the queued boundary refinement. Numerical holdouts and slew/load/PVT coverage remain required.',
    scope='Observed signed clock-to-Q differences at existing sparse FS125 points, using the -1000 ps separated sample per cell/input kind. This is not an asymptotic nominal-delay proof, safe constraint or interpolation bound.'))
print(json.dumps(max(summaries,key=lambda row:row['maximum_observed_delay_change_ps'])))
