#!/usr/bin/env python3
"""Run a pinned loaded BBPD signal-voltage PVT/phase screen with native Xyce.

The fixed-rail reduction excludes supply current, power, noise, nonideal rails,
and nonlinear receivers. Passing this screen never establishes PLL release.
"""
import argparse
import concurrent.futures
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from translate_sky130_diode import translate, REPLACEMENT
from sky130_diode_translation_probe import translated_model, MODEL_SHA256
from reduce_bbpd_fixed_rails import reduce, verify_ideal_rails


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(hashes):
    for path, expected in hashes.items():
        if sha(path) != expected:
            raise RuntimeError(f'Changed input or artifact: {path}')


def read_rows(path, stop_ns=90):
    rows = []
    text = path.read_text()
    for line in text.splitlines()[1:]:
        fields = line.split()
        if fields and fields[0].isdigit():
            row = list(map(float, fields))
            if len(row) != 7 or not all(math.isfinite(v) for v in row):
                raise RuntimeError('Malformed or nonfinite waveform')
            rows.append(row)
    if (not rows or rows[0][1] != 0 or rows[-1][1] < stop_ns * 1e-9 - 1e-14
            or any(b[1] <= a[1] for a, b in zip(rows, rows[1:]))
            or 'End of Xyce(TM) Simulation' not in text):
        raise RuntimeError('Incomplete or nonmonotone waveform')
    return rows


def crossings(rows, column, threshold, start=5e-9, stop=85e-9):
    rise, fall = [], []
    for a, b in zip(rows, rows[1:]):
        if a[column] < threshold <= b[column] or b[column] < threshold <= a[column]:
            t = a[1] + (b[1] - a[1]) * (threshold - a[column]) / (b[column] - a[column])
            if start <= t <= stop:
                (rise if b[column] > a[column] else fall).append(t)
    return rise, fall


def measure(rows, supply):
    result = {}
    for column, name in ((4, 'BBPD[0]'), (5, 'BBPD[1]')):
        edge = {fraction: crossings(rows, column, supply * fraction) for fraction in (.2, .5, .8)}
        complete = all(len(v) == 2 for pair in edge.values() for v in pair)
        widths = [(f-r)*1e9 for r,f in zip(*edge[.5])] if complete else []
        rises = [(h-l)*1e9 for l,h in zip(edge[.2][0],edge[.8][0])] if complete else []
        falls = [(l-h)*1e9 for h,l in zip(edge[.8][1],edge[.2][1])] if complete else []
        complete &= bool(widths) and all(v > 0 for v in widths+rises+falls)
        sample = [r[column] for r in rows if 5e-9 <= r[1] <= 85e-9]
        if not sample:
            raise RuntimeError('Missing analysis window')
        result[name] = {'complete_two_pulses':complete, 'minimum_v':min(sample), 'maximum_v':max(sample),
                        'high_pulse_widths_ns':widths, 'rising_slew_20_80_ns':rises,
                        'falling_slew_80_20_ns':falls,
                        'rising_half_supply_edges_ns':[t*1e9 for t in edge[.5][0]]}
    return result


