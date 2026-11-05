"""Compare positive accepted-time streaming samples with the native reference."""
import argparse,csv,json,math,os,time
from pathlib import Path
import numpy as np
from common_v3 import save,sha,verify
from resources import identity
from compare_selected_transient import rises


def read(path):
    with path.open() as f:
        reader=csv.reader(f);names=next(reader);data=np.asarray([[float(v) for v in row] for row in reader])
    if data.ndim!=2 or data.shape[1]!=len(names) or len(data)<2 or not np.isfinite(data).all() or np.any(np.diff(data[:,0])<=0):
        raise ValueError('complete finite ordered samples required')
    return [s.lower() for s in names],data


def compare(reference,candidate,end_s):
    rn,r=read(reference);cn,c=read(candidate)
    if not math.isfinite(end_s) or end_s<=0 or not 0<c[0,0]<=1e-12 or abs(c[-1,0]-end_s)>1e-18:
        raise ValueError('positive accepted samples must cover bootstrap through declared endpoint')
    if r[0,0]!=0 or r[-1,0]<end_s:raise ValueError('native reference coverage missing')
    if len(set(rn))!=len(rn) or len(set(cn))!=len(cn):raise ValueError('duplicate observation channels')
    metrics={}
    for j,name in enumerate(cn[1:],1):
        key=name if name in rn else 'v(xpll:'+name[2:]
        if key not in rn:raise ValueError('native reference channel missing: '+name)
        v=r[:,rn.index(key)];expected=np.interp(c[:,0],r[:,0],v)
        rr=rises(r[:,0],v);rr=rr[(rr>=c[0,0]) & (rr<=end_s)]
        cr=rises(c[:,0],c[:,j])
        fw_start=max(200e-9,float(c[0,0]));cw=cr[cr>=fw_start];rw=rr[rr>=fw_start]
        cf=float(1/np.mean(np.diff(cw))/1e6) if len(cw)>=3 else None
        rf=float(1/np.mean(np.diff(rw))/1e6) if len(rw)>=3 else None
        metrics[name]=dict(frequency_window_start_s=fw_start,
            candidate_frequency_MHz=cf,reference_frequency_MHz=rf,
            frequency_difference_ppm=(cf-rf)/rf*1e6 if cf is not None and rf is not None else None,
            maximum_voltage_difference_V=float(np.abs(c[:,j]-expected).max()),
            rising_edge_count_candidate=len(cr),rising_edge_count_reference=len(rr),
            maximum_rising_edge_difference_s=float(np.abs(cr-rr).max()) if len(cr)==len(rr) and len(cr) else None)
    if not metrics:raise ValueError('observation channels required')
    maximum=max(v['maximum_voltage_difference_V'] for v in metrics.values())
    return dict(first_positive_accepted_time_s=float(c[0,0]),end_s=end_s,candidate_samples=len(c),channels=len(metrics),
        maximum_voltage_difference_V=maximum,within_diagnostic_voltage_tolerance=maximum<=1e-6,
        diagnostic_voltage_tolerance_V=1e-6,metrics=metrics,DC_comparison=False,
        reference_interpolation='linear_at_candidate_saved_times',physical_correlation_qualified=False,release_ready=False)


def follow(native,reference,output,end_s):
    output.mkdir(parents=True,exist_ok=False)
    owner=json.loads((native/'owner.json').read_text())
    pins={str(p):sha(p) for p in [reference,Path(__file__).resolve(),Path(__file__).with_name('compare_selected_transient.py')]}
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'inputs.json',dict(input_sha256=pins,native_owner=owner,end_s=end_s))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43500
    try:
        while True:
            state=json.loads((native/'status.json').read_text())['state']
            if state=='native_streaming_completed_comparison_pending':break
            if state=='stopped_without_qualification':raise RuntimeError('native streaming control failed')
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('native controller exited without completion receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>deadline:raise TimeoutError('native completion wait exhausted')
            save(output/'status.json',dict(state='waiting_for_native_streaming_completion',release_ready=False));time.sleep(10)
        verify(pins);verify(json.loads((native/'manifest.json').read_text())['input_sha256'])
        candidate=native/'signals.csv';digest=sha(candidate)
        report=compare(reference,candidate,end_s)
        if digest!=sha(candidate):raise ValueError('streamed waveform changed')
        verify(pins);report['input_sha256']=dict(pins,**{str(candidate):digest})
        save(output/'assessment.json',report)
        save(output/'status.json',dict(state='streaming_comparison_complete',within_diagnostic_voltage_tolerance=report['within_diagnostic_voltage_tolerance'],release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['native','reference','output']:p.add_argument('--'+key,required=True,type=Path)
    p.add_argument('--end-ns',required=True,type=float)
    a=p.parse_args();os.sched_setaffinity(0,{27});follow(a.native.resolve(),a.reference.resolve(),a.output.resolve(),a.end_ns*1e-9)
