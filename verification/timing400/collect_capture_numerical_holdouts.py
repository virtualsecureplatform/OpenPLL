#!/usr/bin/env python3
"""Retain all selected capture-control differences; choose no uncertainty bound."""
from collections import defaultdict
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process


def compare(label,index,case,left,right):
    record=dict(control=label,case_index=index,master=case['master'],kind=case['kind'],input_minus_clock_ps=case['offset_ps'],
        observations_comparable=False,left_observation=left,right_observation=right)
    if not left.get('observation_integrity_passed') or not right.get('observation_integrity_passed'):
        record['reason']='One source observation failed integrity; retain without assigning edge error';return record
    record.update(observations_comparable=True,left_outcome=left['outcome'],right_outcome=right['outcome'],
        outcome_matches=left['outcome']==right['outcome'],
        signed_measured_input_offset_difference_ps=right['observed_input_minus_clock_ps']-left['observed_input_minus_clock_ps'])
    differences={};unmatched=[]
    for direction in ('rising','falling'):
        a,b=left['post_test_50percent_edges_ns'][direction],right['post_test_50percent_edges_ns'][direction]
        if len(a)==len(b):differences[direction]=[(y-x)*1000 for x,y in zip(a,b)]
        else:unmatched.append(dict(direction=direction,left_edges_ns=a,right_edges_ns=b))
    record.update(signed_matched_edge_differences_ps=differences,unmatched_events=unmatched)
    return record


def main():
    root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
    source=base/'capture_numerical_holdouts_fs125_001';owner_path=source/'owner.json';owner=json.loads(owner_path.read_text())
    deadline=owner['deadline_uptime'];pid=owner['runner_pid'];out=base/'capture_numerical_holdout_comparison_001';out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),source_runner_pid=pid,started_utc=datetime.now(timezone.utc).isoformat(),
        deadline_uptime=deadline,native_started_stopped_or_retried=False))
    terminal=source/'assessment.json'
    while not terminal.exists():
        identity=process(pid)
        if not identity['live'] or time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
            save(out/'status.json',dict(state='source_incomplete_or_deadline',source_runner=identity,release_qualified=False));return
        assert any(arg.endswith('run_capture_numerical_holdouts.py') for arg in identity['argv'])
        save(out/'status.json',dict(state='waiting_for_terminal_capture_numerical_controls',deadline_uptime=deadline,release_qualified=False))
        time.sleep(min(5,max(.01,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    result=json.loads(terminal.read_text());cases=result['cases']
    if not result['all_controls_have_terminal_receipts']:
        save(out/'assessment.json',dict(source_cases=cases,selected_controls_complete=False,release_qualified=False));return
    proof=base/'capture_numerical_holdout_preparation_checks_001/assessment.json'
    assert json.loads(proof.read_text())['synthetic_separated_controls_passing']==36
    pins={str(p):digest(p) for p in (Path(__file__).resolve(),terminal,owner_path,source/'plan.json',proof)}
    data={}
    for c in cases:
        p,r=Path(c['plan']),Path(c['assessment']);assert digest(p)==c['plan_sha256'] and digest(r)==c['assessment_sha256']
        plan,report=json.loads(p.read_text()),json.loads(r.read_text())
        assert report['fixtures']==72 and report['all_native_waveform_events_terminal'] and report['separated_controls']==36
        assert report['independent_control']==plan['independent_control']==c['label']
        assert report['pvt']==plan['pvt']==dict(corner='fs',temperature_c=125,supply_v=1.8)
        for path,sha in report['artifacts'].items():assert digest(Path(path))==sha,path;pins[path]=sha
        pins[str(p)]=digest(p);pins[str(r)]=digest(r);data[c['label']]=(plan,report)
    baseline_plan,baseline=data['subset_baseline'];comparisons=[];cached={}
    for index,case in enumerate(baseline_plan['fixtures']):
        path=Path(case['source_receipt'])
        if str(path) not in cached:cached[str(path)]=json.loads(path.read_text());pins[str(path)]=digest(path)
        previous=cached[str(path)]['records'][case['source_case_index']]
        assert previous['case_index']==case['source_case_index']
        comparisons.append(compare('subset_context_and_print_precision_vs_prior_batch',index,case,previous,baseline['records'][index]))
        for label,(plan,report) in data.items():
            assert plan['fixtures']==baseline_plan['fixtures'] and plan['output_precision']==16
            if label=='subset_baseline':continue
            assert report['records'][index]['case_index']==index
            comparisons.append(compare(label,index,case,baseline['records'][index],report['records'][index]))
    summaries=[]
    for label in sorted({c['control'] for c in comparisons}):
        rows=[r for r in comparisons if r['control']==label];valid=[r for r in rows if r['observations_comparable']]
        errors=[abs(v) for r in valid for values in r['signed_matched_edge_differences_ps'].values() for v in values]
        summaries.append(dict(control=label,fixtures=len(rows),comparable_observations=len(valid),
            outcome_changes=[r['case_index'] for r in valid if not r['outcome_matches']],
            unmatched_event_cases=[r['case_index'] for r in valid if r['unmatched_events']],
            invalid_observation_cases=[r['case_index'] for r in rows if not r['observations_comparable']],
            maximum_matched_edge_difference_ps=max(errors) if errors else None))
    for p,sha in pins.items():assert digest(Path(p))==sha,p
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    save(out/'comparisons.json',comparisons)
    save(out/'assessment.json',dict(input_sha256=pins,selected_controls_complete=True,summaries=summaries,
        observation_integrity_passes={label:r['observation_integrity_passing'] for label,(_,r) in data.items()},
        separated_control_passes={label:r['separated_controls_passing'] for label,(_,r) in data.items()},
        source_inputs_independently_reaudited_here=False,producer_input_checks_consumed=True,raw_artifacts_revalidated=True,
        subset_reference_comparison_includes_print_precision=True,numerical_uncertainty_acceptance_threshold_selected=False,
        numerical_domain_enclosure_qualified=False,setup_hold_recovery_removal_qualified=False,
        physical_timing_qualified=False,release_qualified=False,adopted=False,
        scope='Selected72 FS125 fixtures only. Retain all changed outcomes, unmatched events, failed observations and signed edge differences. Do not infer safe constraints or unmeasured slew/load/PVT bounds.'))
    save(out/'status.json',dict(state='completed_capture_numerical_control_comparison',release_qualified=False))


if __name__=='__main__':main()
