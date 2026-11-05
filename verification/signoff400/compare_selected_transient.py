"""Quantify conditional-replay voltage/edge differences; never physical signoff."""
import argparse,csv,json,sys
from pathlib import Path
import numpy as np
from common_v3 import ROOT,save,sha
sys.path.insert(0,str(ROOT))
from tools.xyce_umfpack.compare_prefix import Prefix


def rises(t,v):
    i=np.flatnonzero((v[:-1]<.9)&(v[1:]>=.9))
    return t[i]+(.9-v[i])/(v[i+1]-v[i])*(t[i+1]-t[i])


def compare(reference,candidate,end_s,tolerance=1e-6):
    if not np.isfinite(end_s) or end_s<=0:raise ValueError('positive endpoint required')
    count=None
    with candidate.open() as f:
        for line in f:
            if line.startswith('No. Points:'):count=int(line.split(':',1)[1]);break
    if count is None or count<2:raise ValueError('complete candidate sample inventory required')
    p=Prefix(candidate)
    try:a=np.asarray([p.sample(i) for i in range(count)]);names=p.names
    finally:p.stream.close()
    if a[0,0]!=0 or abs(a[-1,0]-end_s)>1e-18:raise ValueError('candidate observation endpoint incomplete or wrong')
    with reference.open() as f:
        reader=csv.reader(f);columns=next(reader);ref=np.asarray([[float(v) for v in row] for row in reader])
    if not np.isfinite(ref).all() or np.any(np.diff(ref[:,0])<=0) or ref[0,0]>0 or ref[-1,0]<end_s:raise ValueError('finite ordered reference with endpoint coverage required')
    metrics={}
    for j,name in enumerate(names[1:],1):
        key=name if name in columns else 'v(xpll:'+name[2:]
        if key not in columns:raise ValueError('missing native channel: '+name)
        v=ref[:,columns.index(key)];interpolated=np.interp(a[:,0],ref[:,0],v);diff=np.abs(a[:,j]-interpolated)
        cr=rises(a[:,0],a[:,j]);rr=rises(ref[:,0],v);rr=rr[rr<=end_s]
        metrics[name]=dict(maximum_voltage_difference_V=float(diff.max()),rising_edge_count_candidate=len(cr),rising_edge_count_reference=len(rr),maximum_rising_edge_difference_s=float(np.max(np.abs(cr-rr))) if len(cr)==len(rr) and len(cr) else None)
    maximum=max(row['maximum_voltage_difference_V'] for row in metrics.values())
    return dict(end_s=end_s,candidate_samples=count,channels=len(metrics),maximum_voltage_difference_V=maximum,within_diagnostic_voltage_tolerance=maximum<=tolerance,diagnostic_voltage_tolerance_V=tolerance,metrics=metrics,reference_interpolation='linear_at_candidate_saved_times',physical_correlation_qualified=False,release_ready=False)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['reference','candidate','output']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--end-ns',type=float,required=True);a=p.parse_args()
    if a.output.exists():p.error('fresh output required')
    r=compare(a.reference,a.candidate,a.end_ns*1e-9);r['input_sha256']={str(x.resolve()):sha(x) for x in [a.reference,a.candidate,Path(__file__)]};save(a.output,r);print(json.dumps({k:v for k,v in r.items() if k not in ['metrics','input_sha256']}))
