"""Measure physical fast-clock transport and observed retimer capture latency.

Pair the ordered startup carrier edges, then check Q changes against the first
eligible CLK edge after D/reset transitions. Sparse TT observations do not
qualify a corner envelope, uncertainty bound, or complete causal timing model.
"""
import argparse,bisect,csv,json,math
from pathlib import Path
from common_v3 import save,sha,verify
from selected_native_clock_shapes import load
from assess_selected_detector_phase_probe_v2 import transitions
from capture_selected_native_initial_snapshot import fingerprint


def interpolate(rows,t_ns):
    t=t_ns*1e-9;times=[p[0] for p in rows];i=bisect.bisect_left(times,t)
    if i<len(rows) and times[i]==t:return rows[i][1]
    if i==0 or i==len(rows):raise ValueError('observation extrapolation forbidden')
    a,v=rows[i-1];b,w=rows[i];return v+(w-v)*(t-a)/(b-a)


def carrier_pair(root,clock):
    r=[t for t in root if t>=180];c=[t for t in clock if t>=180]
    if len(r)<3 or len(r)!=len(c):raise ValueError('one-to-one ordered startup carrier edges required')
    half=min(b-a for a,b in zip(r,r[1:]))/2;delays=[(y-x)*1000 for x,y in zip(r,c)]
    if any(not 0<d<half*1000 for d in delays):raise ValueError('clock transport does not have an unambiguous short ordered pairing')
    return r,c,dict(samples=len(delays),observed_transport_interval_ps=[min(delays),max(delays)],
                    mean_transport_ps=sum(delays)/len(delays),ordered_startup_edge_counts_match=True)


def run(capture,root_signals,clock_timing,snapshot,output):
    if output.exists():raise FileExistsError(output)
    receipt=capture/'assessment.json';a=json.loads(receipt.read_text());verify(a['artifacts'])
    raw=[Path(p) for p in a['input_sha256'] if p.endswith('/profile.raw')]
    if len(raw)!=1:raise ValueError('one frozen full native RAW provenance required')
    sr=json.loads(snapshot.read_text());verify(sr['artifacts']);verify({p:d for p,d in a['input_sha256'].items() if p!=str(raw[0])})
    if sr['input_sha256'].get(str(raw[0]))!=a['input_sha256'][str(raw[0])] or fingerprint(raw[0])!=sr['source_file_fingerprint']:raise ValueError('full native RAW fingerprint/provenance mismatch')
    timing=json.loads(clock_timing.read_text());verify(timing['input_sha256']);verify(timing['reference_model_sha256'])
    if timing['input_sha256'].get(str(root_signals))!=sha(root_signals):raise ValueError('root clock CSV differs from native timing observation')
    shared={p:d for p,d in timing['input_sha256'].items() if p in a['input_sha256'] and p.endswith('/manifest.json')}
    if not shared or any(a['input_sha256'][p]!=d for p,d in shared.items()):raise ValueError('root and captured clock traces belong to different native runs')
    with root_signals.open() as f:
        reader=csv.reader(f);names=next(reader);rows=[[float(v) for v in row] for row in reader]
    if not rows or any(len(r)!=len(names) or not all(math.isfinite(v) for v in r) for r in rows) or any(b[0]<=a[0] for a,b in zip(rows,rows[1:])):raise ValueError('finite ordered root waveform required')
    root=transitions(rows,names.index('v(pllout)'))['rising_ns'];items=a['clock_driver_waveforms']
    curves={k:load(Path(items[k]['file'])) for k in ['feedback_ff_clock','feedback_ff_data','feedback_ff_reset','CLKDIVR','synchronizer_clock']}
    edges={k:transitions(v,1) for k,v in curves.items()};paths={};paired={}
    for role in ['feedback_ff_clock','synchronizer_clock']:
        r,c,p=carrier_pair(root,edges[role]['rising_ns']);paths[role]=p;paired[role]=(r,c)
    r,clk=paired['feedback_ff_clock'];records=[]
    data=edges['feedback_ff_data'];resets=edges['feedback_ff_reset']['rising_ns']
    for direction,high in [('rising_ns',True),('falling_ns',False)]:
        for q in edges['CLKDIVR'][direction]:
            if q<180:continue
            index=bisect.bisect_left(clk,q)-1
            if index<0:raise ValueError('feedback Q change precedes observed carrier clock')
            c=clk[index];d=interpolate(curves['feedback_ff_data'],c);reset=interpolate(curves['feedback_ff_reset'],c)
            changes=[t for t in data[direction] if t<c];released=[t for t in resets if t<c]
            if not changes or not released:raise ValueError('observed driver data/reset history missing')
            eligible_from=max(changes[-1],released[-1]);eligible=[t for t in clk if eligible_from<t<=c]
            valid=reset>=1.62 and (d>=1.62 if high else d<=.18)
            records.append(dict(output_edge=direction,Q_crossing_ns=q,CLK_crossing_ns=c,
                root_crossing_ns=r[index],CLK_to_Q_ps=(q-c)*1000,root_to_Q_ps=(q-r[index])*1000,
                data_voltage_at_CLK_V=d,reset_voltage_at_CLK_V=reset,data_setup_since_last_crossing_ps=(c-changes[-1])*1000,
                first_eligible_CLK_after_data_or_reset=len(eligible)==1,data_and_reset_levels_match_output=valid))
    if len(records)<3:raise ValueError('at least three output changes required')
    pins={str(p):sha(p) for p in [receipt,root_signals,clock_timing,snapshot,Path(__file__).resolve(),Path(__file__).with_name('selected_native_clock_shapes.py'),Path(__file__).with_name('assess_selected_detector_phase_probe_v2.py'),Path(__file__).with_name('capture_selected_native_initial_snapshot.py')]};verify(pins)
    if fingerprint(raw[0])!=sr['source_file_fingerprint']:raise ValueError('full native RAW changed during measurement')
    save(output,dict(input_sha256=pins,operating_point=timing['operating_point'],clock_paths=paths,retimer_transitions=records,
        all_observed_Q_changes_match_first_eligible_CLK=all(r['first_eligible_CLK_after_data_or_reset'] and r['data_and_reset_levels_match_output'] for r in records),
        unwrapped_causal_latency_qualified=False,clock_timing_qualified=False,physical_models_qualified=False,release_ready=False))
    print(json.dumps(dict(clock_paths=paths,retimer_transitions=records)))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['capture','root-signals','clock-timing','snapshot','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n.replace('-','_')).resolve() for n in ['capture','root-signals','clock-timing','snapshot','output']))
