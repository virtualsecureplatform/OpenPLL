#!/usr/bin/env python3
"""Check fresh raw HS-geometry DC/AC/charge/noise evidence before model use."""
from decimal import Decimal
import json
import math
from pathlib import Path
import re
import signal
import sys
import time
from run_dco_qualification import ROOT,sha,save

sys.path.insert(0,str(ROOT/'scripts'))
from pvt_release_gate import has_xyce_temperature
from sky130_diode_translation_probe import data_rows,charge

CORNERS=['tt','ff','ss','sf','fs']
TEMPS=[-40,27,125]
BIASES=[0,.81,1.62,1.8,1.98]
LIMITS=dict(dc=.001,ac_complex=.0001,ac_imaginary=.0001,rising_charge=.001,falling_charge=.001,noise_psd=.001)


def coverage(jobs):
    actual=[(r['kind'],r['corner'],r['temperature_c'],r['bias_v'],r['label'],r['simulator']) for r in jobs]
    expected=set()
    for corner in CORNERS:
        for temperature in TEMPS:
            for simulator in ['ngspice','xyce']:
                for label in ['dc',*[f'ac_{v:g}V' for v in BIASES],'tran']:
                    expected.add(('electrical',corner,temperature,None,label,simulator))
                for bias in BIASES:
                    expected.add(('noise',corner,temperature,bias,'noise',simulator))
    assert len(actual)==len(expected)==360 and set(actual)==expected


def geometry(text,simulator,temperature):
    prefix='XD 0 bias sky130_fd_pr__diode_pw2nd_05v5' if simulator=='ngspice' else 'D0 0 bias openpll_pw2nd_candidate'
    instances=[line for line in text.splitlines() if line.startswith(prefix+' ')]
    assert len(instances)==1
    params=dict(re.findall(r'\b(area|perim|pj)=([^\s]+)',instances[0]))
    assert Decimal(params['area'])==Decimal('.6417')
    key='perim' if simulator=='ngspice' else 'pj'
    assert set(params)=={'area',key} and Decimal(params[key])==Decimal('3.24')
    if simulator=='xyce':
        assert has_xyce_temperature(text,temperature)
    else:
        directives=re.findall(r'^\.temp\s+(\S+)\s*$',text,re.M|re.I)
        assert len(directives)==1 and float(directives[0])==temperature


def aligned(a,b,count):
    assert len(a)==len(b)==count
    assert all(all(math.isfinite(v) for v in row) for row in a+b)


