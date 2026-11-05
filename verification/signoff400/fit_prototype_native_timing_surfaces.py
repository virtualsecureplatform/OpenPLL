"""Finite native timing surfaces with measured holdout extensions; no universal error bound."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
from common_v3 import save, sha, verify


def surface(points):
    xs=sorted({x for x,y,v in points});ys=sorted({y for x,y,v in points})
    if len(xs)!=3 or len(ys)!=3:raise ValueError('complete three-by-three retained grid required')
    samples=defaultdict(list)
    for x,y,value in points:
        if not all(math.isfinite(v) for v in (x,y,value)) or x<0 or y<0:raise ValueError('invalid native observation')
        samples[x,y].append(value)
    if set(samples)!={(x,y) for x in xs for y in ys}:raise ValueError('missing native grid point')
    return dict(input_slew_20_to_80_ns=xs,external_load_pf=ys,
                lower_ns=[[min(samples[x,y]) for y in ys] for x in xs],
                upper_ns=[[max(samples[x,y]) for y in ys] for x in xs])


def interval(table,x,y):
    xs,ys=table['input_slew_20_to_80_ns'],table['external_load_pf']
    if not xs[0]<=x<=xs[-1] or not ys[0]<=y<=ys[-1]:raise ValueError('native holdout outside retained axes')
    i=next(i for i in range(len(xs)-1) if xs[i]<=x<=xs[i+1])
    j=next(j for j in range(len(ys)-1) if ys[j]<=y<=ys[j+1])
    a=(x-xs[i])/(xs[i+1]-xs[i]);b=(y-ys[j])/(ys[j+1]-ys[j])
    def value(z):return (1-a)*(1-b)*z[i][j]+a*(1-b)*z[i+1][j]+(1-a)*b*z[i][j+1]+a*b*z[i+1][j+1]
    return value(table['lower_ns']),value(table['upper_ns'])


def metrics(f,record,kind):
    """Return related pin, timing type, output direction, metric, samples."""
    if kind=='combinational':
        for rising,label in ((False,'fall'),(True,'rise')):
            direction='rise' if rising!=f['inverted'] else 'fall'
            yield f['input'],'combinational',direction,'delay',record['input_'+label+'_delay_ns']
        for direction in ('rise','fall'):
            yield f['input'],'combinational',direction,'slew',record['output_'+direction+'_slew_ns']
    else:
        for direction in ('rise','fall'):
            name='clock_to_q_'+direction+'_ns'
            if name in record:yield 'CLK','rising_edge',direction,'delay',record[name]
        if 'assertion_to_q_ns' in record:
            direction='rise' if f['reset_value'] else 'fall'
            yield f['control_pin'],'preset' if f['reset_value'] else 'clear',direction,'delay',record['assertion_to_q_ns']
        for direction,suffix in (('rise','20_80'),('fall','80_20')):
            name='output_'+direction+'_'+suffix+'_ns'
            if name not in record:continue
            # Assertion fixtures include both clock-triggered and control-
            # triggered slews. Retain their envelope for both timing arcs.
            yield 'CLK','rising_edge',direction,'slew',record[name]
            if f['kind']=='async_assert' and direction==('rise' if f['reset_value'] else 'fall'):
                yield f['control_pin'],'preset' if f['reset_value'] else 'clear',direction,'slew',record[name]


def run(retained, combinational, sequential, output):
    receipt=retained/'assessment.json';r=json.loads(receipt.read_text());verify(r['artifacts'])
    observations=retained/'observations.json';rows=json.loads(observations.read_text())
    paths=[receipt,observations,Path(__file__).resolve()];points=defaultdict(list);holdouts=defaultdict(list)
    def key(corner,f,pin,timing,direction,metric):
        return (corner,f['master'],pin,f.get('output','Q'),timing,direction,metric)
    for row in rows:
        f=row['fixture'];record=row['observed']
        if not record['passed']:raise ValueError('passing retained native events required')
        for pin,timing,direction,metric,values in metrics(f,record,row['kind']):
            k=key(row['corner'],f,pin,timing,direction,metric)
            points[k].extend((row['input_slew_20_to_80_ns'],row['external_load_pf'],v) for v in values)
    expected={'tt','ff','ss','sf','fs'}
    for directories,kind in ((combinational,'combinational'),(sequential,'sequential')):
        corners=set()
        for directory in directories:
            cr=directory/'assessment.json';c=json.loads(cr.read_text());verify(c['input_sha256']);verify(c['artifacts'])
            if not c['all_paired_native_events_reviewed'] or c['corner'] in corners:raise ValueError('unique reviewed corner comparison required')
            if c['input_sha256'].get(str(receipt))!=sha(receipt):raise ValueError('holdout retained-bank lineage mismatch')
            corners.add(c['corner']);detail=directory/'comparisons.json';paths.extend((cr,detail))
            for row in json.loads(detail.read_text()):
                f=row['fixture'];x=f['full_ramp_ps']*.6/1000;y=f['external_load_pf']
                if kind=='combinational':
                    for comparison in row['comparisons']:
                        direction='rise' if comparison['input_rising']!=f['inverted'] else 'fall'
                        for model in ('retained','final_C'):
                            for metric in ('delay','slew'):
                                k=key(c['corner'],f,f['input'],'combinational',direction,metric)
                                holdouts[k].append(dict(x=x,y=y,model=model,values=comparison[model][metric+'_ns']))
                else:
                    for model in ('retained','final_C'):
                        for pin,timing,direction,metric,values in metrics(f,row[model],kind):
                            k=key(c['corner'],f,pin,timing,direction,metric)
                            holdouts[k].append(dict(x=x,y=y,model=model,values=values))
        if corners!=expected:raise ValueError('five-corner comparisons required')
    if set(points)!=set(holdouts):raise ValueError('every timing surface needs a matching native holdout')
    result=[]
    for k,observed in sorted(points.items()):
        table=surface(observed);lower=upper=0.;residuals=[]
        for h in holdouts[k]:
            lo,hi=interval(table,h['x'],h['y'])
            if not h['values'] or not all(math.isfinite(v) for v in h['values']):raise ValueError('finite complete holdout required')
            below=max(0,lo-min(h['values']));above=max(0,max(h['values'])-hi)
            lower=max(lower,below);upper=max(upper,above)
            residuals.append(dict(h,interpolated_interval_ns=[lo,hi],lower_extension_ns=below,upper_extension_ns=above))
        corner,master,pin,out,timing,direction,metric=k
        result.append(dict(corner=corner,master=master,related_pin=pin,output=out,timing_type=timing,
            output_direction=direction,metric=metric,native_grid=table,
            observed_lower_extension_ns=lower,observed_upper_extension_ns=upper,
            retained_native_samples=len(observed),native_holdouts=residuals,
            numerical_error_margin_included=False,continuous_error_bound_proved=False))
    pins={str(p):sha(p) for p in paths};verify(pins)
    output.mkdir(parents=True,exist_ok=False);detail=output/'surfaces.json';save(detail,result)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         corners=sorted(expected),timing_surfaces=len(result),masters=len({x['master'] for x in result}),
         all_retained_grid_samples_and_holdouts_preserved=True,
         observed_holdout_extensions_are_not_universal_error_bounds=True,
         maximum_sampled_lower_extension_ps=max(x['observed_lower_extension_ns']*1000 for x in result),
         maximum_sampled_upper_extension_ps=max(x['observed_upper_extension_ns']*1000 for x in result),
         capture_constraints_included=False,final_routed_load_and_slew_enclosure_qualified=False,
         native_timing_views_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('retained','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--combinational',type=Path,nargs=5,required=True)
    p.add_argument('--sequential',type=Path,nargs=5,required=True)
    a=p.parse_args();run(a.retained.resolve(),[x.resolve() for x in a.combinational],
                        [x.resolve() for x in a.sequential],a.output.resolve())
