#!/usr/bin/env python3
"""400MHz prototype trace acceptance, independent of physical model qualification.

An explicit observation horizon prevents a truncated channel from moving the
final windows earlier. Actual reference guard edges avoid phase extrapolation.
Full tuning changes are required to detect excursions between clock samples.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import numpy as np

from common_v3 import PROFILE as REQUIREMENTS, sha, save


def validate_spec(value):
    if value.get('profile') != 'programmed_400mhz_prototype_tapeout' or value['modes_mhz'] != [400]:
        raise ValueError('programmed400 prototype profile required')
    if value['reference_mhz'] != 25 or value['voltages'] != [1.8] or value['temperatures_c'] != [27]:
        raise ValueError('signoff operating scope mismatch')



def evaluate(events,controls,target_mhz,enabled_ns,stop_ns,spec):
    validate_spec(spec)
    if target_mhz not in spec['modes_mhz']:
        raise ValueError('unsupported release mode')
    if not all(math.isfinite(v) for v in (enabled_ns,stop_ns)) or not 0<=enabled_ns<stop_ns:
        raise ValueError('invalid observation interval')
    arrays={kind:np.asarray(events[kind],dtype=float) for kind in ('REF','DIV','OUT')}
    for kind,array in arrays.items():
        if array.ndim!=2 or array.shape[1]<2 or len(array)<3 or not np.isfinite(array).all():
            raise ValueError('insufficient/nonfinite '+kind+' trace')
        if np.any(np.diff(array[:,0])<=0) or np.any(array[:,0]<0):
            raise ValueError('invalid '+kind+' timestamps')
        if np.any(array[:,1]!=np.floor(array[:,1])) or np.any((array[:,1]<0)|(array[:,1]>255)):
            raise ValueError('fine codes must be8bit integers')
    result=dict(target_mhz=target_mhz,stimulus_ns=enabled_ns,observation_stop_ns=stop_ns,
        windows=[],passed=False,sustained_final_pass=False,acquisition_confirmed_ns=None,
        evidence='trace_functional_only',release_qualified=False)
    if controls is None or not len(controls):
        return dict(result,failure='complete_control_change_trace_required')
    control=np.asarray(controls,dtype=float)
    if control.ndim!=2 or control.shape[1]!=2 or not np.isfinite(control).all():
        raise ValueError('invalid control trace')
    if np.any(np.diff(control[:,0])<0) or np.any(control[:,0]<0):
        raise ValueError('invalid control timestamps')
    if np.any(control[:,1]!=np.floor(control[:,1])) or np.any((control[:,1]<0)|(control[:,1]>255)):
        raise ValueError('control fine codes must be8bit integers')
    ref,div,out=(arrays[k] for k in ('REF','DIV','OUT'))
    tref=1000/spec['reference_mhz'];tout=1000/target_mhz
    if ref[-1,0]<stop_ns:
        return dict(result,failure='reference_guard_edge_required')
    for kind,period in [('DIV',tref),('OUT',tout)]:
        prior=arrays[kind][arrays[kind][:,0]<=stop_ns]
        if not len(prior) or stop_ns-prior[-1,0]>1.5*period:
            return dict(result,failure='missing_final_'+kind+'_edges')
    start=max(enabled_ns,ref[0,0],div[0,0],out[0,0],control[0,0])
    width=spec['window_ns'];count=int(math.floor((stop_ns-start)/width))
    windows=[]
    for index in range(count):
        right=stop_ns-(count-1-index)*width;left=right-width
        dm=(div[:,0]>=left)&(div[:,0]<=right)
        om=(out[:,0]>=left)&(out[:,0]<=right)
        d=div[dm];o=out[om]
        if len(d)<3 or len(o)<3:
            windows.append(dict(start_ns=left,end_ns=right,passed=False,failure='insufficient_edges'))
            continue
        if np.count_nonzero((ref[:,0]>=left)&(ref[:,0]<=right))<3:
            windows.append(dict(start_ns=left,end_ns=right,passed=False,failure='insufficient_REF_edges'))
            continue
        # Every queried DIV edge lies inside actual reference samples.
        assert ref[0,0]<=d[0,0] and d[-1,0]<=ref[-1,0]
        ref_cycles=np.interp(d[:,0],ref[:,0],np.arange(len(ref)))
        raw=((ref_cycles+.5)%1-.5)*tref
        phase=np.unwrap(raw*2*np.pi/tref)*tref/(2*np.pi)
        span=float(np.ptp(phase))
        mean=float((phase.mean()+tref/2)%tref-tref/2)
        drift=float(np.polyfit(d[:,0]-d[0,0],phase,1)[0]*(d[-1,0]-d[0,0]))
        mhz=1000*(len(o)-1)/(o[-1,0]-o[0,0])
        error=abs(mhz/target_mhz-1)*1e6
        gaps={}
        for kind,period in [('REF',tref),('DIV',tref),('OUT',tout)]:
            array=arrays[kind]
            positions=np.flatnonzero((array[:,0]>=left)&(array[:,0]<=right))
            selected=array[max(0,positions[0]-1):positions[-1]+1,0]
            periods=np.diff(selected)
            gaps[kind]=bool(np.any((periods<.5*period)|(periods>1.5*period)))
        # Include the command active at the window's left boundary, as well as
        # every change inside it; edge-only snapshots can miss short excursions.
        before=np.flatnonzero(control[:,0]<=left)
        if not len(before):
            return dict(result,failure='missing_initial_control_snapshot')
        changes=control[(control[:,0]>left)&(control[:,0]<=right),1]
        values=np.concatenate(([control[before[-1],1]],changes,d[:,1],o[:,1]))
        fine_invalid=bool(np.any((values<spec['fine_code_min'])|(values>spec['fine_code_max'])))
        passed=(error<=spec['frequency_error_ppm'] and span<=tout*spec['phase_span_output_periods']
            and abs(mean)<=tout*spec['phase_mean_output_periods'] and abs(drift)<=tout*spec['phase_drift_output_periods']
            and not any(gaps.values()) and not fine_invalid)
        windows.append(dict(start_ns=left,end_ns=right,frequency_mhz=float(mhz),frequency_error_ppm=float(error),
            phase_span_ns=span,phase_mean_ns=mean,phase_drift_ns=drift,cycle_slip=any(gaps.values()),
            cycle_gaps=gaps,fine_outside_operating_range=fine_invalid,fine_min=int(min(values)),
            fine_max=int(max(values)),passed=bool(passed)))
    sustained=spec['sustained_windows']
    final_pass=len(windows)>=sustained and all(w['passed'] for w in windows[-sustained:])
    last_bad=max((i for i,w in enumerate(windows) if not w['passed']),default=-1)
    first=last_bad+1
    confirmation=windows[first+sustained-1]['end_ns'] if len(windows)-first>=sustained else None
    # Preserve the existing conservative confirmation-deadline convention.
    within=confirmation is not None and confirmation-enabled_ns<=spec['acquisition_limit_ns']
    result.update(windows=windows,sustained_final_pass=bool(final_pass),acquisition_confirmed_ns=confirmation,
                  passed=bool(final_pass and within),complete_control_trace_checked=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trace',type=Path,required=True,help='Existing event,time_ns,code,bbpd CSV schema')
    p.add_argument('--control-trace',type=Path,required=True,help='Phase bridge CSV containing every TUNE event')
    p.add_argument('--mode-mhz',type=int,choices=[400],required=True)
    p.add_argument('--enabled-ns',type=float,required=True)
    p.add_argument('--observation-stop-ns',type=float,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():p.error('fresh output required')
    paths=[a.trace.resolve(),a.control_trace.resolve(),REQUIREMENTS,Path(__file__).resolve()]
    pins={str(path):sha(path) for path in paths}
    events={k:[] for k in ('REF','DIV','OUT')}
    for row in csv.DictReader(a.trace.open()):
        if row['event'] not in events:raise ValueError('unknown clock trace event')
        events[row['event']].append([float(row['time_ns']),int(row['code']),int(row['bbpd'])])
    controls=[]
    for row in csv.DictReader(a.control_trace.open()):
        if row['event']=='ERROR':raise ValueError('model driver reported an error')
        if row['event']=='TUNE':controls.append([int(row['time_ps'])/1000,int(row['fine'])])
    result=evaluate(events,controls,a.mode_mhz,a.enabled_ns,a.observation_stop_ns,json.loads(REQUIREMENTS.read_text()))
    for path,digest in pins.items():
        if sha(path)!=digest:raise ValueError('input changed during assessment')
    result.update(sha256=pins,whole_pll_qualification_pass=False,
        qualification_requires='Terminal capture identity plus matching qualified physical DCO/interface models and validated closed-loop driver; a trace-only pass cannot qualify a release.')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    save(a.output,result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('windows','sha256')}))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