def main():
    out=ROOT/'build/timing400/release_001/hs_diode_geometry_comparison_001'
    plan_path=out/'plan.json'
    plan=json.loads(plan_path.read_text())
    deadline=json.loads((out/'owner.json').read_text())['absolute_deadline_uptime']
    left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left>0
    signal.alarm(max(1,math.floor(left)))
    receipt=json.loads((out/'native_completion.json').read_text())
    assert receipt['all_native_analyses_completed'] and len(receipt['results'])==360
    assert all(r['exit_code']==0 for r in receipt['results'])
    for p,digest in {**receipt['input_sha256'],**receipt['artifacts'],**plan['prepared_deck_sha256']}.items():
        assert sha(Path(p))==digest,p
    coverage(plan['jobs'])
    parsed={}
    sample_text=None
    for row in plan['jobs']:
        text=Path(row['deck']).read_text()
        geometry(text,row['simulator'],row['temperature_c'])
        if sample_text is None and row['simulator']=='xyce':
            sample_text=(text,row['temperature_c'])
        stem=Path(row['output_stem'])
        suffix='.NOISE.prn' if row['kind']=='noise' else ('.FD.prn' if row['label'].startswith('ac_') else '.prn')
        data=Path(row['log']) if row['simulator']=='ngspice' else Path(str(stem)+suffix)
        rows=data_rows(data)
        assert rows and all(all(math.isfinite(v) for v in r) for r in rows),data
        key=(row['kind'],row['corner'],row['temperature_c'],row['bias_v'],row['label'],row['simulator'])
        parsed[key]=rows
    metrics=[]
    for corner in CORNERS:
        for temperature in TEMPS:
            def pair(label):
                return [parsed['electrical',corner,temperature,None,label,s] for s in ['ngspice','xyce']]
            a,b=pair('dc')
            aligned(a,b,110)
            assert all(abs(x[-2]-y[-2])<1e-10 for x,y in zip(a,b))
            errors=dict(dc=max(abs(x[-1]-y[-1])/max(abs(x[-1]),1e-18) for x,y in zip(a,b)))
            complex_errors=[]
            imaginary_errors=[]
            for bias in BIASES:
                a,b=pair(f'ac_{bias:g}V')
                aligned(a,b,21)
                assert all(abs(x[0]/y[0]-1)<1e-6 for x,y in zip(a,b))
                complex_errors.extend(abs(complex(*x[-2:])-complex(*y[-2:]))/abs(complex(*x[-2:])) for x,y in zip(a,b))
                imaginary_errors.extend(abs(x[-1]-y[-1])/abs(x[-1]) for x,y in zip(a,b))
            errors.update(ac_complex=max(complex_errors),ac_imaginary=max(imaginary_errors))
            a,b=pair('tran')
            for label,start,stop in [('rising_charge',.9e-9,1.5e-9),('falling_charge',5e-9,5.6e-9)]:
                qa,qb=charge(a,start,stop),charge(b,start,stop)
                errors[label]=abs(qa-qb)/abs(qa)
            metrics.append(dict(corner=corner,temperature_c=temperature,errors=errors,
                passed=all(math.isfinite(v) and 0<=v<LIMITS[k] for k,v in errors.items())))
    noises=[]
    for corner in CORNERS:
        for temperature in TEMPS:
            for bias in BIASES:
                a,b=[parsed['noise',corner,temperature,bias,'noise',s] for s in ['ngspice','xyce']]
                aligned(a,b,21)
                assert all(x[-1]>0 and y[-1]>0 and abs(x[0]/y[0]-1)<1e-6 for x,y in zip(a,b))
                error=max(abs(x[-1]-y[-1])/x[-1] for x,y in zip(a,b))
                noises.append(dict(corner=corner,temperature_c=temperature,bias_v=bias,noise_psd_error=error,
                    passed=math.isfinite(error) and 0<=error<LIMITS['noise_psd']))
    negative=[]
    for label,action in [('missing_case',lambda:coverage(plan['jobs'][:-1])),
        ('wrong_geometry',lambda:geometry(sample_text[0].replace('area=0.6417','area=0.4347'), 'xyce',sample_text[1]))]:
        try:
            action()
        except AssertionError:
            negative.append(label)
        else:
            raise AssertionError('fault control accepted: '+label)
    assert len(metrics)==15 and len(noises)==75
    passed=all(r['passed'] for r in metrics+noises)
    save(out/'comparison_metrics.json',dict(electrical=metrics,noise=noises))
    evidence=[Path(__file__).resolve(),ROOT/'scripts/pvt_release_gate.py',ROOT/'scripts/sky130_diode_translation_probe.py',
        plan_path,out/'native_completion.json',out/'comparison_metrics.json']
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in evidence},
        artifacts={str(out/'comparison_metrics.json'):sha(out/'comparison_metrics.json')},
        model_equivalence_screen_passed=passed,effective_geometry=dict(area_um2='.6417',perimeter_um='3.24'),
        required_native_analyses=360,electrical_cases=15,noise_bias_cases=75,corners=CORNERS,temperatures_c=TEMPS,
        biases_v=BIASES,limits=LIMITS,negative_controls_rejected=negative,
        reference_geometry='explicit',reference_noise_units='V^2/Hz (set sqrnoise)',
        dc_bias_range_v=[-.2,1.98],ac_noise_frequency_range_hz=[1e6,1e10],
        scope='Only observed effective diode area .6417um2/perimeter3.24um at tested PVT/bias/frequency; no PLL signoff.',
        model_integrated_into_physical_pll=False,pll_release_qualified=False,release_qualified=False))
    print('HS geometry model-equivalence comparison:',passed,'; electrical15,noise75; PLL qualification remains open.')
    return 0 if passed else 1


if __name__=='__main__':
    raise SystemExit(main())
