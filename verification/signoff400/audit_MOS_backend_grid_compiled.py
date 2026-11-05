"""Independent eight-worker audit of every sealed MOS terminal response."""
import argparse,json,os,tempfile,time,threading
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease
from compiled_charge import execute
from check_compiled_MOS_response_audit_v2 import config,verify_metrics


def work(out,scratch,deadline):
    base=ROOT/'build/signoff400';grid=base/'startup_timing_MOS_backend_grid_001/assessment.json';a=json.loads(grid.read_text());plan=grid.parent/'plan.json';p=json.loads(plan.read_text());proof=base/'compiled_MOS_response_audit_controls_002/assessment.json';checked=json.loads(proof.read_text());binary=proof.parent/'audit_MOS_responses';pins={str(x):sha(x) for x in (grid,plan,proof,binary,Path(__file__).resolve(),Path(__file__).with_name('check_compiled_MOS_response_audit_v2.py'))}
    if not checked['independent_compiled_named_response_controls_pass'] or pins[str(binary)]!=checked['artifacts'][str(binary)] or not a['all_476_native_profiles_at_all_15_PVT_compared']:raise ValueError('complete producer and compiled audit controls required')
    for name,h in checked['input_sha256'].items():
        if name in pins and pins[name]!=h:raise ValueError('controlled audit helper changed')
    cases=a['case_results'];expected={tuple(sorted(c.items())) for c in p['cases']};seen=set();prepared=[]
    def pin(path,h):
        if path in pins and pins[path]!=h:raise ValueError('conflicting shared input lineage')
        pins[path]=h
    for row in cases:
        case=row['case'];key=tuple(sorted(case.items()))
        if key in seen or key not in expected:raise ValueError('unique exact declared batch coverage')
        seen.add(key);receipt=Path(row['assessment']);pin(str(receipt),row['assessment_sha256']);r=json.loads(receipt.read_text())
        if r['case']!=case or r['profile_ids']!=list(range(case['profile_start'],case['profile_start']+case['profile_count'])):raise ValueError('complete native parameter-profile binding')
        for n,h in r['input_sha256'].items():pin(n,h)
        cfg=config(receipt)
        for analysis in ('dc','ac'):
            for path in cfg[analysis].values():pin(path,r['artifacts'][path])
        prepared.append((case,receipt,r,cfg))
    if seen!=expected or len(cases)!=450:raise ValueError('all 450 exact cases required')
    save(out/'status.json',dict(state='hashing_unique_full_grid_inputs_and_native_data',unique_files=len(pins),release_qualified=False))
    with ThreadPoolExecutor(max_workers=8) as pool:
        for name,h in zip(pins,pool.map(sha,map(Path,pins))):
            if h!=pins[name]:raise ValueError('sealed full-grid input changed: '+name)
    save(out/'input_manifest.json',dict(input_sha256=pins));done=[];lock=threading.Lock();os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    def task(item):
        case,receipt,r,cfg=item;label=f'{case["corner"]}_{case["temperature_c"]}_{case["profile_start"]}';where=scratch/'cases'/label;where.mkdir();path=where/'config.json';save(path,cfg);execute([binary,path],where/'audit.log',deadline,2);result=json.loads((where/'audit.log').read_text());verify_metrics(result,r['results']);record=dict(case=case,producer_assessment=str(receipt),producer_sha256=pins[str(receipt)],audit=str(where/'audit.log'),audit_sha256=sha(where/'audit.log'),config=str(path),config_sha256=sha(path),comparisons=sum(result[k]['terminal_response_comparisons'] for k in ('dc','ac')),results=result)
        with lock:
            done.append(record);save(out/'status.json',dict(state='auditing_all_sealed_native_MOS_batches',completed_batches=len(done),required_batches=450,release_qualified=False))
        return record
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=[future.result() for future in as_completed([pool.submit(task,item) for item in prepared])]
    comparisons=sum(r['comparisons'] for r in results)
    if comparisons!=4284000:raise ValueError('complete independent terminal response count')
    save(out/'status.json',dict(state='rehashing_sealed_grid_inputs_after_audit',release_qualified=False))
    with ThreadPoolExecutor(max_workers=8) as pool:
        for name,h in zip(pins,pool.map(sha,map(Path,pins))):
            if h!=pins[name]:raise ValueError('sealed input changed during audit')
    save(out/'case_results.json',results);save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(out/'case_results.json'):sha(out/'case_results.json')},case_results=results,independent_compiled_full_MOS_grid_audit_complete=True,named_terminal_headers_and_sweep_coordinates_verified_for_every_case=True,all_producer_aggregate_metrics_reproduced_with_controlled_numeric_screen=True,completed_batches=450,profile_PVT_observations=7140,terminal_response_comparisons=comparisons,audit_workers=8,retained_local_scratch=str(scratch),native_simulations_repeated=False,physical_parameter_sets_selected=False,response_error_enclosure_qualified=False,MOS_backend_compatibility_qualified=False,release_qualified=False));save(out/'status.json',dict(state='independent_compiled_full_MOS_grid_audit_complete',release_qualified=False))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);parser.add_argument('--inside',action='store_true');parser.add_argument('--scratch',type=Path);parser.add_argument('--deadline',type=float);args=parser.parse_args();out=args.output.resolve()
    if args.inside:return work(out,args.scratch,args.deadline)
    out.mkdir(parents=True,exist_ok=False);scratch=Path(tempfile.mkdtemp(prefix='openpll-MOS-response-audit-',dir='/tmp'));(scratch/'cases').mkdir();(out/'cases').symlink_to(scratch/'cases',target_is_directory=True);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=8,memory_GiB=16,retained_local_scratch=str(scratch),automatic_identical_retry=False));save(out/'status.json',dict(state='waiting_for_eight_audit_CPU_slots',release_qualified=False))
    try:
        with lease(8,16,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',ROOT/'build/apptainer/openpll-release-modern.sif','/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',Path(__file__).resolve(),'--inside','--deadline',str(deadline),'--scratch',scratch,'--output',out],out/'controller.log',deadline,16)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise


if __name__=='__main__':main()
