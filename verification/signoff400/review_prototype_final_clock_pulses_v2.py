"""Independently inspect final loaded pulse waveforms; preserve fixture and capture failures."""
import argparse
from fractions import Fraction as F
import json
import math
from pathlib import Path
from common_v3 import save, sha, verify
from audit_hierarchical_capacitance import number
from audit_prototype_final_campaign_coverage_v3 import merge_pins


def edges(rows,column,level,rising):
    result=[]
    for a,b in zip(rows,rows[1:]):
        if (a[column]<level<=b[column] if rising else b[column]<level<=a[column]):
            result.append(a[0]+(b[0]-a[0])*(level-a[column])/(b[column]-a[column]))
    return result


def observe(rows,kind,width,index,n,ramp):
    q=index+1;clk=n+index+1;w=width/1000
    expected_rise=[3,10] if kind=='high' else [3,10+w]
    expected_fall=[4,10+w] if kind=='high' else [10]
    clock_rise=edges(rows,clk,.9,True);clock_fall=edges(rows,clk,.9,False)
    for observed,expected in ((clock_rise,expected_rise),(clock_fall,expected_fall)):
        if len(observed)!=len(expected) or any(abs(a*1e9-b)>1e-3 for a,b in zip(observed,expected)):
            raise ValueError('actual clock edges differ from settled pulse fixture')
    for rising in (False,True):
        lo=edges(rows,clk,.36,rising);hi=edges(rows,clk,1.44,rising)
        if len(lo)!=len(hi) or not lo or any(abs(abs(b-a)*1e12-.6*ramp)>1 for a,b in zip(lo,hi)):
            raise ValueError('actual clock slew differs from declared endpoint')
    old=int(kind=='low');new=1-old
    def stable(a,b,state):
        values=[row[q] for row in rows if a<=row[0]*1e9<=b]
        return bool(values) and (min(values)>=1.62 if state else max(values)<=.18)
    pre=stable(9,9.3,old);final=stable(16,17,new)
    observed=[(t,rising) for rising in (False,True) for t in edges(rows,q,.9,rising) if t>=9e-9]
    observed.sort()
    capture_clock=clock_rise[1]
    captured=pre and final and len(observed)==1 and observed[0][1]==bool(new) and observed[0][0]>=capture_clock
    return dict(kind=kind,nominal_width_ps=width,pre_state_verified=pre,final_state_verified=final,
         full_output_trace_capture_verified=captured,output_edges=[dict(time_ns=t*1e9,rising=r) for t,r in observed],
         actual_capture_clock_ns=capture_clock*1e9,pretest_window_ns=[9,9.3],final_window_ns=[16,17])


def thresholds(cases):
    result={}
    for kind in ('high','low'):
        rows=sorted((c for c in cases if c['kind']==kind),key=lambda c:c['nominal_width_ps'])
        passing=[r['nominal_width_ps'] for i,r in enumerate(rows) if all(x['full_output_trace_capture_verified'] for x in rows[i:])]
        result[kind]=dict(smallest_tested_width_with_all_larger_samples_passing_ps=min(passing,default=None),
             failing_tested_widths_ps=[r['nominal_width_ps'] for r in rows if not r['full_output_trace_capture_verified']],
             continuous_minimum_pulse_width_qualified=False)
    return result


