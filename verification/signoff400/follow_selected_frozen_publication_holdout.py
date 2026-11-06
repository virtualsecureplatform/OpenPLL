"""Replay an independent holdout against a completed frozen publication model.

Wait for original work only. Never refit to the holdout or launch native jobs.
Both nominal and provisional late-window policies remain diagnostics.
"""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity


def run(producer,case,inventory,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{30})
    owners=[json.loads((d/'owner.json').read_text()) for d in [producer,case]]
    replay=Path(__file__).with_name('replay_selected_receiver_uncertainty.py');image=ROOT/'build/apptainer/openpll-release-modern.sif'
    files=[Path(__file__).resolve(),replay,inventory,image,producer/'inputs.json',producer/'owner.json',case/'owner.json']
    pins={str(f):sha(f) for f in files}
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'inputs.json',dict(input_sha256=pins,producer=str(producer),holdout=str(case),original_owners=owners,automatic_native_launch=False,refit_to_holdout=False,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+15000
    try:
        while True:
            pending=[]
            for d,owner,done in zip([producer,case],owners,['publication_training_measured','corner_detector_response_measured']):
                state=json.loads((d/'status.json').read_text())['state']
                if state==done:continue
                if state=='stopped_without_qualification' or identity(owner['pid'])!=str(owner['birth']):raise RuntimeError('original publication work stopped: '+str(d))
                pending.append(str(d))
            if not pending:break
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observer deadline; original workers unchanged')
            save(output/'status.json',dict(state='waiting_for_frozen_model_and_original_holdout',pending=pending,release_ready=False));time.sleep(10)
        verify(pins);model=producer/'model';params=model/'parameters.json';receipt=model/'assessment.json'
        p=json.loads(params.read_text());r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        expected=json.loads((producer/'inputs.json').read_text())['cases']
        if set(p['training_cases'])!=set(expected) or str(case) in p['training_cases'] or p['missing_directions']:raise ValueError('complete independent frozen training model required')
        pins.update({str(f):sha(f) for f in [params,receipt,case/'manifest.json',case/'response.json',case/'waveform_assessment/assessment.json']});verify(pins)
        reports=[]
        for policy in ['nominal','late_window']:
            command=['apptainer','exec','--bind',f'{ROOT}:{ROOT}',str(image),'/usr/bin/python3',str(replay),'--case',str(case),'--inventory',str(inventory),'--publication-model',str(model),'--capture-policy',policy,'--window-ps','100','--output',str(output/policy)]
            with (output/(policy+'.log')).open('x') as log:subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
            reports.append(output/policy/'assessment.json')
        verify(pins);values=[json.loads(f.read_text()) for f in reports]
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(f):sha(f) for f in reports},nominal_counts_and_cycles_match=values[0]['all_observed_sampling_cycles_match'],late_window_counts_and_cycles_match=values[1]['all_observed_sampling_cycles_match'],selected_layout_RTL_replayed=True,refit_to_holdout=False,provisional_window_ps=100,uniform_aperture_bound_qualified=False,complete_controller_timing_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='frozen_publication_holdout_assessed',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['producer','case','inventory','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['producer','case','inventory','output']))
