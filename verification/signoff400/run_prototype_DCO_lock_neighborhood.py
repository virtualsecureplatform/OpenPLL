"""Measure native 80ns points around every observed steady-state control range."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import subprocess
import sys
from common_v3 import ROOT,save,sha,verify

def run(candidate,rc,output):
    worker=Path(__file__).with_name('run_prototype_DCO_candidate_reference_point.py')
    inputs={str(p):sha(p) for p in (candidate/'assessment.json',rc/'assessment.json',worker,Path(__file__).resolve())}
    output.mkdir(parents=True,exist_ok=False);tasks=[]
    for corner,coarse,seed in [('tt',20,111),('ff',9,178),('ss',47,101),('sf',26,90),('fs',20,137)]:
        for delta in (-2,-1,1,2):
            fine=seed+delta;folder=output/f'{corner}_co{coarse}_fine{fine}'
            command=['taskset','-c','0-31',sys.executable,worker,'--candidate',candidate,'--rc',rc,'--corner',corner,'--coarse',str(coarse),'--fine',str(fine),'--output',folder]
            tasks.append((folder,list(map(str,command))))
    save(output/'input_manifest.json',dict(input_sha256=inputs,point_commands=[c for _,c in tasks],
         simultaneous_point_producers=16,center_reference_jobs_reused_separately=True,
         automatic_identical_retry=False,release_ready=False))
    def one(folder,command):
        with (output/(folder.name+'.driver.log')).open('x') as stream:
            code=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT).returncode
        return dict(point=str(folder),exit_code=code)
    results=[]
    with ThreadPoolExecutor(max_workers=16) as pool:
        for future in as_completed([pool.submit(one,*task) for task in tasks]):
            results.append(future.result());save(output/'status.json',dict(state='lock_neighborhood_running',completed_points=len(results),failed_points=sum(r['exit_code']!=0 for r in results),release_ready=False))
    verify(inputs);detail=output/'results.json';save(detail,results)
    for row in results:
        if row['exit_code']==0:
            p=Path(row['point'])/'assessment.json';inputs[str(p)]=sha(p)
    failed=sum(r['exit_code']!=0 for r in results)
    save(output/'assessment.json',dict(input_sha256=inputs,artifacts={str(detail):sha(detail)},
         native_points_completed=len(results)-failed,failed_points=failed,parent_loading_complete=False,
         calibration_and_model_uncertainty_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='lock_neighborhood_complete' if not failed else 'lock_neighborhood_failed',completed_points=len(results),failed_points=failed,release_ready=False))
    if failed:raise RuntimeError('native neighborhood failures preserved without retry')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','rc','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(args.candidate.resolve(),args.rc.resolve(),args.output.resolve())
