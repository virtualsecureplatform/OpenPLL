"""Search the declared gain grid for one corner using explicitly unqualified loop models."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
import os
from pathlib import Path
import time
from common_v3 import ROOT,PROFILE,spec,save,sha,verify
from resources import identity
from compiled_charge import execute


def run(models,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    m=json.loads(models.read_text());verify(m['input_sha256'])
    if not m['synthetic']:raise ValueError('this campaign accepts diagnostic models only')
    corner=m['corner'];profile=spec();image=ROOT/'build/apptainer/openpll-release-modern.sif';worker=Path(__file__).with_name('loop_v3.py').resolve()
    pins={str(p):sha(p) for p in (models,PROFILE,image,worker,Path(__file__).resolve())}
    binaries=['/usr/bin/iverilog','/usr/bin/iverilog-vpi','/usr/bin/vvp'];toolfile=output/'toolchain.json'
    code='import hashlib,json,sys;json.dump({p:hashlib.sha256(open(p,"rb").read()).hexdigest() for p in sys.argv[2:]},open(sys.argv[1],"w"))'
    execute(['apptainer','exec','--bind','/home:/home',image,'/usr/bin/python3','-c',code,toolfile,*binaries],output/'toolchain.log',deadline,4)
    toolhashes=json.loads(toolfile.read_text());results=[]
    grid=[(ki,kp) for ki in profile['gain_search']['ki'] for kp in profile['gain_search']['kp']]
    def point(pair):
        ki,kp=pair;existing=ROOT/f'build/signoff400/prototype_v3_loop_diagnostic_{corner.upper()}_ki{ki}_kp{kp}_001'
        reused=(existing/'assessment.json').exists();where=existing if reused else output/f'ki{ki}_kp{kp}'
        if not reused:
            execute(['apptainer','exec','--bind','/home:/home',image,'/usr/bin/python3',worker,'--models',models,'--output',where,'--ki',ki,'--kp',kp,'--diagnostic'],output/f'ki{ki}_kp{kp}.log',deadline,4)
        rp=where/'assessment.json';r=json.loads(rp.read_text())
        for path,digest in r['input_sha256'].items():
            if path in toolhashes:
                if toolhashes[path]!=digest:raise ValueError('loop image toolchain differs')
            elif sha(Path(path))!=digest:raise ValueError('loop source changed: '+path)
        verify(r['artifacts'])
        if r['corner']!=corner or r['ki']!=ki or r['kp']!=kp or r['physical_models_qualified'] or r['prototype_trace_pass'] or r['input_sha256'].get(str(models))!=pins[str(models)]:raise ValueError('matching unqualified diagnostic loop required')
        expected={(s,p) for s in profile['scenarios'] for p in profile['reference_phase_offsets_ns']}
        if len(r['records'])!=12 or {(x['scenario'],x['phase_offset_ns']) for x in r['records']}!=expected:raise ValueError('complete per-corner trace matrix required')
        return dict(ki=ki,kp=kp,reused=reused,assessment=str(rp),sha256=sha(rp),passed_cases=sum(x['passed'] for x in r['records']),all_cases_passed=r['all_trace_cases_passed'])
    save(output/'status.json',dict(state='diagnostic_gain_grid_running',completed_points=0,release_ready=False))
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(point,pair) for pair in grid]
        for future in as_completed(futures):
            results.append(future.result());save(output/'status.json',dict(state='diagnostic_gain_grid_running',completed_points=len(results),passing_points=sum(r['all_cases_passed'] for r in results),release_ready=False))
    results.sort(key=lambda r:(r['ki'],r['kp']));detail=output/'points.json';save(detail,results);verify(pins)
    pins.update({r['assessment']:r['sha256'] for r in results})
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (detail,toolfile)},corner=corner,
        gain_points=len(results),trace_cases=12*len(results),passing_gain_pairs=[[r['ki'],r['kp']] for r in results if r['all_cases_passed']],
        native_model_holdouts_complete=False,common_five_corner_gains_qualified=False,
        diagnostic=True,synthetic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='diagnostic_gain_grid_complete',completed_points=len(results),passing_points=sum(r['all_cases_passed'] for r in results),release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--models',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.models.resolve(),a.output.resolve())
