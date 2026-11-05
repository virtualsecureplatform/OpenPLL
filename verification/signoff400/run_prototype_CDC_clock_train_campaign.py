"""Run bounded CDC clock-train observations for the actual first-stage envelope."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
import os
from pathlib import Path
import subprocess
import sys
from common_v3 import ROOT,save,sha,verify

def run(extraction,envelopes,output,reuse_pilot):
    source=Path(__file__).with_name('run_prototype_CDC_clock_train_point.py');inputs={str(p):sha(p) for p in (extraction/'assessment.json',source,Path(__file__).resolve())}
    records=[]
    for directory in envelopes:
        p=directory/'assessment.json';a=json.loads(p.read_text());verify(a['artifacts'])
        if a['maximum_Q_load_fF']>20 or a['maximum_slew_ps_by_pin']['CLK']>240 or max(a['maximum_slew_ps_by_pin']['D'],a['maximum_slew_ps_by_pin']['RESET_B'])>1200:raise ValueError('actual first stages exceed proposed native observation envelope')
        records.append(a['corner']);inputs[str(p)]=sha(p)
    if sorted(records)!=['ff','fs','sf','ss','tt']:raise ValueError('five native corner pin envelopes required')
    pilot_receipt=reuse_pilot/'assessment.json';pilot=json.loads(pilot_receipt.read_text())
    verify(pilot['input_sha256']);verify(pilot['artifacts'])
    expected=dict(corner='ss',master='sky130_fd_sc_hs__dfrtp_1',load_fF=20,input_full_ramp_ps=2000,clock_full_ramp_ps=400,clock_period_ns=2,clock_high_ns=1)
    if any(pilot.get(k)!=v for k,v in expected.items()) or pilot['input_sha256'].get(str(source))!=sha(source) or pilot['input_sha256'].get(str(extraction/'assessment.json'))!=sha(extraction/'assessment.json'):
        raise ValueError('matching completed clock-train pilot required')
    inputs[str(pilot_receipt)]=sha(pilot_receipt)
    output.mkdir(parents=True,exist_ok=False);tasks=[]
    for corner in records:
        for data in (20,200,2000):
            for clock in (20,200,400):
                if (corner,data,clock)==('ss',2000,400):
                    tasks.append((reuse_pilot,['reuse_checked_point',str(reuse_pilot)]));continue
                folder=output/f'{corner}_d{data}_c{clock}'
                command=['taskset','-c','0-31',sys.executable,source,'--output',folder,'--extraction',extraction,'--corner',corner,'--master','dfrtp_1','--load-ff','20','--data-ramp-ps',str(data),'--clock-ramp-ps',str(clock)]
                tasks.append((folder,command))
    save(output/'input_manifest.json',dict(input_sha256=inputs,simultaneous_point_producers=12,point_commands=[list(map(str,c)) for _,c in tasks],native_point_resource_leases_retained=True,release_ready=False))
    def one(folder,command):
        if command[0]=='reuse_checked_point':return dict(point=str(folder),exit_code=0,reused_completed_pilot=True)
        with (output/(folder.name+'.driver.log')).open('x') as stream:
            code=subprocess.run(list(map(str,command)),cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT).returncode
        return dict(point=str(folder),exit_code=code)
    results=[];save(output/'status.json',dict(state='native_CDC_resolution_campaign_running',completed_points=0,release_ready=False))
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures=[pool.submit(one,*t) for t in tasks]
        for future in as_completed(futures):
            results.append(future.result());save(output/'status.json',dict(state='native_CDC_resolution_campaign_running',completed_points=len(results),failed_points=sum(r['exit_code']!=0 for r in results),release_ready=False))
    detail=output/'results.json';save(detail,results);verify(inputs)
    if any(r['exit_code']!=0 for r in results):
        save(output/'status.json',dict(state='campaign_terminal_with_failed_points',failed_points=[r['point'] for r in results if r['exit_code']!=0],release_ready=False));raise ValueError('native capture points failed; no automatic retry')
    for folder,_ in tasks:
        receipt=folder/'assessment.json';a=json.loads(receipt.read_text());verify(a['artifacts']);inputs[str(receipt)]=sha(receipt)
    save(output/'assessment.json',dict(input_sha256=inputs,artifacts={str(detail):sha(detail)},native_points_completed=len(tasks),native_cases_completed=45*75,master='sky130_fd_sc_hs__dfrtp_1',load_fF=20,clock_period_ns=2,clock_high_ns=1,pre_next_edge_observation_end_ns=21.8,all_actual_first_stage_pin_envelopes_enclosed=True,observed_resolution_review_complete=False,statistical_or_continuous_metastability_bound_proved=False,FIT_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='native_CDC_resolution_campaign_complete_review_pending',completed_points=len(results),release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--extraction',type=Path,required=True);p.add_argument('--envelope',type=Path,required=True,action='append');p.add_argument('--output',type=Path,required=True);p.add_argument('--reuse-pilot',type=Path,required=True)
    a=p.parse_args();run(a.extraction.resolve(),[x.resolve() for x in a.envelope],a.output.resolve(),a.reuse_pilot.resolve())
