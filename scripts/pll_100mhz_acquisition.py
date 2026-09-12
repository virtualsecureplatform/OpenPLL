#!/usr/bin/env python3
"""Measure a bounded 100 MHz acquisition screen with unchanged configured RTL.

The testbench supports preset, gain and coarse-band overrides and a supplied DCO
model. Production RTL is unchanged. This behavioral screen
is not transistor-level or noise signoff. Failed tracking screens are data,
not simulator errors; the existing configured regression remains separate.
"""
import argparse,csv,json,subprocess
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,default=ROOT/'build/acquisition_100mhz')
p.add_argument('--seeds',default='0,77,89,93,97,109,255')
p.add_argument('--phases-ns',default='0,10,20,30')
p.add_argument('--duration-ns',type=float,default=80000)
p.add_argument('--ki',type=int,default=-1,help='Diagnostic integral gain override; -1 uses controller')
p.add_argument('--kp',type=int,default=-1,help='Diagnostic proportional gain override; -1 uses controller')
p.add_argument('--coarse-code',type=int,default=-1,help='Diagnostic coarse override; -1 uses production controller')
p.add_argument('--dco-model',type=Path,default=ROOT/'models/IntegerPLL_DCO_25MHzCoarse_model.v')
a=p.parse_args(); out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
rtl=['IntegerPLL_B2TH','IntegerPLL_MMD_Retimer','IntegerPLL_Divider','IntegerPLL_DLF','IntegerPLL_DigitalCore','IntegerPLL_Top','IntegerPLL_25MHzModeConfig','IntegerPLL_25MHzModeController']
cmd=['iverilog','-g2012','-DOPENPLL_DCO_MODEL_COARSE','-s','tb_pll_100mhz_acquisition','-o',str(out/'acquisition.vvp')]
cmd += [str(ROOT/'rtl'/f'{name}.v') for name in rtl]
cmd += [str(ROOT/'models/IntegerPLL_BBPD_model.v'),str(a.dco_model.resolve()),str(ROOT/'tb/tb_pll_100mhz_acquisition.v')]
subprocess.run(cmd,check=True)
criteria=dict(window_ns=5120,frequency_tolerance_mhz=1,phase_span_limit_ns=10,phase_drift_limit_ns=2,phase_mean_limit_ns=5,require_no_rail=True)
results=[]
for seed in map(int,a.seeds.split(',')):
 for phase in map(float,a.phases_ns.split(',')):
  name=f'seed{seed:03d}_phase{phase:g}'
  trace=out/f'{name}.csv';log=out/f'{name}.log'
  cmd=['vvp',str(out/'acquisition.vvp'),f'+SEED={seed}',f'+COARSE={a.coarse_code}',f'+KI={a.ki}',f'+KP={a.kp}',f'+PHASE_NS={phase}',f'+DURATION_NS={a.duration_ns}',f'+TRACE={trace}']
  with log.open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=60)
  events={k:[] for k in ['REF','DIV','OUT']}
  with trace.open() as f:
   for r in csv.DictReader(f):events[r['event']].append([float(r['time_ns']),int(r['code']),int(r['bbpd'])])
  arrays={k:np.asarray(v) for k,v in events.items()}
  ref,div,osc=(arrays[k] for k in ['REF','DIV','OUT'])
  assert min(len(ref),len(div),len(osc))>10
  raw=(div[:,0]-ref[0,0]+20)%40-20
  phase_unwrapped=np.unwrap(raw*2*np.pi/40)*40/(2*np.pi)
  start=max(ref[0,0],div[0,0],osc[0,0]);end=min(ref[-1,0],div[-1,0],osc[-1,0])
  windows=[]
  for right in np.arange(end,start+criteria['window_ns'],-criteria['window_ns'])[::-1]:
   left=right-criteria['window_ns'];om=(osc[:,0]>=left)&(osc[:,0]<=right);dm=(div[:,0]>=left)&(div[:,0]<=right)
   ot=osc[om,0];dt=div[dm,0];ph=phase_unwrapped[dm];codes=div[dm,1]
   freq=1000*(len(ot)-1)/(ot[-1]-ot[0]);span=float(np.ptp(ph))
   drift=float(np.polyfit(dt-dt[0],ph,1)[0]*(dt[-1]-dt[0]))
   mean_phase=float((np.mean(ph)+20)%40-20)
   rail=bool(np.any((codes==0)|(codes==255)))
   passed=abs(freq-100)<=criteria['frequency_tolerance_mhz'] and span<=criteria['phase_span_limit_ns'] and abs(drift)<=criteria['phase_drift_limit_ns'] and abs(mean_phase)<=criteria['phase_mean_limit_ns'] and not rail
   windows.append(dict(start_ns=float(left),end_ns=float(right),frequency_mhz=float(freq),phase_span_ns=span,phase_drift_ns=drift,phase_mean_ns=mean_phase,rail=rail,screen_pass=bool(passed)))
  tail=windows[-1];last_bad=max([i for i,w in enumerate(windows) if not w['screen_pass']],default=-1)
  sustained_start=windows[last_bad+1]['start_ns'] if last_bad<len(windows)-1 else None
  result=dict(seed=seed,phase_offset_ns=phase,final_code=int(div[-1,1]),late_code_min=int(div[div[:,0]>=end-5120,1].min()),late_code_max=int(div[div[:,0]>=end-5120,1].max()),late=tail,sustained_screen_start_ns=sustained_start,windows=windows,command=cmd,trace=str(trace))
  results.append(result)
  print(json.dumps({k:result[k] for k in ['seed','phase_offset_ns','final_code','late','sustained_screen_start_ns']}),flush=True)
(out/'summary.json').write_text(json.dumps(dict(model='configured RTL with behavioral BBPD and selected DCO model',criteria=criteria,dco_model=str(a.dco_model.resolve()),coarse_override=a.coarse_code,ki_override=a.ki,kp_override=a.kp,duration_ns=a.duration_ns,results=results),indent=2))
