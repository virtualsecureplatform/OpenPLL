"""Build a separate exact-plateau-compacted conditional replay variant."""
import argparse,json,os,time,shutil
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from compact_boundary_plateaus import compact_file


def run(bench,replay,output):
    output.mkdir(parents=True,exist_ok=False);r=json.loads((replay/'assessment.json').read_text());a=json.loads((bench/'assessment.json').read_text())
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='compacting_exact_plateaus',release_ready=False))
    pins={str(p):sha(p) for p in [bench/'assessment.json',replay/'assessment.json',Path(__file__).resolve(),ROOT/'verification/signoff400/compact_boundary_plateaus.py']}
    os.sched_setaffinity(0,{26});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    try:
        with lease(1,1,deadline):
            verify(a['artifacts']);counts=[0,0];artifacts={}
            for i in range(a['required_boundary_files']):
                source=bench/f'boundary_{i}.pwl';target=output/source.name
                if sha(source)!=r['artifacts'][str(source)]:raise ValueError('source replay changed')
                stat=compact_file(source,target);counts[0]+=stat['input_knots'];counts[1]+=stat['output_knots'];artifacts[str(target)]=sha(target)
                if i%100==0:save(output/'status.json',dict(state='compacting_exact_plateaus',completed_files=i+1,input_knots=counts[0],output_knots=counts[1],release_ready=False))
                if time.clock_gettime(time.CLOCK_BOOTTIME)>deadline:raise TimeoutError('compaction cap exhausted')
            shutil.copyfile(bench/'devices.spice',output/'devices.spice')
            (output/'boundary_sources.spice').write_text((bench/'boundary_sources.spice').read_text().replace(str(bench)+'/',str(output)+'/'))
            for p in [output/'devices.spice',output/'boundary_sources.spice']:artifacts[str(p)]=sha(p)
            verify(pins)
            save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,retained=a['retained'],required_boundary_files=a['required_boundary_files'],input_knots=counts[0],output_knots=counts[1],exact_saved_knots_replayed=True,boundary_files=a['required_boundary_files'],method='exact_constant_plateau_removal',approximation_used=False,native_model_ready=False,diagnostic=True,release_ready=False))
            save(output/'status.json',dict(state='exact_compacted_replay_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['bench','replay','output']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();run(a.bench.resolve(),a.replay.resolve(),a.output.resolve())
