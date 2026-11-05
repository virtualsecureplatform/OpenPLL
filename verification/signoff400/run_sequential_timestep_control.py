"""One-parameter sequential max-step controls using compiled streaming assessment."""
import argparse,json,os,time,threading,difflib
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from common import save,sha
from resources import identity,lease
from compiled_charge import execute


def compare(before,after):
    if before['fixtures']!=after['fixtures']:raise ValueError('fixture inventory')
    records=[];changed=unmatched=0;maximum=0
    for a,b in zip(before['records'],after['records'],strict=True):
        if a['case_index']!=b['case_index']:raise ValueError('fixture identity')
        changed+=a['passed']!=b['passed'];deltas={};missing=[]
        for key in ('clock_to_q_rise_ns','clock_to_q_fall_ns','assertion_to_q_ns','output_rise_20_80_ns','output_fall_80_20_ns'):
            x,y=a.get(key),b.get(key)
            if x is None and y is None:continue
            if x is None or y is None or len(x)!=len(y):missing.append(key);continue
            values=[v-u for u,v in zip(x,y)];deltas[key]=values;maximum=max([maximum,*map(abs,values)])
        unmatched+=bool(missing);records.append(dict(case_index=a['case_index'],baseline_passed=a['passed'],control_passed=b['passed'],signed_control_minus_baseline_ns=deltas,unmatched_metrics=missing))
    return dict(fixtures=len(records),changed_fixture_outcomes=changed,fixtures_with_unmatched_metrics=unmatched,maximum_absolute_matched_metric_difference_ns=maximum,records=records)


