"""Replay original target calibration with publication timing; never launch native work."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from selected_physical_rtl import source_pins
from selected_model_registry import validate
from resources import identity,lease


def run(pipeline,composition,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{28})
    owner=json.loads((pipeline/'owner.json').read_text());folder=Path(__file__).resolve().parent;image=ROOT/'build/apptainer/openpll-release-modern.sif'
    c=json.loads((composition/'assessment.json').read_text());verify(c['input_sha256']);verify(c['artifacts'])
    pins=source_pins();pins.update(c['input_sha256']);pins.update(c['artifacts']);pins.update({str(p):sha(p) for p in [Path(__file__).resolve(),folder/'run_selected_mixed_signal_v4.py',folder/'run_selected_mixed_signal_v5.py',folder/'selected_frequency_interpolation.py',folder/'selected_model_registry.py',image,pipeline/'owner.json',composition/'assessment.json']});verify(pins)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'inputs.json',dict(input_sha256=pins,original_owner=owner,pipeline=str(pipeline),composition=str(composition),automatic_native_launch=False,release_ready=False))
    registry=pipeline/'selected_interface/models.json';deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+176400
    try:
        while not registry.exists():
            state=json.loads((pipeline/'status.json').read_text())['state']
            if state=='stopped_without_qualification' or identity(owner['pid'])!=owner['birth']:raise RuntimeError('original pipeline stopped before registry')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observation deadline; original native untouched')
            save(output/'status.json',dict(state='waiting_for_original_native_calibration',release_ready=False));time.sleep(10)
        r=validate(json.loads(registry.read_text()))
        if r['analog']['operating_point']!=c['operating_point']:raise ValueError('composition operating point mismatch')
        points=[p for p in r['points'] if p['coarse']==20];point=min(points,key=lambda p:(abs(p['frequency_hz']-400e6),p['fine']))
        clock=Path(r['interface']['clock_timing']);detector=composition/'detector.v'
        # Record native analog lineage separately: the diagnostic composition does
        # not rewrite or pretend to be the registry's qualified interface.
        pins.update(r['analog']['input_sha256']);pins[str(registry)]=sha(registry);pins[str(clock)]=sha(clock)
        for p in points:pins[p['receipt']]=sha(Path(p['receipt']))
        verify(pins);save(output/'calibration_inputs.json',dict(input_sha256=pins,selected_measured_point=point,registry_interface_replaced_for_diagnostic=True,release_ready=False))
        reports=[]
        for kind in ['measured_only','linear_period','linear_frequency']:
            runner=folder/('run_selected_mixed_signal_v4.py' if kind=='measured_only' else 'run_selected_mixed_signal_v5.py');dest=output/kind
            command=['apptainer','exec','--bind',f'{ROOT}:{ROOT}',image,'/usr/bin/python3',runner,'--detector',detector,'--clock-timing',clock,'--output',dest,'--coarse',20,'--seed',point['fine'],'--ki',4,'--kp',0,'--polarity',1,'--scenario',0,'--phase-ns',0]
            for p in points:command += ['--point',p['receipt']]
            if kind!='measured_only':command += ['--interpolation',kind]
            save(output/'status.json',dict(state='publication_calibration_diagnostic_running',variant=kind,release_ready=False))
            with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+1200):
                with (output/(kind+'.log')).open('x') as log:result=subprocess.run(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,timeout=180)
            report=dest/'assessment.json'
            if result.returncode not in [0,1,3] or not report.exists():raise RuntimeError('diagnostic failed without an assessment')
            x=json.loads(report.read_text());reports.append(dict(variant=kind,assessment=str(report),sha256=sha(report),state=x['state'],measurement_requests=x['measurement_requests'],functional_trace_pass=x['functional_trace_pass']))
            verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={x['assessment']:x['sha256'] for x in reports},reports=reports,selected_measured_point=point,interpolation_error_bound_qualified=False,native_correlated_controller_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='publication_calibration_diagnostics_assessed',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['pipeline','composition','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['pipeline','composition','output']))
