#!/usr/bin/env python3
"""Independent Decimal conservation audit of saved phase-bridge traces."""
import argparse
import csv
from decimal import Decimal,localcontext
import json
from pathlib import Path

from run_dco_qualification import sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validation',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args()
    if a.output.exists():parser.error('fresh receipt required')
    report_path=a.validation.resolve()/'assessment.json'
    report=json.loads(report_path.read_text())
    assert report['cases']==report['passed']==16 and report['synthetic_component_checks_only']
    assert report['whole_pll_qualification_cases_passed']==0 and not report['release_qualified']
    assert not report['calibration_model_qualified'] and not report['interface_model_qualified']
    pins={str(report_path):sha(report_path),str(Path(__file__).resolve()):sha(__file__)}
    for group in [report['sha256'],*[row['sha256'] for row in report['records'].values()]]:
        for path,digest in group.items():
            assert sha(path)==digest,path
            pins[path]=digest
    positive={};negative={}
    with localcontext() as context:
        context.prec=60
        denominator=Decimal(10**15)
        for name,record in report['records'].items():
            directory=a.validation.resolve()/name
            log=(directory/'run.log').read_text()
            if record.get('negative_control'):
                assert record['returncode']!=0 and 'PLL400_PHASE_ERROR:' in log
                assert record['expected_error'] in log and 'BENCH_END' not in log
                negative[name]=record['expected_error']
                continue
            assert record['returncode']==0 and 'PLL400_PHASE_ERROR:' not in log and 'BENCH_END' in log
            lookup={}
            for line in (directory/'synthetic.table').read_text().splitlines():
                coarse,fine,frequency=map(int,line.split())
                assert (coarse,fine) not in lookup and frequency>0
                lookup[coarse,fine]=frequency
            phase=Decimal(0);frequency=0;last=0;epoch_edges=0;total_edges=0;level=1;last_edge=-1
            max_residual=Decimal(0)
            for row in csv.DictReader((directory/'trace.csv').open()):
                now=int(row['time_ps']);assert now>=last
                phase+=Decimal((now-last)*frequency)/denominator
                last=now
                event=row['event'];observed_level=int(row['level'])
                if event=='RESET':
                    assert observed_level==1 and int(row['frequency_millihz'])==0
                    phase=Decimal(0);frequency=0;epoch_edges=0;level=1
                elif event=='TUNE':
                    frequency=int(row['frequency_millihz'])
                    assert frequency==lookup[int(row['coarse']),int(row['fine'])]
                    assert observed_level==level
                elif event=='EDGE':
                    assert frequency>0 and now>last_edge
                    assert int(row['frequency_millihz'])==frequency
                    epoch_edges+=1;total_edges+=1;level=1-level
                    assert observed_level==level
                    residual=phase-Decimal(epoch_edges)/2
                    # Each observed edge is the first1ps tick after its exact
                    # continuous phase crossing; the residual must remain less
                    # than the phase traversed in that one tick.
                    assert Decimal(0)<=residual<Decimal(frequency)/denominator,(name,now,str(residual))
                    max_residual=max(max_residual,residual)
                    last_edge=now
                else:
                    raise ValueError('unexpected trace event: '+event)
            assert total_edges>0
            positive[name]=dict(edges=total_edges,maximum_rounding_residual_cycles=str(max_residual),
                                exact_lookup_check_pass=True,decimal_phase_conservation_pass=True)
    assert len(positive)==8 and len(negative)==8
    a.output.parent.mkdir(parents=True,exist_ok=True)
    result=dict(independent_audit_pass=True,positive_cases=positive,negative_controls=negative,
        conserved_edges=sum(row['edges'] for row in positive.values()),sha256=pins,
        source_fraction_edge_checks=report['independent_fraction_edge_checks'],
        synthetic_component_checks_only=True,whole_pll_qualification_cases_passed=0,
        calibration_model_qualified=False,interface_model_qualified=False,release_qualified=False)
    save(a.output,result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['sha256','positive_cases','negative_controls']}))


if __name__=='__main__':
    main()
