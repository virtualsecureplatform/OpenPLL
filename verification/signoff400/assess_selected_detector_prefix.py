"""Measure complete detector events from a terminal budget-limited RAW prefix.

A prefix is diagnostic evidence only. It never substitutes for the complete
80 ns holdout, and only cycles with a full 20 ns observation window count.
"""
import argparse,csv,json,math
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity
from check_selected_boundary_waveforms import bind
from assess_selected_detector_phase_probe_v2 import transitions
from characterize_selected_detector_response import pair_phases,cycle_capture,rise_slews


def read_prefix(raw,roles):
    names=[];variables=None;declared=None;rows=[];truncated=False
    with raw.open() as stream:
        for line in stream:
            if line.startswith('No. Variables:'):variables=int(line.split(':',1)[1])
            if line.startswith('No. Points:'):
                value=line.split(':',1)[1].strip();declared=int(value) if value else None
            if line.strip()=='Variables:':break
        for line in stream:
            if line.strip()=='Values:':break
            index,name,_=line.split()
            if int(index)!=len(names):raise ValueError('invalid variable ordering')
            names.append(name)
        if not names or len(names)!=variables or names[0].lower()!='time':raise ValueError('incomplete RAW header')
        binding=bind(list(roles.values()),names)
        if not binding['all_bound']:raise ValueError('all observed voltages required')
        indices=[binding['bindings'][node]['index'] for node in roles.values()]
        for line in stream:
            if not line.strip():continue
            if not line.endswith('\n'):truncated=True;break
            index,value=line.split();t=float(value)
            if int(index)!=len(rows) or not math.isfinite(t) or (rows and t<rows[-1][0]):raise ValueError('invalid sample order')
            values=[t]
            for _ in range(variables-1):
                value=stream.readline()
                if not value or not value.endswith('\n'):truncated=True;break
                v=float(value)
                if not math.isfinite(v):raise ValueError('nonfinite saved native value')
                values.append(v)
            if truncated:break
            rows.append([t]+[values[i] for i in indices])
    if not rows or rows[0][0]!=0:raise ValueError('initial complete sample required')
    return rows,dict(declared_samples=declared,complete_samples=len(rows),incomplete_final_sample_discarded=truncated,
                     repeated_printed_timestamps=sum(a[0]==b[0] for a,b in zip(rows,rows[1:])))


def complete_cycles(rows,names,mapping):
    edges={role:transitions(rows,i) for i,role in enumerate(names) if i}
    end=rows[-1][0]*1e9;cycles=[]
    for reference,feedback in pair_phases(edges['reference_pin']['rising_ns'],edges['feedback_pin']['rising_ns']):
        start=min(reference,feedback);stop=start+20
        if stop>end:continue
        captures={role:cycle_capture(edges['detector_'+role],edges[event],start,stop) for role,event in mapping.items()}
        active=[role for role,c in captures.items() if c['detector_rises']]
        cycles.append(dict(reference_rise_ns=reference,feedback_rise_ns=feedback,
            measured_feedback_minus_reference_ps=(feedback-reference)*1000,
            complete_observation_window_ns=[start,stop],decision=active[0] if len(active)==1 else 'both' if active else 'none',capture=captures))
    return cycles


def run(probe,receivers,output):
    if output.exists():raise FileExistsError(output)
    status=probe/'status.json';state=json.loads(status.read_text())
    if state.get('state')!='stopped_without_qualification' or 'TimeoutError' not in state.get('reason',''):raise ValueError('terminal budget stop required')
    process=probe/'native.process.json';pid=json.loads(process.read_text())
    if identity(pid['pid'])==pid['birth']:raise ValueError('native worker still alive')
    manifest=probe/'manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
    rv=json.loads(receivers.read_text());verify(rv['input_sha256'])
    shared={p:d for p,d in rv['input_sha256'].items() if p in m['input_sha256']}
    if not shared or any(m['input_sha256'][p]!=d for p,d in shared.items()):raise ValueError('receiver physical identity mismatch')
    roles=m['observed_roles'];names=['time_s',*roles];mapping={}
    for role,port in [('up','BBPD[1]'),('dn','BBPD[0]')]:
        key=rv['roles'][port]['event_clock_receiver'];cell=next(c for c in rv['selected_cells'] if c['cell_key']==key)
        observed=[r for r,n in roles.items() if n==cell['pins']['Q']]
        if len(observed)!=1:raise ValueError('unique observed event receiver required')
        mapping[role]=observed[0]
    raw=probe/'probe.raw';rows,info=read_prefix(raw,roles);cycles=complete_cycles(rows,names,mapping)
    if not cycles:raise ValueError('no complete phase-event observation window in prefix')
    output.mkdir(parents=True)
    selected=output/'signals.csv'
    with selected.open('x') as f:
        writer=csv.writer(f);writer.writerow(names);writer.writerows(rows)
    pins=[manifest,status,process,raw,receivers,Path(__file__).resolve(),Path(__file__).with_name('characterize_selected_detector_response.py'),Path(__file__).with_name('assess_selected_detector_phase_probe_v2.py'),Path(__file__).with_name('check_selected_boundary_waveforms.py')]
    save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in pins},artifacts={str(selected):sha(selected)},
        status='budget_prefix_diagnostic',normal_full_window_completed=False,native_budget_stopped=True,
        native_circuit_failure_demonstrated=False,waveform=info,measured_window_ns=[0,rows[-1][0]*1e9],
        commanded_first_driver_offset_ns=m['phase_50_percent_crossing_offset_ns'],cycles=cycles,
        complete_10_90_rise_slews_ps={r:rise_slews(rows,names.index(r)) for r in ['reference_pin','feedback_pin']},
        event_observation_roles=mapping,physical_pin_phase_measured=True,conditional_response_only=True,
        exterior_condition_validated=False,receiver_loading_bounded=False,detector_fit_qualified=False,release_ready=False))
    print(json.dumps(dict(measured_end_ns=rows[-1][0]*1e9,cycles=cycles)))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['probe','receivers','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['probe','receivers','output']))
