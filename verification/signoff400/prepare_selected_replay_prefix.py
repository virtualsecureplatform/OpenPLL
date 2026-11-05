"""Exact PWL prefix, including the first knot at/after a bounded control endpoint."""
import argparse,json,math,os,shutil,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease


def prefix(lines,stop):
    if not math.isfinite(stop) or stop<=0:raise ValueError('positive finite endpoint required')
    previous=-1;result=[]
    for line in lines:
        if not line.strip():continue
        fields=line.split()
        if len(fields)!=2:raise ValueError('two-column PWL required')
        t,v=map(float,fields)
        if not math.isfinite(t) or not math.isfinite(v) or t<=previous:raise ValueError('finite ordered knots required')
        if not result and t!=0:raise ValueError('time-zero knot required')
        previous=t;result.append(line)
        if t>=stop:return result
    raise ValueError('missing right guard knot')


def run(bench,replay,output,stop=1e-15):
    output.mkdir(parents=True,exist_ok=False);r=json.loads((replay/'assessment.json').read_text());a=json.loads((bench/'assessment.json').read_text())
    if not r['exact_saved_knots_replayed']:raise ValueError('verified native replay required')
    pins={str(p):sha(p) for p in [bench/'assessment.json',replay/'assessment.json',Path(__file__).resolve()]}
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));save(output/'status.json',dict(state='building_bounded_prefix',release_ready=False))
    os.sched_setaffinity(0,{27});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    try:
        with lease(1,1,deadline):
            verify(a['artifacts']);artifacts={}
            for i in range(a['required_boundary_files']):
                source=bench/f'boundary_{i}.pwl';target=output/source.name
                before=source.stat()
                with source.open() as f:rows=prefix(f,stop)
                after=source.stat()
                if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('source replay changed')
                target.write_text(''.join(rows));artifacts[str(target)]=sha(target)
                if i%500==0:save(output/'status.json',dict(state='building_bounded_prefix',completed_files=i+1,release_ready=False))
                if time.clock_gettime(time.CLOCK_BOOTTIME)>deadline:raise TimeoutError('prefix build cap exhausted')
            shutil.copyfile(bench/'devices.spice',output/'devices.spice')
            (output/'boundary_sources.spice').write_text((bench/'boundary_sources.spice').read_text().replace(str(bench)+'/',str(output)+'/'))
            for p in [output/'devices.spice',output/'boundary_sources.spice']:artifacts[str(p)]=sha(p)
            verify(pins)
            save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,retained=a['retained'],required_boundary_files=a['required_boundary_files'],boundary_files=a['required_boundary_files'],exact_replay_valid_through_s=stop,full_260ns_replay=False,native_model_ready=False,diagnostic=True,release_ready=False))
            save(output/'status.json',dict(state='bounded_prefix_files_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['bench','replay','output']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();run(a.bench.resolve(),a.replay.resolve(),a.output.resolve())
