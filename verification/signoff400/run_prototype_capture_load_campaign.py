"""Measure declared higher-load FF capture points; qualify no load envelope or timing table."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from common_v3 import ROOT, PROFILE, save, sha, verify, spec
from resources import identity
from run_prototype_capture_campaign import review
from assess_prototype_capture_waveforms import run as waveform_review

LOADS = {'dfrtp_1':100, 'dfrtp_2':150, 'dfrtp_4':250, 'dfstp_1':50, 'dfstp_4':250}


def run(output, ramp_ps):
    if ramp_ps not in (200,500):raise ValueError('declared full-ramp grid is 200 or 500 ps')
    output.mkdir(parents=True, exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    worker=Path(__file__).with_name('run_prototype_capture_boundaries_v3.py')
    assessor=Path(__file__).with_name('assess_prototype_capture_waveforms.py')
    inventory=ROOT/'build/signoff400/startup_corrected_timing_repair_003/masters.txt'
    load_receipt=ROOT/'build/signoff400/prototype_v3_FF_wire_loads_001/assessment.json'
    masters=sorted({x for x in inventory.read_text().split() if '__dfrtp_' in x or '__dfstp_' in x})
    if {m.split('__')[1] for m in masters}!=set(LOADS):raise ValueError('master coverage changed')
    pins={str(p):sha(p) for p in (PROFILE,worker,assessor,inventory,load_receipt,Path(__file__).resolve(),Path(__file__).with_name('run_prototype_capture_campaign.py'))}
    points=[dict(corner=c,master=m,load_fF=LOADS[m.split('__')[1]],ramp_ps=ramp_ps) for c in spec()['corners'] for m in masters]
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,max_small_cell_workers=4,automatic_identical_retry=False))
    save(output/'input_manifest.json',dict(input_sha256=pins,points=points,
        purpose='higher_load_observations_above_measured_wire_only_maxima',
        receiver_pin_and_parent_load_bound_proven=False,temperature_c=27,supply_v=1.8))
    save(output/'status.json',dict(state='capture_load_campaign_running',completed_points=0,failed_points=0,release_ready=False))
    def point(row):
        folder=output/(row['corner']+'_'+row['master'].split('__')[1]);log=output/(folder.name+'.log')
        command=[sys.executable,str(worker),'--corner',row['corner'],'--master',row['master'],'--load-fF',str(row['load_fF']),'--ramp-ps',str(ramp_ps),'--output',str(folder)]
        remaining=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if remaining<=0:raise TimeoutError('capture campaign deadline')
        with log.open('x') as stream:
            completed=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=remaining)
        if completed.returncode:raise ValueError('capture worker failed: '+str(folder))
        native=review(folder)
        receipt=json.loads((folder/'assessment.json').read_text())
        if receipt['output_load_fF']!=row['load_fF'] or receipt['input_slew_ps']!=ramp_ps:raise ValueError('native load/ramp mismatch')
        wave=output/(folder.name+'_waveforms');waveform_review(folder,wave)
        wp=wave/'assessment.json';wr=json.loads(wp.read_text())
        if wr['waveforms']!=21 or not wr['all_separated_control_output_crossings_pass']:raise ValueError('capture waveform control failed')
        return dict(**row,native=native,waveform_assessment=str(wp),waveform_sha256=sha(wp),waveforms=wr['waveforms'])
    results=[];failures=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(point,row):row for row in points}
        for future in as_completed(futures):
            try:results.append(future.result())
            except Exception as exc:failures.append(dict(point=futures[future],reason=repr(exc)))
            save(output/'status.json',dict(state='capture_load_campaign_running',completed_points=len(results),failed_points=len(failures),release_ready=False))
    verify(pins)
    detail=output/'points.json';save(detail,dict(results=results,failures=failures))
    complete=len(results)==len(points) and not failures and {(r['corner'],r['master']) for r in results}=={(r['corner'],r['master']) for r in points}
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},required_points=len(points),completed_points=len(results),
        all_declared_native_points_and_waveform_controls_pass=complete,reviewed_waveforms=sum(r['waveforms'] for r in results),
        full_ramp_ps=ramp_ps,load_fF_by_master=LOADS,receiver_pin_and_parent_load_bound_proven=False,
        setup_hold_recovery_removal_qualified=False,timing_load_envelope_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='capture_load_campaign_terminal',completed_points=len(results),failed_points=len(failures),release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--ramp-ps',type=int,choices=(200,500),required=True)
    a=p.parse_args();run(a.output.resolve(),a.ramp_ps)
