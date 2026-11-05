"""Observe detector decisions by reference windows, including no/both responses."""
import bisect,csv,json,math
from pathlib import Path
from common_v3 import verify
from assess_selected_detector_phase_probe_v4 import transitions


def decisions(edges,end_ns,lookback_ps,initial_feedback_high):
    changes=sorted([(t,True) for t in edges['feedback_pin']['rising_ns']]+
                   [(t,False) for t in edges['feedback_pin']['falling_ns']])
    refs=edges['reference_pin']['rising_ns'];result=[]
    for i,ref in enumerate(refs):
        stop=refs[i+1] if i+1<len(refs) else end_ns
        sample=ref-lookback_ps/1000
        if sample<0:raise ValueError('lookback precedes observed waveform')
        index=bisect.bisect_right([t for t,v in changes],sample)-1
        high=changes[index][1] if index>=0 else initial_feedback_high
        active=[r for r in ['dn','up'] if any(ref<=t<stop for t in edges['detector_'+r]['rising_ns'])]
        actual=active[0] if len(active)==1 else 'both' if active else 'none'
        result.append(dict(reference_rise_ns=ref,window_end_ns=stop,sample_time_ns=sample,
                           sampled_feedback_high=high,predicted='dn' if high else 'up',decision=actual))
    if not result:raise ValueError('reference observations required')
    return result


def observe(path,lookback_ps):
    a=json.loads(path.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    csvs=[Path(p) for p in a['artifacts'] if p.endswith('/signals.csv')]
    if len(csvs)!=1:raise ValueError('unique native observation CSV required')
    with csvs[0].open() as f:
        reader=csv.reader(f);names=next(reader);rows=[[float(v) for v in row] for row in reader]
    if not rows or rows[0][0]!=0 or any(len(r)!=len(names) or not all(math.isfinite(v) for v in r) for r in rows) or any(y[0]<x[0] for x,y in zip(rows,rows[1:])):
        raise ValueError('finite complete nondecreasing observations required')
    roles=['reference_pin','feedback_pin','detector_up','detector_dn']
    if not set(roles)<=set(names):raise ValueError('physical detector input/output observations required')
    edges={r:transitions(rows,names.index(r)) for r in roles};end=rows[-1][0]*1e9
    initial=rows[0][names.index('feedback_pin')]>=.9
    cycles=decisions(edges,end,lookback_ps,initial)
    first=cycles[0]['reference_rise_ns']
    before={r:{direction:[t for t in e[direction] if t<first] for direction in ['rising_ns','falling_ns']}
            for r,e in edges.items() if r.startswith('detector_')}
    # Logical replay starts at t=0; establish the recorded input level explicitly.
    if initial:edges['feedback_pin']['rising_ns'].insert(0,0.)
    return dict(assessment=str(path),waveform=str(csvs[0]),edges=edges,cycles=cycles,
                measured_end_ns=end,normal_full_window_completed=a.get('normal_full_window_completed',True),
                pre_reference_detector_edges=before,initial_feedback_high=initial)
