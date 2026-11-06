"""Replay completed calibration with physical-candidate RTL; never restart native."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from selected_physical_rtl import source_pins
from selected_model_registry import validate
from resources import identity


def run(pipeline,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{27})
    owner=json.loads((pipeline/'owner.json').read_text());folder=Path(__file__).resolve().parent
    runner=folder/'run_selected_mixed_signal_v4.py';image=ROOT/'build/apptainer/openpll-release-modern.sif'
    pins=source_pins();pins.update({str(p):sha(p) for p in [Path(__file__).resolve(),runner,image,pipeline/'owner.json',folder/'selected_model_registry.py']});verify(pins)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'inputs.json',dict(input_sha256=pins,original_pipeline=str(pipeline),original_owner=owner,automatic_native_launch=False,release_ready=False))
    registry=pipeline/'selected_interface/models.json';deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+176400
    try:
        while not registry.exists():
            state=json.loads((pipeline/'status.json').read_text())['state']
            if state=='stopped_without_qualification' or identity(owner['pid'])!=owner['birth']:raise RuntimeError('original pipeline stopped before calibration attachment')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observer deadline; native pipeline untouched')
            save(output/'status.json',dict(state='waiting_for_original_calibration_registry',release_ready=False));time.sleep(10)
        r=validate(json.loads(registry.read_text()));point=min((p for p in r['points'] if p['coarse']==20),key=lambda p:(abs(p['frequency_hz']-400e6),p['fine']))
        interface=r['interface'];detector=Path(interface['detector_rtl']);clock=Path(interface['clock_timing'])
        if interface['input_sha256'].get(str(detector))!=sha(detector) or interface['input_sha256'].get(str(clock))!=sha(clock):raise ValueError('pinned measured interface required')
        pins[str(registry)]=sha(registry);verify(pins)
        command=['apptainer','exec','--bind',f'{ROOT}:{ROOT}',image,'/usr/bin/python3',runner,'--registry',registry,
            '--detector',detector,'--clock-timing',clock,'--output',output/'loop','--coarse',20,'--seed',point['fine'],
            '--ki',4,'--kp',0,'--polarity',1,'--scenario',0,'--phase-ns',0]
        save(output/'status.json',dict(state='physical_candidate_RTL_replay_running',selected_measured_seed=point['fine'],release_ready=False))
        with (output/'run.log').open('x') as log:result=subprocess.run(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,timeout=1200)
        if result.returncode not in [0,3]:raise RuntimeError('physical-candidate replay failed; inspect original report')
        verify(pins);report=output/'loop/assessment.json';r=json.loads(report.read_text())
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(report):sha(report)},selected_measured_point=point,
            RTL_state=r['state'],measurement_requests=r['measurement_requests'],physical_RTL_binding_verified=True,
            native_correlated_controller_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='physical_candidate_calibration_replay_assessed',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['pipeline','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.pipeline.resolve(),a.output.resolve())
