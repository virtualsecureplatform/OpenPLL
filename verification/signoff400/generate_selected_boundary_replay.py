"""Generate exact saved-knot PWL files for a diagnostic boundary replay."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,sha,save,verify
from resources import lease,identity

def run(coverage,plan,bench,output):
    output.mkdir(parents=True,exist_ok=False)
    d=json.loads(plan.read_text());c=json.loads(coverage.read_text());raw=Path(c['waveform'])
    if not c['all_bound'] or c['input_sha256'].get(str(plan))!=sha(plan):raise ValueError('matching complete boundary coverage required')
    source=ROOT/'tools/xyce_waveform/extract_boundary_pwl.cpp'
    pins={str(p):sha(p) for p in [coverage,plan,bench/'devices.spice',bench/'boundary_sources.spice',source,Path(__file__).resolve()]}
    save(output/'inputs.json',dict(input_sha256=pins,raw_path=str(raw),diagnostic=True,release_ready=False))
    before=raw.stat();deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='generating_boundary_replay',release_ready=False))
    indices=output/'indices.txt';indices.write_text(''.join(str(c['bindings'][node]['index'])+'\n' for node in d['required_non_supply_boundary_voltage_nodes']))
    os.sched_setaffinity(0,{24})
    try:
        with lease(1,4,deadline):
            subprocess.run(['g++','-O3','-std=c++17',source,'-o',output/'extract'],check=True,timeout=60)
            with (output/'native.log').open('w') as log:subprocess.run([output/'extract',raw,indices,bench],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=max(1,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
        after=raw.stat()
        if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('source waveform changed')
        verify(pins)
        artifacts={str(bench/f'boundary_{i}.pwl'):sha(bench/f'boundary_{i}.pwl') for i in range(len(d['required_non_supply_boundary_voltage_nodes']))}
        save(output/'assessment.json',dict(input_sha256=pins,raw_sha256=sha(raw),artifacts=artifacts,exact_saved_knots_replayed=True,boundary_files=len(artifacts),boundary_assumptions_validated=False,release_ready=False))
        save(output/'status.json',dict(state='boundary_replay_files_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['coverage','plan','bench','output']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();run(a.coverage.resolve(),a.plan.resolve(),a.bench.resolve(),a.output.resolve())
