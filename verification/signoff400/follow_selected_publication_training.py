"""Collect original native publication training cases without implying holdout validation."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease


def run(cases,inventory,output):
    if not cases or len(set(cases))!=len(cases):raise ValueError('distinct original training cases required')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29});owners=[json.loads((p/'owner.json').read_text()) for p in cases]
    image=ROOT/'build/apptainer/openpll-release-modern.sif';fitter=Path(__file__).with_name('fit_selected_publication_model.py');files=[Path(__file__).resolve(),fitter,inventory,image]+[p/'owner.json' for p in cases];pins={str(p):sha(p) for p in files}
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));save(output/'inputs.json',dict(input_sha256=pins,cases=list(map(str,cases)),original_owners=owners,automatic_native_launch=False,independent_holdout_validated=False,release_ready=False));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+15000
    try:
        while True:
            pending=[]
            for p,owner in zip(cases,owners):
                state=json.loads((p/'status.json').read_text())['state']
                if state=='corner_detector_response_measured':continue
                if state=='stopped_without_qualification' or identity(owner['pid'])!=owner['birth']:raise RuntimeError('original native training case stopped: '+str(p))
                pending.append(str(p))
            if not pending:break
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observer deadline; original native unchanged')
            save(output/'status.json',dict(state='waiting_for_original_publication_training',pending=pending,release_ready=False));time.sleep(10)
        verify(pins);command=['apptainer','exec','--bind',f'{ROOT}:{ROOT}',str(image),'/usr/bin/python3',str(fitter),'--inventory',str(inventory),'--output',str(output/'model')]
        for p in cases:command += ['--case',str(p)]
        with lease(1,2,deadline):
            with (output/'fit.log').open('x') as log:subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
        verify(pins);report=output/'model/assessment.json';r=json.loads(report.read_text())
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(report):sha(report)},direction_coverage_complete=r['direction_coverage_complete'],independent_holdout_validated=False,full_controller_timing_qualified=False,release_ready=False));save(output/'status.json',dict(state='publication_training_measured',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',type=Path,action='append',required=True)
    for n in ['inventory','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run([p.resolve() for p in a.case],a.inventory.resolve(),a.output.resolve())
