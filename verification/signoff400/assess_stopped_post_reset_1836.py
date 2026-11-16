"""Frozen partial full-RC post-reset diagnostics, without completion qualification."""
import json,re,time,datetime
from pathlib import Path
import numpy as np
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compare_stopped_RC_reuse_1834 import read_partial


def run():
    p=ROOT/'build/signoff400/selected_full_RC_extended_reuse_1835'
    proc=json.loads((p/'native.process.json').read_text())
    if identity(proc['pid'])==proc['birth']:raise ValueError('worker still live')
    if json.loads((p/'status.json').read_text())['state']!='stopped_without_qualification':raise ValueError('stopped receipt required')
    out=ROOT/'build/signoff400/selected_post_reset_diagnostic_1836';out.mkdir(exist_ok=False)
    pins={str(q):sha(q)for q in [p/'native.process.json',p/'status.json',p/'inputs.json',p/'transient.spice',p/'transient.prn',p/'native.log',Path(__file__).resolve(),Path(__file__).with_name('compare_stopped_RC_reuse_1834.py')]}
    with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+180):
        header,a,discarded=read_partial(p/'transient.prn');names=header[1:];t=a[:,0];post=t>=80.1e-9
        if not np.any(post):raise ValueError('no post-release samples')
        metrics={}
        for i,name in enumerate(names[1:],1):
            v=a[:,i];vp=v[post];mask=(v>=.9);ix=np.flatnonzero(mask[1:]!=mask[:-1])+1
            transitions=[float(t[j]*1e9)for j in ix if t[j]>=80e-9]
            metrics[name]=dict(post_min_V=float(vp.min()),post_max_V=float(vp.max()),final_V=float(v[-1]),
                post_threshold_crossings_ns=transitions,post_intermediate_samples=int(np.sum((vp>.36)&(vp<1.44))))
        snapshots={}
        for ns in [79.9,80.1,81,85,90,100,float(t[-1]*1e9)]:
            j=int(np.argmin(abs(t-ns*1e-9)));sample={}
            for bus,width in [('COARSE_CODE',6),('DCO_CODE',8),('DLF_CODE',10)]:
                values=[a[j,names.index(f'V({bus}[{k}])')]for k in range(width)]
                sample[bus]=sum((1<<k)for k,v in enumerate(values)if v>=.9)
                sample[bus+'_ambiguous_bits']=[k for k,v in enumerate(values)if .36<v<1.44]
            for signal in ['RESET_N','PLL_ENABLE','REFCLK','PLLOUT','CONFIG_BUSY','CONFIG_READY','TRACKING','FAILED','CLKDIV_RETIMED']:
                sample[signal]=float(a[j,names.index('V('+signal+')')])
            snapshots[str(float(t[j]*1e9))]=sample
        log=(p/'native.log').read_text();pairs=re.findall(r'Percent complete: ([\d.]+) %\n\*\*\*\*\* Current system time: ([^\n]+)',log)
        points=[(float(v)*3.4,datetime.datetime.strptime(s,'%a %b %d %H:%M:%S %Y'))for v,s in pairs];postpoints=[x for x in points if x[0]>=80.1]
        rate=(postpoints[-1][0]-postpoints[0][0])/((postpoints[-1][1]-postpoints[0][1]).total_seconds()/3600) if len(postpoints)>1 else None
        warnings=[line for line in log.splitlines()if any(x in line.lower()for x in ['warning','failed','failure'])]
        verify(pins)
        save(out/'assessment.json',dict(input_sha256=pins,samples=len(a),all_printed_values_finite=True,discarded_incomplete_final_rows=discarded,
             last_simulated_ns=float(t[-1]*1e9),post_release_samples=int(post.sum()),ports=metrics,snapshots=snapshots,
             post_reset_progress_ns_per_hour=rate,post_reset_progress_points=[dict(ns=x,UTC=y.isoformat())for x,y in postpoints],
             warning_failure_lines=warnings,terminal_solver_summary_present='OpenPLL UMFPACK adapter: calls=' in log,
             failure_totals_verified=False,partial_waveform_diagnostic_only=True,frequency_qualified=False,release_ready=False))

if __name__=='__main__':run()
