"""Collect conditional corner frequency and clock-edge guide measurements."""
import argparse,bisect,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from assess_selected_detector_prefix import read_prefix
from assess_selected_detector_phase_probe_v4 import transitions
from selected_spice_device_conditions import read as conditions


def run(cases,output):
    if not cases or len(set(cases))!=len(cases):raise ValueError('distinct nonempty original corner cases required')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29})
    owners=[json.loads((p/'owner.json').read_text()) for p in cases]
    files=[Path(__file__).resolve(),Path(__file__).with_name('assess_selected_detector_prefix.py'),Path(__file__).with_name('assess_selected_detector_phase_probe_v4.py'),Path(__file__).with_name('selected_spice_device_conditions.py')]
    pins={str(p):sha(p) for p in files}
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'inputs.json',dict(input_sha256=pins,cases=list(map(str,cases)),original_owners=owners,automatic_native_launch=False,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+12600
    try:
        while True:
            pending=[]
            for p,owner in zip(cases,owners):
                state=json.loads((p/'status.json').read_text())['state']
                if state=='real_driver_DCO_diagnostic_complete':continue
                if state=='stopped_without_qualification' or identity(owner['pid'])!=owner['birth']:raise RuntimeError('original corner guide stopped before normal completion: '+str(p))
                pending.append(str(p))
            if not pending:break
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observation deadline; original native cases unchanged')
            save(output/'status.json',dict(state='waiting_for_original_corner_guides',pending=pending,release_ready=False));time.sleep(10)
        records=[]
        with lease(1,2,deadline):
            for p in cases:
                m=json.loads((p/'manifest.json').read_text());a=json.loads((p/'assessment.json').read_text());verify(m['input_sha256']);verify(a['artifacts'])
                if conditions(p/'control.spice')['corner']!=m['operating_point']['corner']:raise ValueError('native deck corner and manifest differ')
                if m['exterior_bias_source_operating_point']['corner']!='tt' or m['full_corner_exterior_bias_qualified'] is not False:raise ValueError('explicit conditional exterior bias scope required')
                worker=json.loads((p/'native.process.json').read_text())
                if identity(worker['pid'])==worker['birth']:raise ValueError('native worker remains live')
                roles=list(m['observed_roles']);rows,info=read_prefix(p/'control.raw',m['observed_roles'])
                if info['declared_samples']!=len(rows) or info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-60e-9)>1e-18:raise ValueError('complete finite 60 ns output required')
                root=transitions(rows,roles.index('oscillator')+1);clocks={}
                for role in ['first_sync_clock','feedback_driver_clock','second_sync_clock','inverted_aux_clock','aux_clock']:
                    source_edge='falling_ns' if role=='inverted_aux_clock' else 'rising_ns';edge_times=root[source_edge]
                    targets=transitions(rows,roles.index(role)+1)['rising_ns'];delays=[]
                    for t in targets:
                        if not 20<=t<=60:continue
                        i=bisect.bisect_left(edge_times,t)-1
                        if i<0:raise ValueError('causal preceding root edge missing')
                        delays.append((t-edge_times[i])*1000)
                    if len(delays)<3:raise ValueError('at least three clock/root pairs required')
                    clocks[role]=dict(source_edge=source_edge,paired_rising_edges=len(delays),minimum_relative_delay_ps=min(delays),maximum_relative_delay_ps=max(delays),mean_relative_delay_ps=sum(delays)/len(delays))
                for name in ['manifest.json','assessment.json','control.raw','control.spice']:pins[str(p/name)]=sha(p/name)
                records.append(dict(case=str(p),retained_device_operating_point=m['operating_point'],exterior_bias_operating_point=m['exterior_bias_source_operating_point'],controls=m['controls'],frequency=a['frequency'],clock_edge_guides=clocks))
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,records=records,measurement_window_ns=[20,60],
            clock_edge_association='nearest preceding root edge of declared polarity; unwrapped causal latency remains unqualified',
            conditional_guidance_only=True,full_corner_calibration_qualified=False,physical_models_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='conditional_corner_guides_measured',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run([p.resolve() for p in a.case],a.output.resolve())
