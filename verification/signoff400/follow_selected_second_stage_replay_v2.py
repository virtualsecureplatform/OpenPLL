"""Observe one original two-stage native case and replay its frozen RTL receiver."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity


def run(case,continuation,model,output):
    output.mkdir(parents=True,exist_ok=False)
    folder=Path(__file__).resolve().parent;image=ROOT/'build/apptainer/openpll-release-modern.sif'
    runner=folder/'replay_selected_receiver_cycles_v7.py'
    owner=json.loads((case/'owner.json').read_text())
    pins={str(p):sha(p) for p in [Path(__file__).resolve(),runner,continuation,model/'assessment.json',model/'parameters.json',image]}
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'inputs.json',dict(input_sha256=pins,case=str(case),original_owner=owner,automatic_native_launch=False,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+15000
    try:
        while True:
            state=json.loads((case/'status.json').read_text())['state']
            if state=='recorded_phase_response_measured':break
            if state=='stopped_without_qualification' or identity(owner['pid'])!=owner['birth']:raise RuntimeError('original native case stopped before completion')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observer deadline; original native unchanged')
            save(output/'status.json',dict(state='waiting_for_original_second_stage_case',release_ready=False));time.sleep(10)
        verify(pins)
        command=['apptainer','exec','--bind',f'{ROOT}:{ROOT}',image,'/usr/bin/python3',runner,
            '--case',case,'--inventory',ROOT/'build/signoff400/selected_detector_receiver_inventory_186.json',
            '--continuation',continuation,'--publication-model',model,'--output',output/'replay']
        with (output/'replay.log').open('x') as log:subprocess.run(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
        verify(pins);p=output/'replay/assessment.json';r=json.loads(p.read_text())
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)},
            first_stage_sampling_cycles_match=r['all_observed_sampling_cycles_match'],
            second_stage_sampling_cycles_match=r['all_observed_second_stage_sampling_cycles_match'],
            full_controller_timing_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='second_stage_receiver_replay_assessed',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['case','continuation','model','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['case','continuation','model','output']))
