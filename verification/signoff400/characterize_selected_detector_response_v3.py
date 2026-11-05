"""Measure reference-centered detector events, including falling-edge apertures.

Do not force a bijection between REF and feedback rising edges: a drifting
clock or a first reference near a falling edge need not have one. Keep no/both
output decisions explicit and report actual nearest rise/fall coordinates.
"""
import argparse,bisect,csv,json,math
from pathlib import Path
from common_v3 import save,sha,verify
from assess_selected_detector_phase_probe_v4 import transitions
from characterize_selected_detector_response import cycle_capture,rise_slews


def nearest(edges,t):
    return None if not edges else min(edges,key=lambda e:(abs(e-t),e))-t


def falling_slews(rows,column):
    high=transitions(rows,column,1.62);low=transitions(rows,column,.18)['falling_ns'];result=[]
    for finish in low:
        index=bisect.bisect_left(high['falling_ns'],finish)-1
        if index<0:continue
        start=high['falling_ns'][index]
        if not any(start<t<finish for t in high['rising_ns']):result.append((finish-start)*1000)
    return result


def run(assessment,receivers,output):
    if output.exists():raise FileExistsError(output)
    a=json.loads(assessment.read_text());rv=json.loads(receivers.read_text());verify(a['input_sha256']);verify(a['artifacts']);verify(rv['input_sha256'])
    shared={p:d for p,d in rv['input_sha256'].items() if p in a['input_sha256']}
    if not shared or any(a['input_sha256'][p]!=d for p,d in shared.items()):raise ValueError('physical receiver/pin identity mismatch')
    paths=[Path(p) for p in a['artifacts'] if p.endswith('/signals.csv')]
    if len(paths)!=1:raise ValueError('one verified observation CSV required')
    with paths[0].open() as f:
        reader=csv.reader(f);names=next(reader);rows=[[float(v) for v in row] for row in reader]
    duration=a.get('native_duration_ns',80)
    if not rows or rows[0][0]!=0 or abs(rows[-1][0]-duration*1e-9)>1e-18 or any(len(r)!=len(names) or not all(math.isfinite(v) for v in r) for r in rows) or any(b[0]<a[0] for a,b in zip(rows,rows[1:])):raise ValueError('complete finite nondecreasing waveform required')
    edges={role:transitions(rows,i) for i,role in enumerate(names) if i};mapping={}
    for role,port in [('up','BBPD[1]'),('dn','BBPD[0]')]:
        key=rv['roles'][port]['event_clock_receiver'];cell=next(c for c in rv['selected_cells'] if c['cell_key']==key)
        matches=[r for r,v in a['observations'].items() if v['node']==cell['pins']['Q']]
        if len(matches)!=1:raise ValueError('unique physical receiver output observation required')
        mapping[role]=matches[0]
    required=['reference_pin','feedback_pin']
    if not set(required)<=edges.keys():raise ValueError('both physical clock pins must be observed')
    ref=edges['reference_pin']['rising_ns'];fb=edges['feedback_pin'];cycles=[]
    for index,t in enumerate(ref):
        stop=ref[index+1] if index+1<len(ref) else rows[-1][0]*1e9
        captures={role:cycle_capture(edges['detector_'+role],edges[event],t,stop) for role,event in mapping.items()}
        active=[role for role,c in captures.items() if c['detector_rises']]
        rise,fall=nearest(fb['rising_ns'],t),nearest(fb['falling_ns'],t)
        cycles.append(dict(reference_rise_ns=t,observation_window_ns=[t,stop],
            nearest_observed_feedback_rising_offset_ps=None if rise is None else rise*1000,
            nearest_observed_feedback_falling_offset_ps=None if fall is None else fall*1000,
            prior_feedback_rising_edge_observed=any(e<t for e in fb['rising_ns']),
            decision=active[0] if len(active)==1 else 'both' if active else 'none',capture=captures))
    pins={str(p):sha(p) for p in [assessment,receivers,paths[0],Path(__file__).resolve(),Path(__file__).with_name('assess_selected_detector_phase_probe_v4.py'),Path(__file__).with_name('characterize_selected_detector_response.py')]};verify(pins)
    save(output,dict(input_sha256=pins,commanded_Q_anchor_offset_ns=a['phase_50_percent_crossing_offset_ns'],native_duration_ns=duration,
        cycles=cycles,event_observation_roles=mapping,
        measured_pin_clock_metrics={r:dict(complete_10_90_rise_slews_ps=rise_slews(rows,names.index(r)),complete_90_10_fall_slews_ps=falling_slews(rows,names.index(r))) for r in required},
        reference_centered_event_windows=True,feedback_edge_reuse_assumed_invalid=False,
        conditional_response_only=True,receiver_loading_bounded=False,exterior_condition_validated=False,
        detector_fit_qualified=False,release_ready=False))
    print(json.dumps(dict(cycles=cycles)))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['assessment','receivers','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['assessment','receivers','output']))
