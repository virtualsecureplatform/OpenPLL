"""Independent one-parameter timestep controls, assessed by the compiled parser."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import difflib
import json
import os
from pathlib import Path
import threading
import time
from common import save,sha
from compiled_charge import execute
from resources import identity,lease


def compare(left,right):
    if left['fixtures']!=right['fixtures'] or len(left['records'])!=len(right['records']):raise ValueError('matching fixture inventories required')
    rows=[];maximum=0;changed=0;unmatched=0
    for a,b in zip(left['records'],right['records']):
        if a['case_index']!=b['case_index']:raise ValueError('matching fixture identity required')
        status_changed=any(a[k]!=b[k] for k in ('passed','strict_output_slew_passed'));changed+=status_changed
        delta={};missing=[]
        for field in ('input_rise_delay_ns','input_fall_delay_ns','output_rise_slew_ns','output_fall_slew_ns'):
            x,y=a.get(field),b.get(field)
            if x is None or y is None or len(x)!=len(y):missing.append(field);continue
            values=[v-u for u,v in zip(x,y)];delta[field]=values
            maximum=max([maximum,*map(abs,values)])
        unmatched+=bool(missing)
        rows.append(dict(case_index=a['case_index'],baseline_passed=a['passed'],control_passed=b['passed'],
             baseline_strict_slew_passed=a['strict_output_slew_passed'],control_strict_slew_passed=b['strict_output_slew_passed'],
             signed_control_minus_baseline_ns=delta,unmatched_metrics=missing))
    return dict(fixtures=len(rows),changed_fixture_outcomes=changed,fixtures_with_unmatched_metrics=unmatched,
                maximum_absolute_matched_metric_difference_ns=maximum,records=rows)


def run(output):
    output.mkdir(parents=True,exist_ok=False);root=Path.cwd()
    baseline=root/'build/signoff400/startup_timing_mux2_4_15PVT_raw_001/assessment.json'
    controls=root/'build/signoff400/compiled_propagation_assessor_controls_002'
    adapter_controls=root/'build/signoff400/compiled_propagation_assessor_adapter_controls_001/assessment.json'
    worker=root/'verification/timing400/run_mux2_4_PVT_case_compiled.py';adapter=worker.with_name('assess_compact_propagation_compiled.py')
    image=root/'build/apptainer/openpll-release-modern.sif';requirements=root/'verification/signoff400/requirements.json'
    a=json.loads(baseline.read_text());c=json.loads((controls/'assessment.json').read_text());checked=json.loads(adapter_controls.read_text())
    if a['completed_raw_PVT_points']!=15 or not a['all_raw_fixture_events_pass']:raise ValueError('complete baseline required')
    if not c['compiled_streaming_assessor_matches_retained_python_records'] or not checked['compiled_adapter_exactly_matches_retained_54_fixture_assessment']:raise ValueError('controlled streaming assessment required')
    paths=[baseline,controls/'assessment.json',controls/'assess_propagation_waveform',adapter_controls,worker,adapter,image,requirements,Path(__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,wall_limit_s=43200,
         maximum_case_workers=8,internal_native_threads=1,case_address_space_limit_GiB=4,automatic_identical_retry=False,
         changed_parameter='maximum timestep 2ps to 1ps only'))
    def status(state,**more):save(output/'status.json',dict(state=state,release_qualified=False,**more))
    status('preparing_independent_timestep_only_controls')
    pins={str(p):sha(p) for p in paths}
    if pins[str(controls/'assess_propagation_waveform')]!=c['artifacts'][str(controls/'assess_propagation_waveform')]:raise ValueError('controlled binary changed')
    for path in (worker,adapter):
        if pins[str(path)]!=checked['input_sha256'][str(path)]:raise ValueError('controlled adapter or future worker changed')
    cases=[]
    for case in a['case_results']:
        receipt=Path(case['assessment']);folder=receipt.parent.parent;plan_path=folder/'plan.json';deck=folder/'batch.cir'
        if sha(receipt)!=case['assessment_sha256']:raise ValueError('baseline case receipt changed')
        plan=json.loads(plan_path.read_text());source=deck.read_text()
        if source.count('.tran 2p 34n 0 2p\n')!=1:raise ValueError('known baseline timestep required')
        text=source.replace('.tran 2p 34n 0 2p\n','.tran 2p 34n 0 1p\n')
        if text.replace('.tran 2p 34n 0 1p\n','.tran 2p 34n 0 2p\n')!=source:raise ValueError('single-parameter stimulus identity')
        where=output/case['label'];where.mkdir();new_deck=where/'batch.cir';new_deck.write_text(text)
        (where/'timestep_only.patch').write_text(''.join(difflib.unified_diff(source.splitlines(True),text.splitlines(True),fromfile='baseline_2ps',tofile='control_1ps')))
        for path in (receipt,plan_path,deck):pins[str(path)]=sha(path)
        plan['input_sha256']={**plan['input_sha256'],**{str(p):sha(p) for p in paths},str(receipt):sha(receipt),str(plan_path):sha(plan_path),str(new_deck):sha(new_deck)}
        plan.update(deadline_uptime=deadline,independent_control='maximum_step_only',maximum_step_ps=1,baseline_plan=str(plan_path),baseline_assessment=str(receipt))
        target=where/'plan.json';save(target,plan);cases.append((case['label'],target,receipt))
    save(output/'plan.json',dict(input_sha256=pins,cases=[dict(label=l,plan=str(p),baseline_assessment=str(r)) for l,p,r in cases],
         baseline_maximum_step_ps=2,control_maximum_step_ps=1,all_stimuli_and_other_solver_parameters_unchanged=True,
         numerical_uncertainty_acceptance_threshold_selected=False,physical_timing_qualified=False,release_qualified=False))
    python='/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3';done=[];lock=threading.Lock()
    def task(case):
        label,plan,prior=case
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,python,worker,'--plan',plan,'--assessor-controls',controls],plan.parent/'worker.log',deadline,4)
        receipt=plan.parent/'run_001/assessment.json';raw=json.loads(receipt.read_text());before=json.loads(prior.read_text())
        if not raw['compiled_streaming_assessor_used'] or raw['pvt']!=before['pvt']:raise ValueError('matching compiled PVT observation required')
        differences=compare(before,raw);comparison=plan.parent/'numerical_comparison.json';save(comparison,differences)
        result=dict(label=label,assessment=str(receipt),assessment_sha256=sha(receipt),passing=raw['passing'],strict_output_slew_passing=raw['strict_output_slew_passing'],
             comparison=str(comparison),comparison_sha256=sha(comparison),changed_fixture_outcomes=differences['changed_fixture_outcomes'],
             fixtures_with_unmatched_metrics=differences['fixtures_with_unmatched_metrics'],maximum_absolute_matched_metric_difference_ns=differences['maximum_absolute_matched_metric_difference_ns'])
        with lock:
            done.append(result);save(output/'case_results.json',done);status('independent_timestep_controls_running',completed_points=len(done),required_points=15)
        return result
    status('independent_timestep_controls_running',completed_points=0,required_points=15)
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:results=[f.result() for f in as_completed([pool.submit(task,case) for case in cases])]
        if any(sha(Path(name))!=digest for name,digest in pins.items()):raise ValueError('source changed during timestep controls')
        save(output/'assessment.json',dict(input_sha256=pins,case_results=results,all_15_independent_timestep_controls_terminal=len(results)==15,
             compiled_streaming_assessor_used_for_every_case=True,all_stimuli_and_other_solver_parameters_unchanged=True,
             changed_fixture_outcomes=sum(r['changed_fixture_outcomes'] for r in results),fixtures_with_unmatched_metrics=sum(r['fixtures_with_unmatched_metrics'] for r in results),
             maximum_absolute_matched_metric_difference_ns=max(r['maximum_absolute_matched_metric_difference_ns'] for r in results),
             numerical_uncertainty_acceptance_threshold_selected=False,numerical_domain_enclosure_qualified=False,physical_timing_qualified=False,release_qualified=False))
        status('all_15_independent_timestep_controls_terminal',completed_points=len(results))
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error),completed_points=len(done));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
