from pathlib import Path
import csv,json,numpy as np
import argparse
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output.resolve()
with (out/'signals.csv').open() as f:
 r=csv.reader(f);names=next(r);a=np.asarray([[float(v) for v in row] for row in r])
assert a.shape[0]>1 and np.isfinite(a).all()
t=a[:,0];assert abs(t[-1]-260e-9)<1e-18
result=dict(samples=len(t),end_ns=t[-1]*1e9,measurement_window_ns=[200,260],signals={},release_ready=False,numerical_convergence_qualified=False,lock_qualified=False)
for name in ['v(pllout)','v(clkdiv_retimed)','v(refclk)','v(xpll:__parent_r_node_617)','v(config_ready)','v(config_busy)','v(tracking)','v(failed)']:
 if name not in names:continue
 v=a[:,names.index(name)];ix=np.flatnonzero((v[:-1]<.9)&(v[1:]>=.9));edges=t[ix]+(.9-v[ix])/(v[ix+1]-v[ix])*(t[ix+1]-t[ix]);w=(t>=200e-9);e=edges[(edges>=200e-9)&(edges<=260e-9)];p=np.diff(e);post=edges[edges>=180e-9]
 result['signals'][name]=dict(final_v=float(v[-1]),window_min_v=float(v[w].min()),window_max_v=float(v[w].max()),rising_edges_200_260ns=len(e),first_rise_after_180ns=float(post[0]*1e9) if len(post) else None,mean_frequency_mhz=float(1e-6/np.mean(p)) if len(p) else None,min_period_ns=float(p.min()*1e9) if len(p) else None,max_period_ns=float(p.max()*1e9) if len(p) else None)
for stem,n in [('coarse_code',6),('dco_code',8),('dlf_code',10)]:
 cols=[a[:,names.index(f'v({stem}[{i}])')] for i in range(n)];codes=sum((v>=.9).astype(int)*(1<<i) for i,v in enumerate(cols));result[stem]=dict(final=int(codes[-1]),window_codes=sorted(set(map(int,codes[t>=200e-9]))),transitions_after_reset=int(np.count_nonzero(np.diff(codes)[t[1:]>=180e-9])))
(out/'assessment.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
