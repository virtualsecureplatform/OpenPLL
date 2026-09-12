#!/usr/bin/env python3
"""Run KLS/extracted-BBPD/RTL diagnostics with explicit DCO calibration.

Requires the regenerated PDK/BBPD artifacts and optional CMake RTL co-sim target.
Criteria are acquisition screens, not a jitter or production release specification.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import numpy as np
from pll_verification import evaluate_trace, load_spec, fingerprint

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-deck', type=Path, required=True, help='Existing extracted-BBPD deck supplying .lib and .include lines')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--binary', type=Path, default=WORKSPACE/'build/openpll-cinterface/xyce_pll_rtl_cosim')
    p.add_argument('--seed', type=int, default=235)
    p.add_argument('--phase-ns', type=float, default=0)
    p.add_argument('--duration-ns', type=float, default=160000)
    p.add_argument('--step-ps', type=float, default=20)
    p.add_argument('--ki', type=int, default=4)
    p.add_argument('--kp', type=int, default=4)
    p.add_argument('--mode-mhz',type=int,choices=[100,250,300,400,500],default=100)
    p.add_argument('--corner',choices=['tt','ff','ss','sf','fs'],default='tt')
    p.add_argument('--vdd',type=float,default=1.8)
    p.add_argument('--temperature-c',type=float,default=27)
    p.add_argument('--dco-model',type=Path,help='Calibrated JSON including mode/PVT metadata and full-code-range points')
    p.add_argument('--dco-timing',choices=['phase-accum','legacy-rounded'],default='phase-accum')
    p.add_argument('--acquisition',action='store_true',help='Use acknowledged coarse acquisition and a 48-band DCO model')
    p.add_argument('--kls-backend',choices=['AUTO','KLS','SERIAL'],default='AUTO')
    p.add_argument('--smoke-only',action='store_true',help='Allow short bridge diagnostics before tracking; cannot qualify acquisition')
    p.add_argument('--acceptance-profile',choices=['engineering','legacy'],default='engineering')
    a = p.parse_args()
    if not np.isfinite(a.vdd) or a.vdd<=0 or not np.isfinite(a.temperature_c) or a.temperature_c<=-273.15:
        p.error('invalid voltage or temperature')
    nominal = a.mode_mhz==100 and a.corner=='tt' and a.vdd==1.8 and a.temperature_c==27
    if a.dco_model is None and not nominal:
        p.error('this operating point requires a characterized --dco-model')
    if a.acceptance_profile=='legacy' and a.mode_mhz!=100:
        p.error('legacy acceptance applies only to 100 MHz')
    if a.smoke_only and a.acceptance_profile!='engineering':
        p.error('smoke-only diagnostics require engineering acceptance')
    model = json.loads(a.dco_model.read_text()) if a.dco_model else None
    if a.dco_model and (not isinstance(model,dict) or not model):
        p.error('DCO model must be a nonempty object with calibration metadata')
    if a.acquisition and (not model or a.dco_timing!='phase-accum'):
        p.error('acquisition requires a complete DCO model and continuous phase')
    if model is not None:
        expected=dict(mode_mhz=a.mode_mhz,corner=a.corner,vdd=a.vdd,temperature_c=a.temperature_c)
        if any(model.get(k)!=v for k,v in expected.items()):
            p.error('DCO model operating point does not match requested conditions')
        bands=model.get('bands',[]) if a.acquisition else [model]
        if not isinstance(bands,list) or any(not isinstance(band,dict) for band in bands):
            p.error('DCO bands must be objects')
        if a.acquisition and [band.get('coarse') for band in bands]!=list(range(48)):
            p.error('acquisition model must include all 48 coarse bands in order')
        for band in bands:
          points=band.get('points',[])
          if not isinstance(points,list) or any(not isinstance(point,dict) or
                type(point.get('code')) is not int or
                type(point.get('mhz')) not in (int,float) for point in points):
            p.error('calibration points require integer code and numeric mhz')
          codes=[point['code'] for point in points]
          if len(codes)<2 or codes[0]!=0 or codes[-1]!=255 or any(x>=y for x,y in zip(codes,codes[1:])):
            p.error('DCO model must cover strictly increasing integer codes 0..255')
          if any(type(point['code']) is not int or not np.isfinite(point['mhz']) or point['mhz']<=0 for point in points):
            p.error('invalid calibration point')
          if type(band.get('coarse')) is not int or not 0<=band['coarse']<=47:
            p.error('invalid calibrated coarse band')
          if type(band.get('output_divider',1)) is not int or band.get('output_divider',1) not in [1,2,4,8]:
            p.error('DCO output divider must be 1, 2, 4, or 8')
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    if (out/'run.log').exists():
        p.error('output already has a run.log; use a fresh directory')
    includes = '\n'.join(line for line in a.base_deck.read_text().splitlines() if line.startswith(('.lib ', '.include ')))
    if not includes:
        p.error('base deck has no model includes')
    includes = re.sub(r'(?m)^(\.lib\s+"[^"\n]+")\s+\w+[ \t]*$', lambda m: m[1]+' '+a.corner, includes)
    deck = out/'circuit.cir'
    deck.write_text(f'''* Production RTL boundary: extracted BBPD only; ideal supplies.
{includes}
.param VDD={a.vdd:g}
.temp {a.temperature_c:g}
VVPWR VPWR 0 {{VDD}}
VVPB VPB 0 {{VDD}}
VVGND VGND 0 0
VVNB VNB 0 0
YDAC ref_driver REF 0 logic_dac
YDAC div_driver CLKDIVR 0 logic_dac
YDAC reset_driver RESET_N 0 logic_dac
YADC up_adc BBPD[1] 0 logic_adc R=1T WIDTH=1
YADC dn_adc BBPD[0] 0 logic_adc R=1T WIDTH=1
.model logic_dac DAC(tr=20p tf=20p)
.model logic_adc ADC(settlingtime=0 uppervoltagelimit={a.vdd:g} lowervoltagelimit=0)
XBBPD BBPD[0] BBPD[1] CLKDIVR REF RESET_N VGND VNB VPB
+ VPWR IntegerPLL_BBPD
.tran 5p {a.duration_ns+1:g}n 0 {a.step_ps:g}p
.options linsol type=KLS KLS_THREADS=1 KLS_PROFILE=1 KLS_BACKEND={a.kls_backend}
.options timeint reltol=1e-4 abstol=1e-8
.end
''')
    trace = out/'trace.csv'
    command = list(map(str,[a.binary.resolve(),deck,trace,a.seed,a.phase_ns,a.duration_ns,a.step_ps,a.ki,a.kp]))
    if a.dco_timing=='phase-accum': command.append('--phase-accum')
    if a.smoke_only: command.append('--smoke-only')
    command += ['--ndiv',str(a.mode_mhz//25),'--coarse',str(model['coarse'] if model and not a.acquisition else 17),'--vdd',str(a.vdd)]
    if a.acquisition:
        table=out/'dco-bank.txt'
        table.write_text(''.join(f"{band['coarse']} {point['code']} {point['mhz']:.15g}\n"
                                for band in model['bands'] for point in band['points']))
        command += ['--acquisition','--dco-bank',str(table)]
        dividers=out/'dco-dividers.txt'
        dividers.write_text(''.join(f"{band['coarse']} {band.get('output_divider',1)}\n" for band in model['bands']))
        command += ['--dco-dividers',str(dividers)]
    elif model:
        table=out/'dco-table.txt'
        table.write_text(''.join(f"{point['code']} {point['mhz']:.15g}\n" for point in model['points']))
        command += ['--dco-table',str(table)]
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    model_files=[]
    for line in includes.splitlines():
        match=re.search(r'"([^"\n]+)"',line)
        if not match: p.error('model includes must use quoted absolute paths')
        included=Path(match[1])
        if not included.is_absolute(): p.error('model includes must use absolute paths')
        if line.startswith('.lib'):
            pdk = next((parent for parent in included.parents if (parent/'libs.ref').is_dir()),None)
            if pdk is None: p.error('cannot identify PDK root for model provenance')
            model_files += [pdk/'libs.ref',pdk/'libs.tech/ngspice']
        else: model_files.append(included)
    run_inputs=[a.binary,deck,*model_files,*((ROOT/'rtl').glob('*.v')),ROOT/'tb/IntegerPLL_Cosim.v',ROOT/'scripts/pll_verification.py',ROOT/'verification/engineering.json']
    if a.dco_model: run_inputs.append(a.dco_model)
    manifest=fingerprint(run_inputs,dict(command=command,acceptance=a.acceptance_profile,dco_timing=a.dco_timing))
    (out/'provenance.json').write_text(json.dumps(manifest,indent=2))
    binary_sha256 = hashlib.sha256(a.binary.read_bytes()).hexdigest()
    start = time.monotonic()
    with (out/'run.log').open('w') as log:
        result = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env)
    metadata = dict(dco_timing=a.dco_timing, acceptance_profile=a.acceptance_profile, mode_mhz=a.mode_mhz, corner=a.corner, vdd=a.vdd, temperature_c=a.temperature_c, calibration_qualified=bool(model and model.get('convergence_passed') and model.get('coverage_passed') and model.get('interpolation_validated')), binary_sha256=binary_sha256, command=command, wall_s=time.monotonic()-start, returncode=result.returncode)
    metadata.update(acquisition=a.acquisition,smoke_only=a.smoke_only,kls_backend=a.kls_backend)
    (out/'run.json').write_text(json.dumps(metadata,indent=2))
    log = (out/'run.log').read_text()
    if result.returncode or 'rtl_cosim=pass' not in log or 'KLS profile calls =' not in log:
        raise RuntimeError(f'Simulation failed; see {out}/run.log')
    events = {k: [] for k in ('REF','DIV','OUT')}
    with trace.open() as f:
        for row in csv.DictReader(f):
            events[row['event']].append([float(row['time_ns']),int(row['code']),int(row['bbpd'])])
    ref,div,osc = (np.asarray(events[k]) for k in events)
    tracking = float(re.search(r'tracking_ns=([\d.e+-]+)',log)[1])
    if tracking<0: tracking=None
    lag = float(re.search(r'max_adc_lag_ps=([\d.e+-]+)',log)[1])
    if lag > a.step_ps+0.1:
        raise RuntimeError(f'ADC latency {lag} ps exceeds requested step')
    assert all(np.isfinite(x).all() and len(x)>10 and np.all(np.diff(x[:,0])>0) for x in (ref,div,osc))
    engineering = evaluate_trace(events,a.mode_mhz,280) if a.acceptance_profile=='engineering' else None
    if engineering is not None and a.smoke_only:
        engineering['passed']=False
        engineering['smoke_only']=True
    if engineering is not None:
        summary=dict(**metadata,seed=a.seed,phase_ns=a.phase_ns,ki=a.ki,kp=a.kp,step_ps=a.step_ps,tracking_ns=tracking,max_adc_lag_ps=lag,engineering=engineering)
        (out/'summary.json').write_text(json.dumps(summary,indent=2)); print(json.dumps(summary),flush=True)
        return
    phase = np.unwrap(((div[:,0]-ref[0,0]+20)%40-20)*2*np.pi/40)*40/(2*np.pi)
    end = min(ref[-1,0],div[-1,0],osc[-1,0]); windows=[]
    for right in np.arange(end,tracking+5120,-5120)[::-1]:
        left=right-5120
        dm=(div[:,0]>=left)&(div[:,0]<=right); om=(osc[:,0]>=left)&(osc[:,0]<=right)
        dt=div[dm,0]; ot=osc[om,0]; ph=phase[dm]; codes=div[dm,1]
        frequency=1000*(len(ot)-1)/(ot[-1]-ot[0]); span=float(np.ptp(ph))
        drift=float(np.polyfit(dt-dt[0],ph,1)[0]*(dt[-1]-dt[0])); mean=float((ph.mean()+20)%40-20)
        rail=bool(np.any((codes==0)|(codes==255)))
        passed=bool(abs(frequency-100)<=1 and span<=10 and abs(drift)<=2 and abs(mean)<=5 and not rail)
        windows.append(dict(start_ns=float(left),end_ns=float(right),frequency_mhz=frequency,phase_span_ns=span,phase_drift_ns=drift,phase_mean_ns=mean,rail=rail,code_min=int(codes.min()),code_max=int(codes.max()),screen_pass=passed))
    summary=dict(**metadata,seed=a.seed,phase_ns=a.phase_ns,ki=a.ki,kp=a.kp,step_ps=a.step_ps,tracking_ns=tracking,max_adc_lag_ps=lag,windows=windows,late=windows[-1] if windows else None,sustained_final_four_pass=len(windows)>=4 and all(w['screen_pass'] for w in windows[-4:]))
    (out/'summary.json').write_text(json.dumps(summary,indent=2)); print(json.dumps(summary),flush=True)

if __name__ == '__main__':
    main()