def point(directory,pins=None):
    receipt=directory/'assessment.json';r=json.loads(receipt.read_text())
    if pins is None:verify(r['input_sha256']);verify(r['artifacts'])
    else:merge_pins(pins,r)
    if 'Using KLU as Direct Linear Solver' not in (directory/'native.log').read_text():raise ValueError('KLU banner missing')
    data=directory/'waveform.dat';declared=json.loads((directory/'observations.json').read_text())
    order=[(k,w) for k in ('high','low') for w in (400,600,1000,1600)]
    if r['cases']!=8 or [(c['kind'],c['nominal_width_ps']) for c in declared]!=order:raise ValueError('exact eight-case pulse grid required')
    rows=[]
    with data.open() as stream:
        if stream.readline().split()!=['time']+[f'v(q{i})' for i in range(8)]+[f'v(clk{i})' for i in range(8)]:
            raise ValueError('pulse waveform columns differ')
        for line in stream:
            values=tuple(map(float,line.split()))
            if len(values)!=17 or not all(map(math.isfinite,values)) or rows and values[0]<=rows[-1][0]:
                raise ValueError('invalid pulse waveform samples')
            rows.append(values)
    if not rows or rows[0][0]!=0 or abs(rows[-1][0]-18e-9)>1e-15:raise ValueError('complete settled pulse horizon required')
    decks=[Path(p) for p in r['input_sha256'] if p.endswith('/pulse_grid.cir')]
    if len(decks)!=1:raise ValueError('unique pinned pulse deck required')
    loads={}
    for line in decks[0].read_text().splitlines():
        f=line.split()
        if f and f[0].startswith('CLOAD'):
            i=int(f[0][5:])
            if i in loads or len(f)!=4 or f[1:3]!=['Q'+str(i),'0']:raise ValueError('pulse load topology differs')
            loads[i]=number(f[3])
    if set(loads)!=set(range(8)) or any(v!=F(str(r['load_fF']))/10**15 for v in loads.values()):
        raise ValueError('reported pulse load differs from actual deck')
    cases=[observe(rows,k,w,i,8,r['clock_full_ramp_ps']) for i,(k,w) in enumerate(order)]
    return dict(corner=r['corner'],master=r['master'],load_fF=r['load_fF'],clock_full_ramp_ps=r['clock_full_ramp_ps'],
                cases=cases,sampled_thresholds=thresholds(cases))


def run(campaign,coverage,output):
    rr=campaign/'assessment.json';cr=coverage/'assessment.json';r,c=[json.loads(p.read_text()) for p in (rr,cr)]
    if not c['exact_native_case_coverage_verified'] or c['native_cases']!=400 or c['complete_native_operating_points']!=50:
        raise ValueError('complete audited final pulse coverage required')
    if c['input_sha256'].get(str(rr))!=sha(rr):raise ValueError('pulse coverage lineage differs')
    points=coverage/'points.json';pins={str(p):sha(p) for p in (rr,cr,points,Path(__file__).resolve())};results=[]
    for record in (r,c):merge_pins(pins,record)
    helper=Path(__file__).with_name('audit_prototype_final_campaign_coverage_v3.py');pins[str(helper)]=sha(helper)
    for row in json.loads(points.read_text()):
        directory=Path(row['directory']);rp=directory/'assessment.json'
        if c['input_sha256'].get(str(rp))!=sha(rp):raise ValueError('audited pulse point changed')
        results.append(point(directory,pins))
        if pins[str(rp)]!=sha(rp):raise ValueError('point changed during waveform review')
    verify(pins);output.mkdir(parents=True,exist_ok=False);detail=output/'observations.json';save(detail,results)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},native_cases=400,
         all_pretest_states_verified=all(x['pre_state_verified'] for row in results for x in row['cases']),
         capture_failures=sum(not x['full_output_trace_capture_verified'] for row in results for x in row['cases']),
         all_grids_have_passing_high_and_low_samples=all(row['sampled_thresholds'][k]['smallest_tested_width_with_all_larger_samples_passing_ps'] is not None for row in results for k in ('high','low')),
         all_actual_clock_edges_slews_and_loads_verified=True,numerical_uncertainty_bounded=False,
         final_load_and_slew_envelope_qualified=False,release_ready=False))


def run_point(directory,output):
    result=point(directory)
    paths=[directory/'assessment.json',directory/'waveform.dat',directory/'observations.json',Path(__file__).resolve()]
    pins={str(p):sha(p) for p in paths};verify(pins)
    output.mkdir(parents=True,exist_ok=False);detail=output/'observations.json';save(detail,result)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},native_cases=8,
         scope='one completed native pulse point; complete campaign coverage not claimed',
         all_pretest_states_verified=all(x['pre_state_verified'] for x in result['cases']),
         capture_failures=sum(not x['full_output_trace_capture_verified'] for x in result['cases']),
         all_actual_clock_edges_slews_and_loads_verified=True,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('campaign','coverage','point'):p.add_argument('--'+n,type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.point and not (a.campaign or a.coverage):run_point(a.point.resolve(),a.output.resolve())
    elif a.campaign and a.coverage and not a.point:run(a.campaign.resolve(),a.coverage.resolve(),a.output.resolve())
    else:p.error('one point or campaign plus coverage required')
