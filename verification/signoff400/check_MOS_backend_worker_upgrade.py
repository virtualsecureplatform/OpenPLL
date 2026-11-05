"""Verify compact metadata preserves every generated physical MOS circuit."""
import argparse,json,time
from pathlib import Path
from common import save,sha
from resources import lease
import run_MOS_backend_case as old
import run_MOS_backend_case_v2 as new


def run(out):
    out.mkdir(parents=True,exist_ok=False);root=Path.cwd();base=root/'build/signoff400';inventory=base/'startup_timing_MOS_backend_profiles_001';proof=inventory/'assessment.json';a=json.loads(proof.read_text());profiles=inventory/'profiles.jsonl';plan=inventory/'comparison_plan.json';benchmark=base/'startup_timing_MOS_backend_batch_control_001/assessment.json';b=json.loads(benchmark.read_text());paths=[proof,profiles,plan,benchmark,Path(old.__file__).resolve(),Path(new.__file__).resolve(),Path(__file__).resolve()];deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    with lease(1,2,deadline):
        pins={str(p):sha(p) for p in paths}
        for p in (profiles,plan):
            if pins[str(p)]!=a['artifacts'][str(p)]:raise ValueError('profile/grid inventory changed')
        if b['case']!=dict(corner='tt',temperature_c=27,profile_start=0,profile_count=16) or not b['both_simulators_terminal']:raise ValueError('controlled completed initial batch required')
        if pins[str(Path(old.__file__).resolve())]!=b['input_sha256'][str(Path(old.__file__).resolve())]:raise ValueError('original worker source changed')
        p=[json.loads(l) for l in profiles.read_text().splitlines()];grid=json.loads(plan.read_text());comparisons=0;old_size=new_size=0
        for start in range(0,len(p),16):
            batch=p[start:start+16]
            for analysis in ('dc','ac'):
                left=old.deck_body(batch,grid,analysis);right=new.deck_body(batch,grid,analysis)
                if left[1:]!=right[1:] or len(left[0])!=len(right[0]):raise ValueError('physical circuit or observation vectors changed')
                for a,b in zip(left[0],right[0],strict=True):
                    if {k:v for k,v in a.items() if k!='profile'}!={k:v for k,v in b.items() if k!='profile'} or {k:a['profile'][k] for k in ('profile_id','model','parameters')}!=b['profile']:raise ValueError('fixture identity changed')
                comparisons+=1
                if start==0 and analysis=='ac':old_size=len(json.dumps(left[0]));new_size=len(json.dumps(right[0]))
        if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('worker upgrade source changed')
        save(out/'assessment.json',dict(input_sha256=pins,all_476_profiles_preserve_physical_deck_and_observation_vectors=True,profile_batches=30,analysis_batches_compared=comparisons,benchmark_physics_reuse_verified=True,first_batch_AC_metadata_JSON_bytes_before=old_size,first_batch_AC_metadata_JSON_bytes_after=new_size,external_caller_lease_execution_validated=False,native_simulations_started=0,MOS_backend_compatibility_qualified=False,release_qualified=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
