#!/usr/bin/env python3
"""Review refined observations and repeated controls; qualify no timing limits."""
from collections import defaultdict
from datetime import datetime,timezone
import json
import math
import os
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process


def key(case):return case['master'],case['kind'],case['offset_ps']


def main():
    root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
    folder=base/'capture_aperture_refinement_fs125_001';run=folder/'run_002';plan_path=folder/'plan.json'
    plan=json.loads(plan_path.read_text());deadline=plan['shared_deadline_uptime']
    reservation=base/'capture_aperture_priority_reservation_001'
    reserved=json.loads((reservation/'owner.json').read_text());handoff_path=reservation/'handoff.json'
    handoff=json.loads(handoff_path.read_text());assert handoff['prior_native_cases_started']==0
    assert handoff['replacement_output']==str(run) and handoff['native_case_retried'] is False
    out=base/'capture_aperture_refinement_review_001';out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        reservation_runner_pid=reserved['runner_pid'],deadline_uptime=deadline,native_started_stopped_or_retried=False))
    receipt_path=run/'assessment.json'
    while not receipt_path.exists():
        identity=process(reserved['runner_pid'])
        if not identity['live'] or time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
            save(out/'status.json',dict(state='source_incomplete_or_deadline',reservation_runner=identity,release_qualified=False));return
        assert any(arg.endswith('reserve_capture_aperture_refinement.py') for arg in identity['argv'])
        save(out/'status.json',dict(state='waiting_for_terminal_capture_refinement',deadline_uptime=deadline,release_qualified=False))
        time.sleep(min(5,max(.01,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    report=json.loads(receipt_path.read_text())
    assert report['all_native_waveform_events_terminal'] and report['fixtures']==90 and report['separated_controls']==36
    assert report['pvt']==plan['pvt']
    original=base/'compact_capture_boundaries_fs125_001'
    old_plan_path=original/'plan.json';old_receipt_path=original/'run_001/assessment.json'
    baseline_review=base/'capture_boundaries_fs125_review_001/assessment.json'
    reviewed=json.loads(baseline_review.read_text())
    for p in (old_plan_path,old_receipt_path):assert digest(p)==reviewed['input_sha256'][str(p)]
    old_plan=json.loads(old_plan_path.read_text());old=json.loads(old_receipt_path.read_text())
    assert old['observation_integrity_passing']==198 and old['pvt']==plan['pvt']
    pins={str(p):digest(p) for p in (Path(__file__).resolve(),plan_path,receipt_path,handoff_path,
        old_plan_path,old_receipt_path,baseline_review)}
    for path,sha in report['artifacts'].items():
        assert digest(Path(path))==sha,path
        pins[path]=sha
    previous={key(c):(c,r) for c,r in zip(old_plan['fixtures'],old['records'],strict=True)}
    assert len(previous)==198
    merged={k:dict(case=c,observed=r,source='original') for k,(c,r) in previous.items()}
    controls=[];new_points=[];invalid=[]
    same_fields=('master','kind','offset_ps','ports','control_pin','reset_value','clock_center_ns','changing_input_center_ns',
        'clock','data','control','pretest_value','changed_value','sentinel','sentinel_expected_final_value',
        'full_clock_ramp_ps','full_changing_input_ramp_ps','external_load_pf')
    for index,(c,r) in enumerate(zip(plan['fixtures'],report['records'],strict=True)):
        assert r['case_index']==index
        if not r['observation_integrity_passed']:
            invalid.append(dict(case_index=index,fixture=c,observation=r));continue
        k=key(c)
        if c['purpose']=='separated_batch_control':
            oc,orr=previous[k];assert c['sentinel'] and all(c[f]==oc[f] for f in same_fields)
            diff={};missing=[]
            for direction in ('rising','falling'):
                a,b=orr['post_test_50percent_edges_ns'][direction],r['post_test_50percent_edges_ns'][direction]
                if len(a)==len(b):diff[direction]=[(y-x)*1000 for x,y in zip(a,b)]
                else:missing.append(dict(direction=direction,original_edges_ns=a,repeat_edges_ns=b))
            controls.append(dict(master=c['master'],kind=c['kind'],offset_ps=c['offset_ps'],
                original_outcome=orr['outcome'],repeated_outcome=r['outcome'],outcome_matches=orr['outcome']==r['outcome'],
                sentinel_passed=r.get('sentinel_passed',False),signed_edge_differences_ps=diff,unmatched_edges=missing))
        else:
            assert c['purpose']=='new_interior_sample' and k not in previous and k not in merged
            bracket=c['source_bracket'];assert bracket['left_ps']<c['offset_ps']<bracket['right_ps']
            merged[k]=dict(case=c,observed=r,source='refinement');new_points.append(k)
    groups=defaultdict(list)
    for (master,kind,offset),item in merged.items():groups[master,kind].append(item)
    summaries=[]
    for (master,kind),items in sorted(groups.items()):
        items.sort(key=lambda item:item['case']['offset_ps']);brackets=[]
        for left,right in zip(items,items[1:]):
            if left['observed']['outcome']!=right['observed']['outcome']:
                a,b=left['case']['offset_ps'],right['case']['offset_ps']
                brackets.append(dict(left_ps=a,right_ps=b,width_ps=b-a,left_outcome=left['observed']['outcome'],right_outcome=right['observed']['outcome']))
        reference=next(item for item in items if item['case']['offset_ps']==-1000)
        direction='rising' if reference['case']['changed_value'] else 'falling'
        ref_edges=reference['observed']['post_test_50percent_edges_ns'][direction]
        assert len(ref_edges)==1
        reference_delay=(ref_edges[0]-reference['case']['clock_center_ns'])*1000
        samples=[]
        for item in items:
            c,r=item['case'],item['observed'];edges=r['post_test_50percent_edges_ns'];delay=None
            if r['outcome']=='changed_value' and sum(map(len,edges.values()))==1 and len(edges[direction])==1:
                delay=(edges[direction][0]-c['clock_center_ns'])*1000
            samples.append(dict(input_minus_clock_ps=c['offset_ps'],source=item['source'],outcome=r['outcome'],
                output_edge_minus_clock_ps=delay,delay_change_from_original_separated_control_ps=None if delay is None else delay-reference_delay,
                raw_post_test_edges_ns=edges))
        summaries.append(dict(master=master,kind=kind,observations=samples,observed_transition_brackets=brackets,
            reference_separated_delay_ps=reference_delay,monotonicity_between_samples_proven=False))
    assert len(groups)==18
    for p,sha in pins.items():assert digest(Path(p))==sha,p
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    save(out/'assessment.json',dict(input_sha256=pins,pvt=plan['pvt'],repeated_controls=controls,
        valid_repeated_controls=len(controls),matching_control_outcomes=sum(c['outcome_matches'] for c in controls),
        unmatched_control_edges=[c for c in controls if c['unmatched_edges']],invalid_observations=invalid,
        valid_new_interior_samples=len(new_points),merged_unique_samples=len(merged),groups=summaries,
        source_observation_integrity_passing=report['observation_integrity_passing'],
        source_separated_controls_passing=report['separated_controls_passing'],
        source_inputs_independently_reaudited_here=False,producer_input_hash_checks_consumed=True,raw_artifacts_revalidated=True,
        comparison_acceptance_threshold_selected=False,delay_degradation_threshold_selected=False,
        numerical_domain_enclosure_qualified=False,setup_hold_recovery_removal_qualified=False,
        metastability_or_MTBF_qualified=False,release_qualified=False,adopted=False,
        scope='Sparse FS125 observations only. Retain ambiguous/non-monotonic outcomes, cross-batch control differences, all sampled brackets and delay degradation. No safe constraint, interval monotonicity or physical uncertainty enclosure is inferred.'))
    save(out/'status.json',dict(state='completed_capture_refinement_review',release_qualified=False))


if __name__=='__main__':main()
