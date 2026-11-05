"""Measure physical pin phase, slew, and event capture in a conditional probe.

Commanded source offsets are never substituted for measured detector-pin phase.
Both rising and falling event-toggle edges count as captures.
"""
import argparse,bisect,csv,json,math
from pathlib import Path
from common_v3 import save,sha,verify
from assess_selected_detector_phase_probe_v2 import transitions


def pair_phases(reference,feedback,period_ns=40):
    pairs=[];used=set()
    for r in reference:
        candidates=sorted((abs(f-r),i,f) for i,f in enumerate(feedback) if abs(f-r)<period_ns/2)
        if not candidates or (len(candidates)>1 and abs(candidates[0][0]-candidates[1][0])<1e-9):raise ValueError('missing or ambiguous feedback edge')
        _,index,f=candidates[0]
        if index in used:raise ValueError('feedback edge reused across reference cycles')
        used.add(index);pairs.append((r,f))
    return pairs


def rise_slews(rows,column):
    low=transitions(rows,column,.18);high=transitions(rows,column,1.62)['rising_ns'];result=[]
    for finish in high:
        index=bisect.bisect_left(low['rising_ns'],finish)-1
        if index<0:continue
        start=low['rising_ns'][index]
        if any(start<t<finish for t in low['falling_ns']):continue
        result.append((finish-start)*1000)
    return result


def cycle_capture(detector,events,start,stop):
    rises=[t for t in detector['rising_ns'] if start<=t<stop]
    toggles=sorted(t for direction in ['rising_ns','falling_ns'] for t in events[direction] if start<=t<stop)
    latencies=[(t-r)*1000 for r,t in zip(rises,toggles)]
    return dict(detector_rises=len(rises),event_toggles=len(toggles),
                capture_latencies_ps=latencies,
                one_toggle_per_detector_rise=len(rises)==len(toggles) and all(v>=0 for v in latencies))


def run(assessment,receivers,output):
    if output.exists():raise FileExistsError(output)
    a=json.loads(assessment.read_text());rv=json.loads(receivers.read_text())
    verify(a['input_sha256']);verify(a['artifacts']);verify(rv['input_sha256'])
    # Bind receivers to the exact pin inventory already used by the native assessor.
    shared={p:d for p,d in rv['input_sha256'].items() if p in a['input_sha256']}
    if not shared or any(a['input_sha256'][p]!=d for p,d in shared.items()):raise ValueError('receiver/native physical pin identity mismatch')
    csv_paths=[Path(p) for p in a['artifacts'] if p.endswith('/signals.csv')]
    if len(csv_paths)!=1:raise ValueError('one assessed waveform CSV required')
    with csv_paths[0].open() as f:
        reader=csv.reader(f);names=next(reader);rows=[[float(v) for v in row] for row in reader]
    if not rows or any(len(row)!=len(names) or not all(math.isfinite(v) for v in row) for row in rows) or rows[0][0]!=0 or any(b[0]<=a[0] for a,b in zip(rows,rows[1:])):raise ValueError('finite ordered complete waveform required')
    if abs(rows[-1][0]-80e-9)>1e-18:raise ValueError('incomplete probe duration')
    edges={role:transitions(rows,i) for i,role in enumerate(names) if i>0}
    def observed_role(node):
        roles=[role for role,o in a['observations'].items() if o['node']==node]
        if len(roles)!=1:raise ValueError('unique observed receiver output required')
        return roles[0]
    mapping={}
    for role,port in [('up','BBPD[1]'),('dn','BBPD[0]')]:
        key=rv['roles'][port]['event_clock_receiver']
        cell=next(c for c in rv['selected_cells'] if c['cell_key']==key)
        mapping[role]=observed_role(cell['pins']['Q'])
    global_capture={role:cycle_capture(edges['detector_'+role],edges[event],10,80) for role,event in mapping.items()}
    metrics={};cycles=[];missing=[r for r in ['reference_pin','feedback_pin'] if r not in names]
    if not missing:
        for role in ['reference_pin','feedback_pin']:
            metrics[role]=dict(complete_10_90_rise_slews_ps=rise_slews(rows,names.index(role)))
        for reference,feedback in pair_phases(edges['reference_pin']['rising_ns'],edges['feedback_pin']['rising_ns']):
            start=min(reference,feedback);stop=start+20
            captures={role:cycle_capture(edges['detector_'+role],edges[event],start,stop) for role,event in mapping.items()}
            active=[role for role,c in captures.items() if c['detector_rises']]
            cycles.append(dict(reference_rise_ns=reference,feedback_rise_ns=feedback,
                measured_feedback_minus_reference_ps=(feedback-reference)*1000,
                decision=active[0] if len(active)==1 else 'both' if active else 'none',capture=captures))
    result=dict(input_sha256={str(p):sha(p) for p in [assessment,receivers,csv_paths[0],Path(__file__).resolve(),Path(__file__).with_name('assess_selected_detector_phase_probe_v2.py')]},
        commanded_driver_offset_ns=a['phase_50_percent_crossing_offset_ns'],missing_physical_input_observations=missing,
        measured_pin_clock_metrics=metrics,cycles=cycles,global_capture=global_capture,
        event_observation_roles=mapping,physical_pin_phase_measured=not missing,
        conditional_response_only=True,receiver_loading_bounded=False,exterior_condition_validated=False,
        detector_fit_qualified=False,release_ready=False)
    save(output,result);print(json.dumps({k:result[k] for k in ['cycles','global_capture','missing_physical_input_observations']}))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['assessment','receivers','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['assessment','receivers','output']))
