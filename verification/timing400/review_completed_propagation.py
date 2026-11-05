#!/usr/bin/env python3
"""Review completed native observations and independently audit ambiguous edges."""
import argparse
from decimal import Decimal,localcontext
import json
from pathlib import Path

from check_compact_clock_tree import verify
from run_dco_qualification import sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True,type=Path)
    parser.add_argument('--result',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();out=args.output.resolve();assert not out.exists()
    source=args.result.resolve();report=verify(source);plan=json.loads(args.plan.read_text())
    cases,records=plan['fixtures'],report['records']
    assert len(cases)==len(records)==891 and report['all_native_waveform_events_terminal']
    assert all(r['case_index']==i for i,r in enumerate(records))
    ambiguous=[r['case_index'] for r in records if not r['strict_output_slew_passed']]
    wave=source.parent/'batch.prn'
    launch=json.loads((source.parent/'launch.json').read_text())
    assert not (Path('/proc')/str(launch['pid'])).exists(),'producer still exists'
    groups={}
    for positive in (False,True):
        selected=[r for r,c in zip(records,cases) if (c['external_load_pf']>0)==positive]
        groups['positive_external_load' if positive else 'zero_external_load']=dict(
            cases=len(selected),minimum_v=min(r['output_min_v'] for r in selected),
            maximum_v=max(r['output_max_v'] for r in selected),
            outside_conditional_diode_bias_range=sum(r['output_min_v']<-.2 or r['output_max_v']>1.95 for r in selected))
    series={i:[] for i in ambiguous};times=[];terminal=False
    with wave.open() as stream:
        header=stream.readline().split();assert len(header)==2+2*len(cases)
        assert header[:2]==['Index','TIME']
        for i in ambiguous:assert header[3+2*i]==f'V(OUT_{i})'
        for line in stream:
            if 'End of Xyce(TM) Simulation' in line:
                assert not terminal;terminal=True;continue
            fields=line.split()
            if not fields:continue
            assert not terminal and len(fields)==len(header) and int(fields[0])==len(times)
            t=Decimal(fields[1]);assert t.is_finite() and (not times or t>times[-1])
            times.append(t)
            for i in ambiguous:
                value=Decimal(fields[3+2*i]);assert value.is_finite();series[i].append(value)
    assert terminal and times[0]==0 and times[-1]>=Decimal('34e-9')-Decimal('1e-15')
    independent=[]
    with localcontext() as context:
        context.prec=40
        for i,values in series.items():
            observed={}
            for threshold in ('0.36','0.9','1.44'):
                level=Decimal(threshold)
                for rising,label in ((False,'fall'),(True,'rise')):
                    found=[]
                    for index,(a,b) in enumerate(zip(values,values[1:])):
                        crosses=a<level<=b if rising else b<level<=a
                        if crosses:
                            found.append((times[index]+(times[index+1]-times[index])*(level-a)/(b-a))*Decimal('1e9'))
                    key=label+'_'+threshold
                    expected=records[i]['raw_output_threshold_crossings_ns'][key]
                    assert len(found)==len(expected)
                    assert all(abs(v-Decimal(str(e)))<Decimal('1e-9') for v,e in zip(found,expected))
                    observed[key]=list(map(str,found))
            independent.append(dict(case_index=i,fixture=cases[i],decimal_threshold_crossings_ns=observed))
    repeated=[]
    for i,r in enumerate(records):
        for direction in ('input_rise_delay_ns','input_fall_delay_ns'):
            a,b=r[direction]
            repeated.append(dict(case_index=i,direction=direction,delays_ns=[a,b],difference_ps=abs(a-b)*1000))
    maximum=max(repeated,key=lambda r:r['difference_ps'])
    pins={str(p.resolve()):sha(p) for p in [Path(__file__),args.plan,source,wave]}
    out.mkdir(parents=True)
    save(out/'assessment.json',dict(input_sha256=pins,pvt=report['pvt'],
        propagation_observations_passed=report['passing'],strict_slew_observations_passed=report['strict_output_slew_passing'],
        voltage_domain_groups=groups,independently_recomputed_ambiguous_cases=independent,
        raw_rows_checked=len(times),largest_repeated_opportunity_difference=maximum,
        observations_excluded_or_averaged=False,effective_load_or_voltage_enclosure_qualified=False,
        physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print(f'Reviewed891terminal observations; independently recomputed{len(ambiguous)}ambiguous cases.')


if __name__=='__main__':
    main()
