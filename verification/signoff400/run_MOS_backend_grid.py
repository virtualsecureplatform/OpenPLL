"""Compare all current MOS profiles on the declared finite 15-PVT bias grid."""
import argparse,json,os,sys,time,threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from common import ROOT,save,sha
from resources import identity,lease
from compiled_charge import execute


def run(out):
    out.mkdir(parents=True,exist_ok=False);base=ROOT/'build/signoff400';inventory=base/'startup_timing_MOS_backend_profiles_001';proof=inventory/'assessment.json';a=json.loads(proof.read_text());plan=inventory/'comparison_plan.json';grid=json.loads(plan.read_text());profiles=inventory/'profiles.jsonl';upgrade=base/'startup_timing_MOS_backend_worker_upgrade_001/assessment.json';u=json.loads(upgrade.read_text());benchmark=base/'startup_timing_MOS_backend_batch_control_001/assessment.json';b=json.loads(benchmark.read_text());worker=ROOT/'verification/signoff400/run_MOS_backend_case_v2.py';paths=[proof,plan,profiles,upgrade,benchmark,worker,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths};deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    if a['full_parameter_profiles']!=476 or not u['all_476_profiles_preserve_physical_deck_and_observation_vectors'] or not u['benchmark_physics_reuse_verified']:raise ValueError('complete controlled profile/generator inventory required')
    if pins[str(worker)]!=u['input_sha256'][str(worker)]:raise ValueError('controlled compact worker changed')
    for p in (profiles,plan):
        if pins[str(p)]!=a['artifacts'][str(p)]:raise ValueError('complete profile/grid source changed')
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),cpu_slots_per_case=1,memory_GiB_per_case=4,maximum_native_workers=14,deadline_uptime=deadline,automatic_identical_retry=False,maximum_workers_reason='32-core shared cap minus 16-core live projection reservation minus 2-core projection controls'))
    logs=out/'case_logs';logs.mkdir();cases=[]
    for point in grid['required_PVT']:
        for start in range(0,476,16):cases.append(dict(corner=point['corner'],temperature_c=point['temperature_c'],profile_start=start,profile_count=min(16,476-start)))
    if len(cases)!=450:raise ValueError('450 disjoint PVT/profile batches required')
    save(out/'plan.json',dict(input_sha256=pins,cases=cases,required_case_batches=450,required_profile_PVT_observations=7140,required_terminal_response_comparisons=4284000,benchmark_reused=str(benchmark),response_error_enclosure_qualified=False,physical_junction_parameter_set_selected=False,release_qualified=False))
    def status(state,**kw):save(out/'status.json',dict(state=state,release_qualified=False,**kw))
    done=[];lock=threading.Lock()
    def verify(receipt,case,reused):
        r=json.loads(receipt.read_text())
        if r['case']!=case or r['profile_ids']!=list(range(case['profile_start'],case['profile_start']+case['profile_count'])) or not r['both_simulators_terminal']:raise ValueError('complete exact native batch required')
        if r['results']['dc']['terminal_response_comparisons']!=case['profile_count']*6*7*4 or r['results']['ac']['terminal_response_comparisons']!=case['profile_count']*54*2*4:raise ValueError('complete declared terminal/bias/excitation scope')
        # All common model, profile, grid, image and binary dependencies must match
        # the sealed benchmark; worker code differs only under the upgrade proof.
        for n,h in b['input_sha256'].items():
            if n in r['input_sha256'] and r['input_sha256'][n]!=h:raise ValueError('shared physical model/binary/grid source changed')
        for analysis in ('dc','ac'):
            raw=receipt.parent/analysis/'comparison.json'
            if sha(raw)!=r['artifacts'][str(raw)]:raise ValueError('batch metric artifact changed')
        result=dict(case=case,assessment=str(receipt),assessment_sha256=sha(receipt),benchmark_reused=reused,results=r['results'])
        with lock:done.append(result);save(out/'case_results.json',done);status('MOS_backend_grid_running',completed_batches=len(done),required_batches=450)
        return result
    benchmark_case=dict(corner='tt',temperature_c=27,profile_start=0,profile_count=16);verify(benchmark,benchmark_case,True)
    # Validate caller-owned resource admission on one new circuit before broad launch.
    first=dict(corner='tt',temperature_c=27,profile_start=16,profile_count=16)
    def task(case):
        label=f'{case["corner"]}_{case["temperature_c"]}_profiles_{case["profile_start"]}';where=out/label
        with lease(1,4,deadline) as token:
            execute([sys.executable,worker,'--output',where,'--corner',case['corner'],'--temperature-c',case['temperature_c'],'--profile-start',case['profile_start'],'--profile-count',case['profile_count'],'--deadline',deadline,'--lease-token',token],logs/(label+'.log'),deadline,4)
        return verify(where/'assessment.json',case,False)
    status('validating_new_caller_owned_lease_execution',completed_batches=1,required_batches=450)
    try:
        task(first);save(out/'caller_lease_control.json',dict(first_completed_case=first,caller_owned_lease_execution_validated=True,automatic_identical_retry=False,release_qualified=False))
        pending=[c for c in cases if c not in (benchmark_case,first)]
        with ThreadPoolExecutor(max_workers=14) as pool:
            for f in as_completed([pool.submit(task,c) for c in pending]):f.result()
        if len(done)!=450 or len({tuple(sorted(r['case'].items())) for r in done})!=450:raise ValueError('exact complete unique native grid')
        comparisons=sum(sum(v['terminal_response_comparisons'] for v in r['results'].values()) for r in done)
        if comparisons!=4284000:raise ValueError('full terminal response inventory')
        if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('grid controller source changed')
        save(out/'assessment.json',dict(input_sha256=pins,case_results=done,completed_case_batches=450,completed_profile_PVT_observations=7140,terminal_response_comparisons=comparisons,one_sealed_benchmark_case_reused_without_resimulation=True,all_476_native_profiles_at_all_15_PVT_compared=True,all_declared_DC_biases_and_AC_terminal_excitations_compared=True,maximum_native_workers=14,response_error_enclosure_qualified=False,physical_junction_parameter_set_selected=False,MOS_backend_compatibility_qualified=False,release_qualified=False));status('all_current_MOS_backend_grid_observations_complete')
    except BaseException as e:status('stopped_without_promotion',reason=repr(e),completed_batches=len(done));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
