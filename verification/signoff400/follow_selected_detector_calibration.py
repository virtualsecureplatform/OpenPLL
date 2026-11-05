"""After a measured point attaches, rerun actual RTL with the selected detector.

Observe the original calibration; never restart it or launch another native
job. Unsupported tuning codes stay explicit measurement requests.
"""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify,source_pins
from resources import identity,lease
from bind_selected_detector_registry import run as bind_detector
from run_selected_mixed_signal_v3 import run as run_loop


def run(advance,fit,clock_timing,output):
    output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));owner=json.loads((advance/'owner.json').read_text())
    paths=[fit/'assessment.json',fit/'detector.v',fit/'parameters.json',clock_timing,Path(__file__).resolve(),Path(__file__).with_name('bind_selected_detector_registry.py'),Path(__file__).with_name('run_selected_mixed_signal_v3.py')]
    pins=source_pins();pins.update({str(p):sha(p) for p in paths})
    save(output/'inputs.json',dict(input_sha256=pins,registry_advance_owner=owner,automatic_native_launch=False,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+172800
    try:
        while True:
            state=json.loads((advance/'status.json').read_text())['state']
            if state=='calibration_attached_next_measurement_requested':break
            if state=='stopped_without_qualification':raise RuntimeError('original calibration registry advancement failed')
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('registry advancement owner exited without terminal receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observation deadline; original native calibration unchanged')
            save(output/'status.json',dict(state='waiting_for_measured_calibration_attachment',release_ready=False));time.sleep(10)
        verify(pins);a=json.loads((advance/'assessment.json').read_text());verify(a['input_sha256']);verify(a['artifacts'])
        os.sched_setaffinity(0,{29})
        with lease(1,4,deadline):
            save(output/'status.json',dict(state='binding_selected_detector_and_running_actual_RTL',release_ready=False))
            bind_detector(advance/'models.json',fit,clock_timing,output/'registry')
            registry=output/'registry/models.json';r=json.loads(registry.read_text())
            report=run_loop([Path(p['receipt']) for p in r['points']],fit/'detector.v',output/'loop',
                ki=4,kp=0,coarse=20,seed=111,polarity=1,scenario=0,phase_ns=0,registry_path=registry,clock_timing_path=clock_timing)
        verify(pins)
        if report['state'] not in ['needs_native_tuning_points','diagnostic_simulation_completed']:raise RuntimeError('diagnostic RTL trace did not complete or request a measured point')
        save(output/'assessment.json',dict(input_sha256=dict(pins,**{str(advance/'assessment.json'):sha(advance/'assessment.json')}),
            artifacts={str(p):sha(p) for p in [registry,output/'registry/assessment.json',output/'loop/assessment.json']},
            state=report['state'],measurement_requests=report['measurement_requests'],measured_points=len(r['points']),
            diagnostic=True,physical_models_qualified=False,lock_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='selected_detector_RTL_rerun_assessed',measurement_requests=report['measurement_requests'],release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['advance','fit','clock-timing','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n.replace('-','_')).resolve() for n in ['advance','fit','clock-timing','output']))
