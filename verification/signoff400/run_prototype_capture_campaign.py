"""Run one declared load/slew capture grid for all used FF masters at five nominal corners."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from common_v3 import ROOT,PROFILE,save,sha,verify,spec
from resources import identity


def review(directory):
    rp=directory/'assessment.json';r=json.loads(rp.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if r['fixtures']!=21 or r['native_completed']!=21 or r['separated_controls']!=6 or not r['separated_controls_pass']:
        raise ValueError('incomplete native capture or failed separated controls')
    observations=json.loads((directory/'observations.json').read_text())
    if any(x['pretest_value']!=x['pretest_expected'] for x in observations):raise ValueError('pretest state integrity failed')
    return dict(corner=r['corner'],master=r['master'],assessment=str(rp),assessment_sha256=sha(rp),
                native_cases=r['native_completed'],separated_controls_pass=True)


def run(pilot,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,
         max_small_cell_workers=4,automatic_identical_retry=False))
    worker=Path(__file__).with_name('run_prototype_capture_boundaries_v2.py');inventory=ROOT/'build/signoff400/startup_corrected_timing_repair_003/masters.txt'
    masters=sorted({x for x in inventory.read_text().split() if '__dfrtp_' in x or '__dfstp_' in x})
    expected={'sky130_fd_sc_hs__dfrtp_1','sky130_fd_sc_hs__dfrtp_2','sky130_fd_sc_hs__dfrtp_4','sky130_fd_sc_hs__dfstp_1','sky130_fd_sc_hs__dfstp_4'}
    if set(masters)!=expected:raise ValueError('used FF inventory changed')
    pins={str(p):sha(p) for p in (PROFILE,worker,inventory,Path(__file__).resolve())}
    save(output/'status.json',dict(state='waiting_for_capture_pilot',release_ready=False))
    while not (pilot/'assessment.json').exists():
        owner=json.loads((pilot/'owner.json').read_text())
        if identity(owner['pid'])!=owner['birth']:raise ValueError('pilot disappeared before completing')
        if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('capture campaign deadline')
        time.sleep(1)
    first=review(pilot);pins[first['assessment']]=first['assessment_sha256'];results=[first]
    todo=[(c,m) for c in spec()['corners'] for m in masters if (c,m)!=(first['corner'],first['master'])]
    if len(todo)!=24:raise ValueError('pilot not part of required 25-point grid')
    save(output/'input_manifest.json',dict(input_sha256=pins,points=[dict(corner=c,master=m) for c,m in todo],
         reused_native_pilot=first,input_slew_ps=200,output_load_fF=20,temperature_c=27,supply_v=1.8))
    def case(corner,master):
        folder=output/(corner+'_'+master.rsplit('__',1)[1]);log=output/(folder.name+'.log')
        remaining=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if remaining<=0:raise TimeoutError('capture campaign deadline')
        command=[sys.executable,str(worker),'--corner',corner,'--master',master,'--output',str(folder)]
        with log.open('x') as stream:
            completed=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=remaining)
        if completed.returncode:raise ValueError('native capture point failed: '+str(folder))
        return review(folder)
    failures=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(case,c,m):(c,m) for c,m in todo}
        for future in as_completed(futures):
            try:results.append(future.result())
            except Exception as error:failures.append(dict(point=list(futures[future]),reason=repr(error)))
            save(output/'status.json',dict(state='native_small_cell_capture_campaign_running',completed_points=len(results),failed_points=len(failures),release_ready=False))
    verify(pins);detail=output/'points.json';save(detail,dict(results=results,failures=failures))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         required_points=25,completed_points=len(results),native_cases=sum(x['native_cases'] for x in results),
         all_25_nominal_capture_points_complete=len(results)==25 and not failures,
         input_slew_ps=200,output_load_fF=20,setup_hold_recovery_removal_tables_qualified=False,
         other_load_slew_points_covered=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='capture_campaign_terminal_review_pending',completed_points=len(results),failed_points=len(failures),release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pilot',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.pilot.resolve(),a.output.resolve())
