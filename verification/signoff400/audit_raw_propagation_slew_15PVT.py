"""Reassess retained raw combinational waves with strict threshold semantics."""
import argparse,json,os,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from common import save,sha
from resources import lease,identity
from compiled_charge import execute
from test_compiled_propagation_assessor import equal


def run(out):
    out.mkdir(parents=True,exist_ok=False);root=Path.cwd();base=root/'build/signoff400'
    coverage=base/'startup_timing_characterization_coverage_002/assessment.json';c=json.loads(coverage.read_text());masters=coverage.parent/'master_coverage.json';counts=json.loads(masters.read_text())
    control=base/'compiled_propagation_assessor_controls_002/assessment.json';a=json.loads(control.read_text());binary=control.parent/'assess_propagation_waveform'
    requirements=root/'verification/signoff400/requirements.json';spec=json.loads(requirements.read_text());expected={(k,t,1.8) for k in spec['corners'] for t in spec['temperatures_c']}
    paths=[coverage,masters,control,binary,requirements,Path(__file__).resolve(),root/'verification/signoff400/test_compiled_propagation_assessor.py'];datasets=[];seen=set()
    for name,digest in c['input_sha256'].items():
        if not name.endswith('/assessment.json') or 'compact' not in name or 'sequential' in name:continue
        receipt=Path(name);r=json.loads(receipt.read_text())
        if r.get('fixtures')!=891:continue
        if sha(receipt)!=digest:raise ValueError('coverage receipt changed')
        plan=receipt.parent.parent/'plan.json' if receipt.parent.name=='run_001' else receipt.parent/'plan.json';p=json.loads(plan.read_text())
        point=(p['pvt']['corner'],p['pvt']['temperature_c'],p['pvt']['supply_v'])
        if point in seen or point not in expected:raise ValueError('PVT inventory mismatch')
        seen.add(point);waves=[Path(x) for x in r['artifacts'] if x.endswith('/batch.prn')]
        if len(waves)!=1:raise ValueError('unique retained waveform required')
        wave=waves[0];label=point[0]+'_'+str(point[1]);datasets.append((label,receipt,plan,wave,r,p));paths.extend([receipt,plan,wave])
    if seen!=expected or len(datasets)!=15:raise ValueError('all 15 retained combinational points required')
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),cpu_slots=8,memory_GiB=8,deadline_uptime=deadline,native_simulations_started=0,automatic_identical_retry=False))
    def status(state,**kw):save(out/'status.json',dict(state=state,release_qualified=False,**kw))
    status('waiting_for_shared_resources')
    try:
        with lease(8,8,deadline):
            with ThreadPoolExecutor(max_workers=8) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            if pins[str(binary)]!=a['artifacts'][str(binary)] or pins[str(masters)]!=c['artifacts'][str(masters)]:raise ValueError('controlled parser or current-master inventory changed')
            for _,receipt,plan,wave,r,p in datasets:
                if r['artifacts'][str(wave)]!=pins[str(wave)] or c['input_sha256'][str(plan)]!=pins[str(plan)]:raise ValueError('retained waveform or plan lineage changed')
            status('compiled_strict_slew_reassessment_running',PVT_points=15)
            def task(dataset):
                label,receipt,plan,wave,prior,p=dataset;where=out/label;where.mkdir();cfg=where/'config.json';report=where/'report.json';save(cfg,dict(plan=str(plan),waveform=str(wave),deadline_uptime=deadline,report=str(report)))
                execute([binary,cfg],where/'run.log',deadline,2);r=json.loads(report.read_text())
                if r['fixtures']!=891 or len(p['fixtures'])!=891 or not r['all_native_waveform_events_terminal']:raise ValueError('complete reassessment required')
                for old,new in zip(prior['records'],r['records'],strict=True):
                    for k,v in old.items():equal(v,new[k],label+'.'+str(old['case_index'])+'.'+k)
                failures=[]
                for i,(fixture,record) in enumerate(zip(p['fixtures'],r['records'],strict=True)):
                    if record['case_index']!=i:raise ValueError('fixture index mismatch')
                    if not record['passed'] or not record['strict_output_slew_passed']:
                        master=fixture['master'];failures.append(dict(PVT=p['pvt'],fixture=fixture,current_candidate_instances=counts.get(master,{}).get('instances',0),record=record))
                return dict(label=label,PVT=p['pvt'],fixtures=891,passing=r['passing'],strict_slew_passing=r['strict_output_slew_passing'],prior_records_independently_preserved=True,report=str(report),report_sha256=sha(report),failures=failures)
            with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(task,datasets))
            failures=[f for r in results for f in r.pop('failures')];target=out/'nonpassing_fixtures.jsonl'
            with target.open('x') as f:
                for row in failures:f.write(json.dumps(row)+'\n')
            by_master={}
            for row in failures:
                m=row['fixture']['master'];s=by_master.setdefault(m,dict(current_candidate_instances=row['current_candidate_instances'],nonpassing_fixture_PVT_observations=0,observed_external_loads_pf=[],observed_full_ramps_ps=[]));s['nonpassing_fixture_PVT_observations']+=1
                for key,value in [('observed_external_loads_pf',row['fixture']['external_load_pf']),('observed_full_ramps_ps',row['fixture']['full_ramp_ps'])]:s[key]=sorted(set(s[key]+[value]))
            with ThreadPoolExecutor(max_workers=8) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):raise ValueError('input changed during raw slew audit')
            save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(target):sha(target),**{r['report']:r['report_sha256'] for r in results}},results=results,nonpassing_by_master=by_master,total_fixture_PVT_observations=13365,nonpassing_fixture_PVT_observations=len(failures),all_15_retained_PVT_waves_reassessed=True,all_previously_reported_record_fields_preserved=True,native_simulations_started=0,current_candidate_load_domains_qualified=False,strict_failures_waived=False,physical_timing_qualified=False,release_qualified=False))
            status('all_15_raw_strict_slew_reassessments_complete',nonpassing_observations=len(failures))
    except BaseException as e:
        status('stopped_without_promotion',reason=repr(e));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
