"""Observe extreme thermometer carry hazards across PVT and oscillator phases."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import subprocess
import sys
from common_v3 import ROOT,save,sha,verify

def run(output):
    worker=Path(__file__).with_name('run_prototype_candidate_DCO_transition.py')
    inputs={str(p):sha(p) for p in (worker,Path(__file__).resolve())};tasks=[]
    output.mkdir(parents=True,exist_ok=False)
    for corner,coarse in [('tt',20),('ff',9),('ss',47),('sf',26),('fs',20)]:
        source=ROOT/f'build/signoff400/prototype_v3_DCO_fine_grain_high_routed_{corner}_co{coarse}_fine8_001'
        receipt=source/'assessment.json';inputs[str(receipt)]=sha(receipt)
        for hazard in (0,255):
            for phase in (0,.625,1.25,1.875):
                folder=output/f'{corner}_hazard{hazard}_phase{str(phase).replace(".","p")}'
                command=['taskset','-c','0-31',sys.executable,worker,'--source',source,'--initial','127','--final','128','--hazard',str(hazard),'--phase-ns',str(phase),'--output',folder]
                tasks.append((folder,list(map(str,command))))
    save(output/'input_manifest.json',dict(input_sha256=inputs,point_commands=[c for _,c in tasks],simultaneous_point_producers=12,
         initial_code=127,final_code=128,injected_extreme_hazard_codes=[0,255],
         physical_control_ramp_ps=200,hazard_plateau_ps=200,
         extracted_decoder_timing=False,final_parent_loading_complete=False,automatic_identical_retry=False,release_ready=False))
    def one(folder,command):
        with (output/(folder.name+'.driver.log')).open('x') as stream:
            code=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT).returncode
        return dict(point=str(folder),exit_code=code)
    results=[]
    with ThreadPoolExecutor(max_workers=12) as pool:
        for future in as_completed([pool.submit(one,*task) for task in tasks]):
            results.append(future.result());save(output/'status.json',dict(state='native_hazard_campaign_running',completed_points=len(results),failed_points=sum(r['exit_code']!=0 for r in results),release_ready=False))
    verify(inputs);detail=output/'results.json';save(detail,results)
    failed=sum(r['exit_code']!=0 for r in results)
    for row in results:
        if row['exit_code']==0:
            path=Path(row['point'])/'assessment.json';inputs[str(path)]=sha(path)
    save(output/'assessment.json',dict(input_sha256=inputs,artifacts={str(detail):sha(detail)},native_points_completed=len(results)-failed,
         failed_points=failed,all_oscillator_phases_proved=False,extracted_decoder_timing_included=False,
         final_parent_loading_complete=False,native_dynamic_control_response_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='native_hazard_campaign_complete' if not failed else 'native_hazard_campaign_failed',completed_points=len(results),failed_points=failed,release_ready=False))
    if failed:raise RuntimeError('native hazard failures preserved without retry')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output.resolve())
