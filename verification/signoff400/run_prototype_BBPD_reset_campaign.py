"""Run corrected five-corner late-reset release controls; qualify no interface loading."""
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


def review(folder,corner,release):
    receipt=folder/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if r['corner']!=corner or r['reset_start_ns']!=release or r['geometry_model']!='signal' or r['completed_cases']!=2 or r['all_reset_capture_controls_pass'] is not True:raise ValueError('incomplete/mismatched native reset controls')
    obs=json.loads((folder/'observations.json').read_text())
    if obs['failures'] or {x['phase_ps'] for x in obs['results']}!={-1000,1000}:raise ValueError('signed reset-phase coverage incomplete')
    return dict(corner=corner,reset_start_ns=release,assessment=str(receipt),sha256=sha(receipt),native_cases=2)


def run(pilot,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    first=review(pilot,'tt',15);worker=Path(__file__).with_name('run_prototype_BBPD_reset_point.py')
    pins={str(p):sha(p) for p in (PROFILE,worker,pilot/'assessment.json',Path(__file__).resolve())}
    points=[(c,r) for c in spec()['corners'] for r in (15,25,35) if (c,r)!=('tt',15)]
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,max_small_native_workers=4,automatic_identical_retry=False))
    save(output/'input_manifest.json',dict(input_sha256=pins,points=[dict(corner=c,reset_start_ns=r) for c,r in points],reused_native_pilot=first,
        phase_ps=[-1000,1000],temperature_c=27,supply_v=1.8,actual_sequencer_timing_included=False))
    results=[first];failures=[]
    def point(corner,release):
        folder=output/(corner+'_release'+str(release));log=output/(folder.name+'.log')
        command=[sys.executable,str(worker),'--geometry-model','signal','--corner',corner,'--phases-ps','-1000','1000','--reset-start-ns',str(release),'--output',str(folder)]
        remaining=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if remaining<=0:raise TimeoutError('reset campaign deadline')
        with log.open('x') as stream:code=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=remaining).returncode
        if code:raise ValueError('native reset point failed')
        return review(folder,corner,release)
    save(output/'status.json',dict(state='native_reset_campaign_running',completed_points=1,failed_points=0,release_ready=False))
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(point,c,r):(c,r) for c,r in points}
        for future in as_completed(futures):
            try:results.append(future.result())
            except Exception as exc:failures.append(dict(point=list(futures[future]),reason=repr(exc)))
            save(output/'status.json',dict(state='native_reset_campaign_running',completed_points=len(results),failed_points=len(failures),release_ready=False))
    verify(pins);detail=output/'points.json';save(detail,dict(results=results,failures=failures))
    complete=len(results)==15 and not failures and {(r['corner'],r['reset_start_ns']) for r in results}=={(c,r) for c in spec()['corners'] for r in (15,25,35)}
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},required_points=15,completed_points=len(results),native_cases=sum(r['native_cases'] for r in results),
        all_declared_late_reset_release_controls_pass=complete,actual_sequencer_timing_included=False,intercell_RC_included=False,parent_coupling_included=False,
        omitted_loads_bounded=False,native_interface_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='native_reset_campaign_terminal',completed_points=len(results),failed_points=len(failures),release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pilot',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.pilot.resolve(),a.output.resolve())
