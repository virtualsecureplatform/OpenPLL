"""Prospectively declare coarse23 endpoints and a separate holdout, with bounded admission."""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from common_v3 import ROOT, save, sha, verify
from resources import identity
from queue_keeper_coarse19_endpoints import wait_complete
from queue_keeper_coarse23_center import BACKEND
from run_keeper_native_BSIM_coarse_band import run as capture
from assess_keeper_physical_tuning_v2 import run as physical
from collect_keeper_TT_characterization import characterize


def cases():
    b = ROOT / 'build/signoff400'
    return [(8,17,b/'selected_keeper_coarse23_fine8_step50_1516',b/'selected_keeper_coarse23_fine8_physical_1517'),
            (247,18,b/'selected_keeper_coarse23_fine247_step50_1518',b/'selected_keeper_coarse23_fine247_physical_1519'),
            (198,23,b/'selected_keeper_coarse23_fine198_step50_1520',b/'selected_keeper_coarse23_fine198_physical_1521')]


def checked_point(n,p,domain,fine):
    if (domain.get('corner'),domain.get('temperature_C'),domain.get('supply_V'),
            domain.get('coarse'),domain.get('fine'),domain.get('max_step_ps'),domain.get('simulation_ns')) != ('tt',27,1.8,23,fine,50,260):
        raise ValueError('same predeclared TT operating domain required')
    if (n.get('normal_native_completion') is not True or n.get('all_saved_native_values_finite') is not True
            or n.get('stationary_requested_code') is not True
            or n.get('native_executable_sha256') != BACKEND
            or n.get('BSIM_PBSWGD_default_corrected') is not True
            or n.get('codes') != {'COARSE_CODE':[23],'DCO_CODE':[fine]}):
        raise ValueError('normal finite stationary corrected capture required')
    if (p.get('all_macro_and_DCO_tuning_bits_match') is not True or p.get('mismatched_endpoints') != 0
            or p.get('observed_bits') != 302 or p.get('observed_endpoint_voltages') != 604
            or (p.get('coarse'),p.get('fine')) != (23,fine)):
        raise ValueError('matching complete physical tuning checks required')
    frequency=n.get('frequency_diagnostic')
    f=frequency.get('frequency_mhz') if isinstance(frequency,dict) else None
    if type(f) not in (int,float) or not math.isfinite(f) or f<=0:
        raise ValueError('positive finite native frequency required')
    return f


def load_point(native,controls,fine):
    nr,pr,ci = native/'assessment.json',controls/'assessment.json',native/'inputs.json'
    n,p,d = [json.loads(f.read_text()) for f in (nr,pr,ci)]
    for record in (n,p):
        verify(record['input_sha256'])
        verify(record['artifacts'])
    if p['input_sha256'].get(str(nr)) != sha(nr) or p['input_sha256'].get(str(ci)) != sha(ci):
        raise ValueError('physical controls must bind this native capture and domain')
    return dict(fine=fine,frequency_mhz=checked_point(n,p,d,fine),native_receipt=str(nr),
                physical_receipt=str(pr),receipt_sha256={str(f):sha(f) for f in (nr,pr,ci)})


