"""Compare bounded clock-source probes with terminal exact-source prefixes.

Verify sampled pin and detector edge times, decision signs, actual receiver
captures and input slews. Agreement at these controls is diagnostic, not a
uniform charge-error or detector-equivalence proof.
"""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity
from fit_selected_detector_diagnostic import observe,same_model


def compare(reference,candidate,response,tolerance_ps=1):
    old=json.loads(reference.read_text());new=json.loads(response.read_text())
    verify(old['input_sha256']);verify(old['artifacts']);verify(new['input_sha256'])
    a,b=observe(reference),observe(candidate);same_model([a,b]);stop=min(a['measured_end_ns'],b['measured_end_ns']);checks=[]
    for role in a['edges']:
        for edge in ['rising_ns','falling_ns']:
            x=[t for t in a['edges'][role][edge] if t<stop];y=[t for t in b['edges'][role][edge] if t<stop]
            differences=[abs(t-u)*1000 for t,u in zip(x,y)]
            checks.append(dict(role=role,edge=edge,reference_count=len(x),candidate_count=len(y),
                maximum_edge_difference_ps=max(differences,default=0),agrees=len(x)==len(y) and all(d<=tolerance_ps for d in differences)))
    first,second=old['cycles'][0],new['cycles'][0]
    phase=abs(first['measured_feedback_minus_reference_ps']-second['measured_feedback_minus_reference_ps'])
    capture=[]
    for role in ['up','dn']:
        x,y=first['capture'][role],second['capture'][role];diff=[abs(a-b) for a,b in zip(x['capture_latencies_ps'],y['capture_latencies_ps'])]
        counts=x['detector_rises']==y['detector_rises'] and x['event_toggles']==y['event_toggles'] and len(x['capture_latencies_ps'])==len(y['capture_latencies_ps'])
        capture.append(dict(role=role,counts_match=counts,maximum_capture_latency_difference_ps=max(diff,default=0),
            agrees=counts and x['one_toggle_per_detector_rise'] and y['one_toggle_per_detector_rise'] and all(d<=tolerance_ps for d in diff)))
    slew=[]
    for role in ['reference_pin','feedback_pin']:
        x=old['complete_10_90_rise_slews_ps'][role][0];y=new['measured_pin_clock_metrics'][role]['complete_10_90_rise_slews_ps'][0]
        slew.append(dict(role=role,difference_ps=abs(x-y),agrees=abs(x-y)<=tolerance_ps))
    agree=first['decision']==second['decision'] and phase<=tolerance_ps and all(c['agrees'] for c in checks+capture+slew)
    return dict(reference=str(reference),candidate=str(candidate),response=str(response),common_measured_window_ns=[0,stop],
        original_reference_budget_stopped=old['native_budget_stopped'],candidate_complete_80ns=True,
        first_event_decision_reference=first['decision'],first_event_decision_candidate=second['decision'],
        first_event_pin_phase_difference_ps=phase,edge_checks=checks,capture_checks=capture,slew_checks=slew,
        diagnostic_tolerance_ps=tolerance_ps,sampled_control_agrees=agree)


def run(cases,references,output,wait=False,assessments=None,responses=None):
    if len(cases)!=len(references) or not cases:raise ValueError('paired nonempty candidate and reference lists required')
    explicit=assessments is not None or responses is not None
    if explicit and (assessments is None or responses is None or len(assessments)!=len(cases) or len(responses)!=len(cases)):raise ValueError('paired recovered assessment and response paths required')
    output.mkdir(parents=True,exist_ok=False);save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    pins={str(p):sha(p) for p in [*references,Path(__file__).resolve(),Path(__file__).with_name('fit_selected_detector_diagnostic.py')]}
    owners=[json.loads((p/'owner.json').read_text()) for p in cases];deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+4800
    save(output/'inputs.json',dict(input_sha256=pins,cases=list(map(str,cases)),case_owners=owners,release_ready=False))
    try:
        while not explicit:
            complete=[]
            for case,owner in zip(cases,owners):
                state=json.loads((case/'status.json').read_text())['state'];done=state=='nearzero_conditional_response_measured';complete.append(done)
                if state=='stopped_without_qualification':raise RuntimeError('bounded-source probe stopped; inspect original native worker')
                if not done and identity(owner['pid'])!=owner['birth']:raise RuntimeError('probe owner exited without terminal response')
            if all(complete):break
            if not wait:raise ValueError('bounded-source probes still live')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observation deadline; original native probes unchanged')
            save(output/'status.json',dict(state='waiting_for_bounded_clock_controls',release_ready=False));time.sleep(10)
        verify(pins);records=[]
        for index,(case,reference) in enumerate(zip(cases,references)):
            assessment=assessments[index] if explicit else case/'waveform_assessment/assessment.json'
            response=responses[index] if explicit else case/'response.json'
            native=case/'native'
            if explicit:
                state=json.loads((native/'status.json').read_text())
                worker=json.loads((native/'native.process.json').read_text())
                if state['state']!='conditional_detector_probe_completed_assessment_pending' or identity(worker['pid'])==worker['birth']:raise ValueError('completed native worker required for recovered observations')
                av=json.loads(assessment.read_text());rv=json.loads(response.read_text())
                if av['input_sha256'].get(str(native/'manifest.json'))!=sha(native/'manifest.json') or rv['input_sha256'].get(str(assessment))!=sha(assessment):raise ValueError('recovered observations do not bind this completed native case')
                for path in [native/'status.json',native/'native.process.json']:pins[str(path)]=sha(path)
            m=json.loads((native/'manifest.json').read_text());verify(m['input_sha256'])
            if m.get('clock_sources_voltage_approximated') is not True or m.get('maximum_source_voltage_error_V')!=1e-6:raise ValueError('expected bounded 1 uV native source variant')
            records.append(compare(reference,assessment,response))
            for p in [assessment,response,native/'manifest.json']:pins[str(p)]=sha(p)
        verify(pins);agree=all(r['sampled_control_agrees'] for r in records)
        save(output/'assessment.json',dict(input_sha256=pins,records=records,all_sampled_controls_agree=agree,
            recovered_completed_native_observations=explicit,
            status='diagnostic_clock_simplification_controls_agree' if agree else 'diagnostic_clock_simplification_controls_disagree',
            voltage_derivative_equivalence_proven=False,charge_error_bounded=False,detector_response_equivalence_proven=False,
            full_phase_coverage_qualified=False,physical_models_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='bounded_clock_control_comparison_complete',all_sampled_controls_agree=agree,release_ready=False))
        print(json.dumps(dict(all_sampled_controls_agree=agree,controls=len(records))))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',action='append',type=Path,required=True);p.add_argument('--reference',action='append',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--wait',action='store_true');p.add_argument('--assessment',action='append',type=Path);p.add_argument('--response',action='append',type=Path)
    a=p.parse_args();os.sched_setaffinity(0,{31});run([p.resolve() for p in a.case],[p.resolve() for p in a.reference],a.output.resolve(),a.wait,[p.resolve() for p in a.assessment] if a.assessment else None,[p.resolve() for p in a.response] if a.response else None)