def run(out):
    out.mkdir(parents=True,exist_ok=False);root=Path.cwd();base=root/'build/signoff400';proof=base/'compiled_sequential_assessor_controls_001/assessment.json';a=json.loads(proof.read_text());controls=proof.parent
    adapter_proof=base/'compiled_sequential_assessor_adapter_controls_002/assessment.json';checked=json.loads(adapter_proof.read_text());worker=root/'verification/timing400/run_sequential_PVT_case_compiled.py';adapter=worker.with_name('assess_compact_sequential_compiled.py');image=root/'build/apptainer/openpll-release-modern.sif';requirements=root/'verification/signoff400/requirements.json'
    if not a['compiled_streaming_sequential_assessor_matches_all_retained_records'] or not checked['compiled_sequential_adapter_matches_retained_108_fixture_TT_records']:raise ValueError('controlled compiled assessment required')
    paths=[proof,adapter_proof,controls/'assess_sequential_waveform',worker,adapter,image,requirements,Path(__file__).resolve()];deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),maximum_case_workers=16,case_address_space_GiB=4,internal_native_threads=1,deadline_uptime=deadline,automatic_identical_retry=False,changed_parameter='maximum timestep 2ps to 1ps only'))
    def status(state,**kw):save(out/'status.json',dict(state=state,release_qualified=False,**kw))
    status('preparing_independent_sequential_timestep_controls');pins={str(p):sha(p) for p in paths}
    for p in (worker,adapter):
        if pins[str(p)]!=checked['input_sha256'][str(p)]:raise ValueError('controlled future adapter or worker changed')
    if pins[str(controls/'assess_sequential_waveform')]!=a['artifacts'][str(controls/'assess_sequential_waveform')]:raise ValueError('compiled parser changed')
    cases=[];points=set();spec=json.loads(requirements.read_text());expected={(k,t,1.8) for k in spec['corners'] for t in spec['temperatures_c']}
    for name,digest in a['input_sha256'].items():
        if not name.endswith('/assessment.json'):continue
        receipt=Path(name);before=json.loads(receipt.read_text())
        if before.get('fixtures')!=108:continue
        if sha(receipt)!=digest:raise ValueError('baseline native receipt changed')
        plan_path=receipt.parent.parent/'plan.json';p=json.loads(plan_path.read_text());pvt=p['pvt'];point=(pvt['corner'],pvt['temperature_c'],pvt['supply_v'])
        if point in points or point not in expected:raise ValueError('unique required PVT')
        points.add(point);deck=plan_path.parent/'batch.cir'
        for path in (receipt,plan_path,deck):pins[str(path)]=sha(path)
        if pins[str(plan_path)]!=a['input_sha256'][str(plan_path)] or pins[str(deck)]!=p['input_sha256'][str(deck)]:raise ValueError('baseline native deck lineage')
        source=deck.read_text()
        if source.count('.tran 2p 64n 0 2p\n')!=1:raise ValueError('known baseline max step')
        text=source.replace('.tran 2p 64n 0 2p\n','.tran 2p 64n 0 1p\n')
        if text.replace('.tran 2p 64n 0 1p\n','.tran 2p 64n 0 2p\n')!=source:raise ValueError('one-parameter deck change')
        label=point[0]+'_'+str(point[1]);where=out/label;where.mkdir();new=where/'batch.cir';new.write_text(text);(where/'maximum_step_only.patch').write_text(''.join(difflib.unified_diff(source.splitlines(True),text.splitlines(True),fromfile='baseline_2ps',tofile='control_1ps')))
        # New native jobs bind model/engine bytes from the historical plan and
        # explicit current control inputs, rather than its mutable release manifest.
        models={n:h for n,h in p['input_sha256'].items() if n.startswith('/opt/pdk/') or n=='/opt/xyce/bin/Xyce' or Path(n).suffix in ('.spice','.pm3','.mod','.lib')}
        p.update(input_sha256={**models,**{str(path):pins[str(path)] for path in paths},str(receipt):pins[str(receipt)],str(plan_path):pins[str(plan_path)],str(new):sha(new)},reference_plan=str(plan_path),deadline_uptime=deadline,max_step_ps=1,independent_control='maximum_step_only',baseline_assessment=str(receipt),historical_mutable_release_manifest_reused=False)
        target=where/'plan.json';save(target,p);cases.append((label,target,receipt,pvt))
    if points!=expected or len(cases)!=15:raise ValueError('complete 15-point baseline required')
    save(out/'plan.json',dict(input_sha256=pins,cases=[dict(label=l,plan=str(p),baseline_assessment=str(r),PVT=v) for l,p,r,v in cases],baseline_maximum_step_ps=2,control_maximum_step_ps=1,all_other_deck_tokens_identical=True,historical_native_model_and_engine_hashes_checked_in_each_native_worker=True,release_qualified=False))
    done=[];lock=threading.Lock()
    def task(case):
        label,plan,prior,pvt=case
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,'/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',worker,'--plan',plan,'--assessor-controls',controls],plan.parent/'worker.log',deadline,4)
        receipt=plan.parent/'run_001/assessment.json';raw=json.loads(receipt.read_text())
        if raw['pvt']!=pvt or not raw['compiled_streaming_sequential_assessor_used']:raise ValueError('matching compiled PVT assessment required')
        comparison=plan.parent/'numerical_comparison.json';delta=compare(json.loads(prior.read_text()),raw);save(comparison,delta)
        result=dict(label=label,assessment=str(receipt),assessment_sha256=sha(receipt),comparison=str(comparison),comparison_sha256=sha(comparison),passing=raw['passing'],**{k:delta[k] for k in ('fixtures','changed_fixture_outcomes','fixtures_with_unmatched_metrics','maximum_absolute_matched_metric_difference_ns')})
        with lock:done.append(result);save(out/'case_results.json',done);status('sequential_timestep_controls_running',completed_points=len(done),required_points=15)
        return result
    status('sequential_timestep_controls_running',completed_points=0,required_points=15)
    try:
        with ThreadPoolExecutor(max_workers=16) as pool:results=[f.result() for f in as_completed([pool.submit(task,c) for c in cases])]
        if any(sha(Path(n))!=h for n,h in pins.items()):raise ValueError('control input changed')
        save(out/'assessment.json',dict(input_sha256=pins,case_results=results,all_15_sequential_timestep_controls_terminal=len(results)==15,fixtures_per_PVT=108,total_fixture_comparisons=1620,changed_fixture_outcomes=sum(r['changed_fixture_outcomes'] for r in results),fixtures_with_unmatched_metrics=sum(r['fixtures_with_unmatched_metrics'] for r in results),maximum_absolute_matched_metric_difference_ns=max(r['maximum_absolute_matched_metric_difference_ns'] for r in results),compiled_streaming_assessor_used_for_every_case=True,all_other_deck_tokens_identical=True,numerical_domain_enclosure_qualified=False,setup_hold_recovery_removal_qualified=False,physical_timing_qualified=False,release_qualified=False));status('all_15_sequential_timestep_controls_terminal')
    except BaseException as e:
        status('stopped_without_promotion',reason=repr(e),completed_points=len(done));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
