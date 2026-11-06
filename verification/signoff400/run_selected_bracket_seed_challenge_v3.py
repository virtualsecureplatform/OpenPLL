"""Fast, finite startup-seed sensitivity within the measured TT bracket.

Uses measured seeds, actual selected RTL, two diagnostic publication views and
both interpolation laws. Missing coverage remains explicit. This experiment
does not select a release gain or qualify capture under uncertainty.
"""
import json
import itertools
import os
import subprocess
import time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from compose_selected_diagnostic_registry import compose
from resources import identity,lease


def run(output, gains, cpu):
    from common_v3 import spec
    grid=spec()['gain_search']
    if not gains or len(set(gains))!=len(gains) or any(ki not in grid['ki'] or kp not in grid['kp'] for ki,kp in gains):raise ValueError('distinct declared KI/KP pairs required')
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{cpu})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    base=ROOT/'build/signoff400/selected_upper_calibration_pipeline_463/selected_interface/models.json'
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    worker=Path(__file__).with_name('run_selected_mixed_signal_v6.py')
    clock=ROOT/'build/signoff400/selected_clock_phase_observations_187.json'
    views=[('nominal',ROOT/'build/signoff400/selected_root_publication_detector_407',ROOT/'build/signoff400/selected_nominal_RTL_build_cache_778'),
           ('receiver',ROOT/'build/signoff400/selected_receiver_stress_detector_450',ROOT/'build/signoff400/selected_stress_RTL_build_cache_788')]
    pins={str(p):sha(p)for p in [Path(__file__).resolve(),base,image,worker,clock,Path(__file__).with_name('compose_selected_diagnostic_registry.py')]}
    cases=[]
    try:
        for name,composition,cache in views:
            pins.update({str(p):sha(p)for p in [composition/'assessment.json',cache/'assessment.json']})
            compose(base,composition,output/(name+'_models.json'))
        save(output/'inputs.json',dict(input_sha256=pins,measured_startup_seeds=[133,165],gain_pairs=[list(g)for g in gains],expected_cases=8*len(gains),
            native_launches=0,release_gain_selection=False,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
        for (ki,kp),seed,(view,composition,cache),kind in itertools.product(gains,[133,165],views,['linear_period','linear_frequency']):
            verify(pins)
            case=output/f'{view}_ki{ki}_kp{kp}_seed{seed}_{kind}'
            save(output/'status.json',dict(state='bracket_seed_case_running',case=case.name,completed_cases=len(cases),release_ready=False))
            command=['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,'python3',worker,
                '--registry',output/(view+'_models.json'),'--detector',composition/'detector.v','--clock-timing',clock,
                '--build-cache',cache,'--output',case,'--seed',seed,'--coarse',20,'--ki',ki,'--kp',kp,
                '--polarity',1,'--scenario',0,'--phase-ns',0,'--interpolation',kind]
            with lease(1,4,deadline):
                with (output/(case.name+'.log')).open('x')as log:
                    result=subprocess.run(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,timeout=180)
            receipt=case/'assessment.json';report=json.loads(receipt.read_text())
            if result.returncode not in [0,1,3]:raise ValueError('case stopped without ordinary assessment')
            cases.append(dict(ki=ki,kp=kp,seed=seed,view=view,interpolation=kind,assessment=str(receipt),assessment_sha256=sha(receipt),
                state=report['state'],functional_trace_pass=report['functional_trace_pass'],measurement_requests=report['measurement_requests']))
            save(output/'cases.json',cases)
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'cases.json'):sha(output/'cases.json')},
            completed_cases=len(cases),expected_cases=8*len(gains),full_phase_scenario_matrix=False,common_gain_selected=False,
            native_launches=0,capture_under_uncertainty_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='bracket_seed_challenge_assessed',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--gain',nargs=2,type=int,action='append',required=True);p.add_argument('--cpu',type=int,choices=[23,24],required=True);a=p.parse_args();run(a.output.resolve(),[tuple(g)for g in a.gain],a.cpu)
