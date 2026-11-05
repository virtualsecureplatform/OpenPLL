"""Measure corrected five-corner detector/receiver phase response and separate full-model holdouts."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from common_v3 import ROOT,PROFILE,spec,save,sha,verify
from resources import identity

PHASES=[-1000,-200,-50,-20,-5,0,5,20,50,200,1000]


def run(output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    worker=Path(__file__).with_name('run_prototype_BBPD_ng47_corner.py')
    correlation=ROOT/'build/signoff400/prototype_v3_BBPD_corrected_TT_model_comparison_001/assessment.json';r=json.loads(correlation.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if r['compared_phase_cases']!=3 or r['all_signal_threshold_crossing_counts_match'] is not True:raise ValueError('completed TT full/reduced native correlation required')
    points=[dict(corner=c,geometry_model='signal',phases=PHASES) for c in spec()['corners']]
    points += [dict(corner=c,geometry_model='full',phases=[-1000,0,1000]) for c in spec()['corners'] if c!='tt']
    pins={str(p):sha(p) for p in (PROFILE,worker,correlation,Path(__file__).resolve())}
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,max_small_native_workers=8,automatic_identical_retry=False))
    save(output/'input_manifest.json',dict(input_sha256=pins,points=points,reused_TT_full_correlation=str(correlation),native_case_count=67,
        temperature_c=27,supply_v=1.8,parent_intercell_and_omitted_load_bounds_qualified=False))
    results=[];failures=[]
    def point(row):
        folder=output/(row['corner']+'_'+row['geometry_model']);log=output/(folder.name+'.log')
        command=[sys.executable,str(worker),'--output',str(folder),'--geometry-model',row['geometry_model'],'--corner',row['corner'],'--phases-ps',*map(str,row['phases'])]
        remaining=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if remaining<=0:raise TimeoutError('BBPD campaign deadline')
        with log.open('x') as stream:code=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=remaining).returncode
        if code:raise ValueError('corrected native corner process failed')
        receipt=folder/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        if r['corner']!=row['corner'] or r['geometry_model']!=row['geometry_model'] or r['completed_cases']!=len(row['phases']) or r['all_declared_native_waveforms_complete'] is not True:raise ValueError('incomplete/mismatched native phase point')
        observed=folder/'observations.json';data=json.loads(observed.read_text())
        if data['failures'] or len(data['results'])!=len(row['phases']) or {p['phase_ps'] for p in data['results']}!=set(row['phases']):raise ValueError('native phase coverage incomplete')
        return dict(**row,assessment=str(receipt),sha256=sha(receipt),native_cases=len(row['phases']))
    save(output/'status.json',dict(state='corrected_BBPD_corner_campaign_running',completed_points=0,failed_points=0,release_ready=False))
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures={pool.submit(point,row):row for row in points}
        for future in as_completed(futures):
            try:results.append(future.result())
            except Exception as exc:failures.append(dict(point=futures[future],reason=repr(exc)))
            save(output/'status.json',dict(state='corrected_BBPD_corner_campaign_running',completed_points=len(results),failed_points=len(failures),release_ready=False))
    verify(pins);detail=output/'points.json';save(detail,dict(results=results,failures=failures))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},required_points=9,completed_points=len(results),
        native_cases=sum(p['native_cases'] for p in results),all_declared_native_phase_points_complete=len(results)==9 and not failures,
        fine_phase_grid_ps=PHASES,full_model_holdout_grid_ps=[-1000,0,1000],
        full_model_corner_correlations_complete=False,intercell_RC_included=False,parent_coupling_included=False,omitted_loads_bounded=False,native_interface_qualified=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='corrected_BBPD_corner_campaign_terminal',completed_points=len(results),failed_points=len(failures),release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);run(p.parse_args().output.resolve())
