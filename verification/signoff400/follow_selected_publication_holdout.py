"""Fit completed training cases, then replay disjoint holdouts; never launch native."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity


def run(training,holdouts,inventory,output):
    cases=training+holdouts
    if not training or not holdouts or len(set(cases))!=len(cases):
        raise ValueError('nonempty distinct training and independent holdout cases required')
    folder=Path(__file__).resolve().parent
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    files=[Path(__file__).resolve(),image,inventory]+[folder/name for name in [
        'fit_selected_publication_model.py','selected_publication_delivery.py',
        'replay_selected_receiver_cycles_v4.py']]
    pins={str(p):sha(p) for p in files}
    owners=[json.loads((c/'owner.json').read_text()) for c in cases]
    output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'inputs.json',dict(input_sha256=pins,training=list(map(str,training)),
        holdouts=list(map(str,holdouts)),owners=owners,automatic_native_launch=False,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+15000
    try:
        while True:
            pending=[]
            for case,owner in zip(cases,owners):
                state=json.loads((case/'status.json').read_text())['state']
                if state in ['nearzero_conditional_response_measured','recorded_phase_response_measured','corner_detector_response_measured']:continue
                if state=='stopped_without_qualification' or identity(owner['pid'])!=owner['birth']:
                    raise RuntimeError(f'original case stopped before completion: {case}')
                pending.append(str(case))
            if not pending:break
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observer deadline; native jobs untouched')
            save(output/'status.json',dict(state='waiting_for_original_publication_cases',pending=pending,release_ready=False))
            time.sleep(10)
        verify(pins)
        prefix=['apptainer','exec','--bind',f'{ROOT}:{ROOT}',image,'/usr/bin/python3']
        command=prefix+[folder/'fit_selected_publication_model.py','--inventory',inventory,'--output',output/'model']
        for case in training:command+=['--case',case]
        with (output/'fit.log').open('x') as log:
            subprocess.run(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
        model=json.loads((output/'model/parameters.json').read_text())
        if model['missing_directions']:raise ValueError('training still lacks publication directions')
        reports=[]
        for i,case in enumerate(holdouts):
            destination=output/f'holdout_{i}'
            command=prefix+[folder/'replay_selected_receiver_cycles_v4.py','--inventory',inventory,
                '--publication-model',output/'model','--case',case,'--output',destination]
            with (output/f'holdout_{i}.log').open('x') as log:
                subprocess.run(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
            report=destination/'assessment.json';reports.append(report)
        verify(pins)
        passed=all(json.loads(p.read_text())['all_observed_sampling_cycles_match'] for p in reports)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in reports},
            all_independent_first_stage_cycles_match=passed,direction_coverage_complete=True,
            full_controller_timing_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='publication_holdouts_assessed',observed_checks_passed=passed,release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['training','holdout']:p.add_argument('--'+name,type=Path,action='append',required=True)
    for name in ['inventory','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run([c.resolve() for c in a.training],[c.resolve() for c in a.holdout],a.inventory.resolve(),a.output.resolve())
