"""Diagnostic comparison of frozen partial waveforms; never qualifies completion."""
import datetime, json, re
from pathlib import Path
import numpy as np
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
import time


def read_partial(path):
    lines=path.read_text().splitlines();header=lines[0].split()
    if header[:2]!=['Index','TIME']:raise ValueError('standard header required')
    rows=[];discarded=[]
    for i,line in enumerate(lines[1:],1):
        if not line.strip():continue
        fields=line.split()
        if fields==['End','of','Xyce(TM)','Simulation']:raise ValueError('expected stopped partial run')
        if len(fields)!=len(header):
            if i!=len(lines)-1:raise ValueError('interior malformed sample')
            discarded.append(line);continue
        values=[float(v) for v in fields[1:]]
        if int(fields[0])!=len(rows) or not np.all(np.isfinite(values)):raise ValueError('invalid sample')
        if rows and values[0]<=rows[-1][0]:raise ValueError('nonmonotonic sample')
        rows.append(values)
    if not rows or rows[0][0]!=0:raise ValueError('initial sample required')
    return header,np.array(rows),len(discarded)


def progress(log):
    pairs=re.findall(r'\*\*\*\*\* Percent complete: ([\d.]+) %\n\*\*\*\*\* Current system time: ([^\n]+)',log)
    points=[(float(p)*3.4,datetime.datetime.strptime(t,'%a %b %d %H:%M:%S %Y'))for p,t in pairs]
    return dict(points=[dict(simulated_ns=p,UTC=t.isoformat())for p,t in points],
        transient_progress_ns_per_hour=((points[-1][0]-points[0][0])/((points[-1][1]-points[0][1]).total_seconds()/3600)) if len(points)>1 else None)


def run():
    base=ROOT/'build/signoff400';folders=[base/'selected_full_RC_transient_1827',base/'selected_full_RC_reuse_transient_1833']
    out=base/'selected_stopped_RC_reuse_comparison_1834';out.mkdir(exist_ok=False)
    pins={};data=[];stats=[];decks=[]
    with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+180):
        for p in folders:
            proc=json.loads((p/'native.process.json').read_text())
            if identity(proc['pid'])==proc['birth']:raise ValueError('worker still live')
            status=json.loads((p/'status.json').read_text())
            if status['state']!='stopped_without_qualification':raise ValueError('terminal stopped receipt required')
            for name in ['native.process.json','status.json','inputs.json','transient.prn','native.log','transient.spice']:
                q=p/name;pins[str(q)]=sha(q)
            h,a,d=read_partial(p/'transient.prn');data.append((h,a))
            log=(p/'native.log').read_text()
            stats.append(dict(folder=str(p),samples=len(a),last_simulated_ns=float(a[-1,0]*1e9),discarded_incomplete_final_rows=d,
                completed_numeric_factorizations=log.count('OPENPLL_LINEAR_TRACE end numeric'),
                **progress(log),last_progress=[x for x in log.splitlines()if x.startswith('OpenPLL UMFPACK progress:')][-1:]))
            deck=(p/'transient.spice').read_text().replace(str(p/'transient.prn'),'OUTPUT.prn');decks.append(deck)
        if decks[0]!=decks[1]:raise ValueError('physical decks differ beyond output path')
        (ha,a),(hb,b)=data
        if ha!=hb or len(ha)!=67:raise ValueError('same 65 formal ports required')
        end=min(a[-1,0],b[-1,0]);grid=np.unique(np.concatenate([a[a[:,0]<=end,0],b[b[:,0]<=end,0]]))
        errors={}
        for i,name in enumerate(ha[2:],1):
            delta=np.abs(np.interp(grid,a[:,0],a[:,i])-np.interp(grid,b[:,0],b[:,i]))
            errors[name]=dict(max_abs_V=float(np.max(delta)),rms_V=float(np.sqrt(np.mean(delta**2))))
        verify(pins)
        save(out/'assessment.json',dict(input_sha256=pins,physical_decks_identical_except_output=True,
             runs=stats,shared_interval_end_ns=float(end*1e9),port_errors=errors,
             comparison_method='linear interpolation on union of complete sample timestamps',
             residual_acceptance_independently_verified=False,convergence_failure_totals_available=False,
             partial_waveform_diagnostic_only=True,transient_correlation_qualified=False,release_ready=False))

if __name__=='__main__':run()