def deck(pdk, model, corner, supply, temperature, phase_ps, edge_ps, loads):
    if (corner not in ('ss','tt','ff','sf','fs') or not 0 < supply <= 1.95
            or temperature not in (-40,27,125) or not -5000 <= phase_ps <= 5000
            or not 0 < edge_ps <= 1000 or len(loads) != 2
            or any(not math.isfinite(v) or v <= 0 for v in loads)):
        raise RuntimeError('Unsupported characterization point')
    text=f'''* Isolated BUF8 BBPD loaded voltage screen, reduced constant-rail filler MOS.
.lib "{pdk}/libs.tech/ngspice/sky130.lib.spice" {corner}
.include "{model}"
.param VDD={supply:g}
.options device temp={temperature:g}
VVPWR VPWR 0 {{VDD}}
VVPB VPB 0 {{VDD}}
VVGND VGND 0 0
VVNB VNB 0 0
VRESET RESET_N 0 PWL(0 0 1n 0 1.02n {{VDD}})
VREF REF 0 PULSE(0 {{VDD}} 10n {edge_ps:g}p {edge_ps:g}p 20n 40n)
VDIV CLKDIVR 0 PULSE(0 {{VDD}} {10+phase_ps/1000:g}n {edge_ps:g}p {edge_ps:g}p 20n 40n)
CUP BBPD[1] 0 {loads[1]:.12g}p
CDN BBPD[0] 0 {loads[0]:.12g}p
XBBPD BBPD[0] BBPD[1] CLKDIVR REF RESET_N VGND VNB VPB VPWR IntegerPLL_BBPD
.options timeint reltol=1e-5 abstol=1e-9 method=gear
.tran 5p 90n 0 5p
.print tran format=std v(REF) v(CLKDIVR) v(BBPD[0]) v(BBPD[1]) i(VVPWR)
.end
'''
    verify_ideal_rails(text)
    return text


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--baseline-manifest',type=Path,required=True)
    parser.add_argument('--qualification',type=Path,required=True)
    parser.add_argument('--electrical',type=Path,required=True)
    parser.add_argument('--pdk',type=Path,required=True)
    parser.add_argument('--interface-assessment',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--xyce',type=Path,default=Path('/opt/xyce/bin/Xyce'))
    parser.add_argument('--jobs',type=int,default=4)
    parser.add_argument('--phases-ps',default='50')
    parser.add_argument('--edges-ps',default='20')
    args=parser.parse_args()
    if args.output.exists() or not 1 <= args.jobs <= 4:
        parser.error('Use a fresh output directory and 1–4 workers')
    phases=[float(v) for v in args.phases_ps.split(',')]; edges=[float(v) for v in args.edges_ps.split(',')]
    if (not phases or not edges or len(set(phases))!=len(phases) or len(set(edges))!=len(edges)
            or any(not math.isfinite(v) or not -5000 <= v <= 5000 for v in phases)
            or any(not math.isfinite(v) or not 0 < v <= 1000 for v in edges)):
        parser.error('Empty or repeated phase/slew list')
    qualified=json.loads(args.qualification.read_text())
    if qualified.get('model_equivalence_screen_passed') is not True:
        raise RuntimeError('Missing qualified diode comparison')
    evidence=qualified['evidence_sha256']; verify(evidence)
    if str(args.electrical.resolve()) not in evidence:
        raise RuntimeError('Unqualified electrical corner parameters')
    model=args.pdk/'libs.ref/sky130_fd_pr/spice/sky130_fd_pr__diode_pw2nd_05v5.model.spice'
    if sha(model)!=MODEL_SHA256:
        raise RuntimeError('Changed PDK diode model')
    params=json.loads(args.electrical.read_text())['corner_parameters']
    baseline=json.loads(args.baseline_manifest.read_text())['sha256']; verify(baseline)
    interface=json.loads(args.interface_assessment.read_text())
    verify(interface['sha256']); verify(interface['artifact_sha256'])
    # Use the exact independently extracted receiver pin + routed-wire loads.
    loads=[interface['input_loads_pf'][p]['total_pf'] for p in ('BBPD[0]','BBPD[1]')]
    translated,count=translate(args.source.read_text())
    if count!=1:
        raise RuntimeError('Expected one physical REF antenna diode')
    reduced,removed=reduce(translated)
    out=args.output.resolve(); out.mkdir(parents=True)
    models={}; jobs=[]
    for corner in ('ss','tt','ff','sf','fs'):
        aj,pj=params[corner]
        for temperature in (-40,27,125):
            p=out/f'bbpd_{corner}_{temperature}.spice'
            p.write_text(reduced+'\n'+translated_model(temperature,aj,pj)
                         +f'.subckt {REPLACEMENT} N P\nD0 N P openpll_pw2nd_candidate area=.4347 pj=2.64\n.ends {REPLACEMENT}\n')
            models[corner,temperature]=p
            for supply in (1.62,1.8,1.95):
                for phase in phases:
                    for edge in edges:
                        d=out/f'{corner}_{supply:g}V_{temperature:g}C_phase{phase:g}ps_edge{edge:g}ps';d.mkdir()
                        c=d/'loaded.cir';c.write_text(deck(args.pdk,p,corner,supply,temperature,phase,edge,loads))
                        jobs.append((d,c,corner,supply,temperature,phase,edge))
    pinned={**baseline,**evidence,**interface['sha256'],**interface['artifact_sha256']}
    for p in [args.source,args.baseline_manifest,args.qualification,args.electrical,args.interface_assessment,
              args.xyce,Path(__file__),ROOT/'verification/timing450/reduce_bbpd_fixed_rails.py',
              ROOT/'scripts/translate_sky130_diode.py',ROOT/'scripts/sky130_diode_translation_probe.py',
              model,*models.values(),*(j[1] for j in jobs)]:
        pinned[str(p.resolve())]=sha(p)
    verify(pinned)
    (out/'input_manifest.json').write_text(json.dumps({'sha256':pinned,'removed_instances':removed,
             'requested_points':len(jobs),'loads_pf':loads,'phase_ps':phases,'edge_ps':edges},indent=2)+'\n')
    def run(job):
        d,c,corner,supply,temperature,phase,edge=job
        with (d/'run.log').open('w') as log:
            # No observation timeout is treated as termination or restart.
            result=subprocess.run([str(args.xyce),'-linsolv','KLU','-quiet','-o',str(d/'loaded'),str(c)],stdout=log,stderr=subprocess.STDOUT)
        log=(d/'run.log').read_text()
        a={'corner':corner,'supply_v':supply,'temperature_c':temperature,'phase_ps':phase,'edge_ps':edge,
           'simulation_completed':False,'exit_code':result.returncode,'release_qualified':False,'selected':False}
        if result.returncode==0 and not any(v in log for v in ('Unrecognized dot line','Simulation aborted','Netlist error')):
            try:
                a['output_waveforms']=measure(read_rows(d/'loaded.prn'),supply)
                a['simulation_completed']=True
                a['two_full_pulses_observed']=all(v['complete_two_pulses'] for v in a['output_waveforms'].values())
            except (RuntimeError,ValueError,OSError) as e:
                a['error']=str(e)
        a['sha256']={str(p):sha(p) for p in (c,d/'run.log',d/'loaded.prn') if p.exists()}
        (d/'assessment.json').write_text(json.dumps(a,indent=2)+'\n')
        print(json.dumps({k:v for k,v in a.items() if k not in ('sha256','output_waveforms')}),flush=True)
        return d,a
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for result in pool.map(run,jobs):results.append(result)
    verify(pinned)
    success=all(a['simulation_completed'] for _,a in results)
    aggregate={'requested_points':len(jobs),'completed_points':sum(a['simulation_completed'] for _,a in results),
               'all_simulations_completed':success,'all_two_full_pulses_observed':success and all(a.get('two_full_pulses_observed',False) for _,a in results),
               'release_qualified':False,'selected':False,'scope':'Lumped measured load; reduced fixed-rail MOS; ideal supplies; deterministic signal voltages',
               'limitations':['No nonlinear receiver coupling or full resistance','No current/power/noise/nonideal supply qualification','Phase/slew coverage limited to explicit request'],
               'input_manifest_sha256':sha(out/'input_manifest.json'),
               'receipts':{str(d/'assessment.json'):sha(d/'assessment.json') for d,_ in results}}
    (out/'assessment.json').write_text(json.dumps(aggregate,indent=2)+'\n')
    if not success:raise RuntimeError('One or more requested native simulations did not complete')

if __name__=='__main__':main()
