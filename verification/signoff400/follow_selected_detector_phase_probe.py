"""Assess one normally completed detector probe; never restart a native job."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from assess_selected_detector_phase_probe import run as assess


def run(probe,ports,inventory,output):
    output.mkdir(parents=True,exist_ok=False)
    owner=json.loads((probe/'owner.json').read_text())
    pins={str(p):sha(p) for p in [ports,inventory,Path(__file__).resolve(),Path(__file__).with_name('assess_selected_detector_phase_probe.py')]}
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+7200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='waiting_for_conditional_detector_probe',release_ready=False))
    try:
        while True:
            state=json.loads((probe/'status.json').read_text())['state']
            if state=='conditional_detector_probe_completed_assessment_pending':break
            if state not in ['preparing_conditional_detector_phase_probe','conditional_detector_native_running']:raise RuntimeError('probe did not complete normally: '+state)
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('probe owner exited without normal terminal status')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>deadline:raise TimeoutError('observation budget exhausted; inspect original probe without restarting')
            time.sleep(5)
        verify(pins)
        save(output/'status.json',dict(state='assessing_completed_detector_probe',release_ready=False))
        os.sched_setaffinity(0,{27})
        with lease(1,2,deadline):assess(probe,ports,inventory,output/'waveform_assessment')
        verify(pins);save(output/'provenance.json',dict(input_sha256=pins,release_ready=False))
        save(output/'status.json',dict(state='conditional_detector_phase_assessed',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['probe','ports','inventory','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['probe','ports','inventory','output']))