def worker(output,fine):
    _,cpu,native,controls=next(row for row in cases() if row[0]==fine)
    if native.exists() or controls.exists():
        raise FileExistsError('one-shot worker refuses existing output')
    record=output/f'worker_{fine}.json'
    save(record,dict(pid=os.getpid(),birth=identity(os.getpid()),CPU=cpu,state='starting'))
    try:
        pins=json.loads((output/'plan.json').read_text())['input_sha256']
        verify(pins)
        b=ROOT/'build/signoff400'
        capture(b/'selected_keeper_flat_native_smoke_1210',native,fine,cpu,23,50)
        physical(native,b/'selected_keeper_DCO_control_drivers_1233',b/'selected_keeper_flat_native_model_1208',
                 b/'selected_keeper_parent_reroute_1136',controls,False,cpu=cpu)
        result=load_point(native,controls,fine)
        verify(pins)
        save(output/f'result_{fine}.json',result)
        save(record,dict(pid=os.getpid(),birth=identity(os.getpid()),CPU=cpu,state='complete'))
    except BaseException as error:
        save(record,dict(pid=os.getpid(),birth=identity(os.getpid()),CPU=cpu,state='stopped_without_qualification',reason=repr(error)))
        raise


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{19})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    b=ROOT/'build/signoff400'
    central=b/'selected_keeper_corrected_coarse23_fine149_step50_1513'
    center_controls=b/'selected_keeper_corrected_coarse23_physical_1514'
    coordinator=b/'selected_keeper_coarse23_central_campaign_1512'
    try:
        if (central/'assessment.json').exists() or any(p.exists() for _,_,n,c in cases() for p in (n,c)):
            raise ValueError('holdout and endpoints must be declared before central result and worker creation')
        names=['queue_keeper_coarse23_characterization.py','queue_keeper_coarse23_center.py',
               'queue_keeper_coarse19_endpoints.py','run_keeper_native_BSIM_coarse_band.py',
               'assess_keeper_physical_tuning_v2.py','collect_keeper_TT_characterization.py']
        pins={str(p):sha(p) for p in [coordinator/'plan.json',*[Path(__file__).with_name(n) for n in names]]}
        save(output/'plan.json',dict(input_sha256=pins,coarse=23,fit_fine_codes=[8,149,247],
             independent_holdout_fine=198,primary_interpolation='linear_frequency',sensitivity_interpolation='linear_period',
             central_admission_range_mhz=[380,420],CPUs=[17,18,23],native_memory_GiB_per_worker=16,
             maximum_additional_native_cases=3,total_band23_cases_including_central=4,max_step_ps=50,
             native_cap_s_per_case=86400,global_CPU_RAM_admission_unchanged=True,
             automatic_identical_retry=False,central_point_is_not_blind_holdout=True,
             target_extrapolation_forbidden=True,band_auto_selected=False,release_ready=False))
        save(output/'status.json',dict(state='waiting_for_completed_coarse23_center_and_physical_checks',release_ready=False))
        wait_complete(coordinator,time.clock_gettime(time.CLOCK_BOOTTIME)+172800)
        center=load_point(central,center_controls,149)
        if not 380<=center['frequency_mhz']<=420:
            save(output/'assessment.json',dict(input_sha256=pins,central=center,
                 admission_range_mhz=[380,420],additional_native_cases_started=0,
                 central_admission_pass=False,band_auto_selected=False,release_ready=False))
            save(output/'status.json',dict(state='central_result_outside_predeclared_campaign_admission',release_ready=False))
            return
        verify(pins)
        children=[]
        for fine,_,_,_ in cases():
            with (output/f'worker_{fine}.log').open('x') as log:
                child=subprocess.Popen([sys.executable,Path(__file__).resolve(),'--output',output,'--worker',str(fine)],stdout=log,stderr=subprocess.STDOUT)
            children.append((fine,child))
        save(output/'workers.json',dict(workers=[dict(fine=f,pid=c.pid,birth=identity(c.pid)) for f,c in children]))
        save(output/'status.json',dict(state='running_predeclared_endpoints_and_independent_holdout',release_ready=False))
        codes={fine:child.wait() for fine,child in children}
        if any(codes.values()):
            raise RuntimeError('one-shot worker failed; no identical retry: '+repr(codes))
        results={fine:json.loads((output/f'result_{fine}.json').read_text()) for fine,_,_,_ in cases()}
        results[149]=center
        for row in results.values():
            verify(row['receipt_sha256'])
        def point(fine,role):
            row=results[fine]
            return dict(fine=fine,frequency_hz=row['frequency_mhz']*1e6,role=role,
                        native_assessment=row['native_receipt'],physical_assessment=row['physical_receipt'])
        result=characterize([point(f,'fit') for f in (8,149,247)],point(198,'holdout'))
        pins.update({p:d for row in results.values() for p,d in row['receipt_sha256'].items()})
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,**result,coarse=23,corner='tt',
             corrected_backend=True,max_step_ps=50,primary_interpolation_predeclared='linear_frequency',
             independent_holdout_roles_preserved=True,target_extrapolation_used=False,
             numerical_accuracy_qualified=False,other_corners_qualified=False,
             changed_controller_prediction_qualified=False,model_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='coarse23_curve_and_independent_holdout_characterized',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--worker',type=int,choices=(8,247,198))
    args=parser.parse_args()
    (run(args.output.resolve()) if args.worker is None else worker(args.output.resolve(),args.worker))
