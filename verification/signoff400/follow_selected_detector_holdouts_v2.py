"""Observe original detector cases and check a frozen fit; never restart native jobs."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity


def run(cases,fit,output):
    if not cases or len(set(cases))!=len(cases):raise ValueError('distinct nonempty cases required')
    output.mkdir(parents=True,exist_ok=False)
    folder=Path(__file__).resolve().parent
    checker=folder/'check_selected_frozen_detector_holdout_v2.py'
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    paths=[Path(__file__).resolve(),checker,folder/'selected_detector_level_observations.py',
           folder/'fit_selected_detector_diagnostic.py',image,fit/'assessment.json',fit/'parameters.json',fit/'detector.v']
    owners=[json.loads((case/'owner.json').read_text()) for case in cases]
    pins={str(p):sha(p) for p in paths};verify(pins)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'inputs.json',dict(input_sha256=pins,cases=list(map(str,cases)),owners=owners,automatic_native_launch=False,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+15000
    try:
        while True:
            pending=[]
            for case,owner in zip(cases,owners):
                state=json.loads((case/'status.json').read_text())['state']
                if state in ['recorded_phase_response_measured','nearzero_conditional_response_measured','corner_detector_response_measured']:continue
                if state=='stopped_without_qualification':raise RuntimeError(f'original case stopped: {case}')
                if identity(owner['pid'])!=owner['birth']:raise RuntimeError(f'case owner exited without completion: {case}')
                pending.append(str(case))
            if not pending:break
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observation deadline; original native cases unchanged')
            save(output/'status.json',dict(state='waiting_for_original_recorded_phase_cases',pending=pending,release_ready=False))
            time.sleep(10)
        verify(pins)
        command=['apptainer','exec','--bind',f'{ROOT}:{ROOT}',image,'/usr/bin/python3',checker,
                 '--fit',fit,'--output',output/'holdouts']
        for case in cases:command.extend(['--assessment',case/'waveform_assessment/assessment.json'])
        save(output/'status.json',dict(state='checking_frozen_detector_fit',release_ready=False))
        with (output/'check.log').open('x') as log:
            subprocess.run(list(map(str,command)),check=True,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
        verify(pins)
        report=output/'holdouts/assessment.json';value=json.loads(report.read_text())
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(report):sha(report)},
             all_sampled_signs_match=value['all_sampled_signs_match'],all_event_counts_match=value['all_event_counts_match'],
             all_edges_within_observed_fit_band=value['all_edges_within_observed_fit_band'],
             parameters_refitted=False,full_phase_coverage_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='recorded_phase_holdouts_assessed',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',type=Path,action='append',required=True)
    for name in ['fit','output']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run([p.resolve() for p in args.case],args.fit.resolve(),args.output.resolve())
