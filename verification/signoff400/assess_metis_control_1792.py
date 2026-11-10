"""Assess normally completed ordering controls against exact divider voltages."""
import csv,json,math
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity

def run():
    source=ROOT/'build/signoff400/selected_init_trace_control_1791'
    build=ROOT/'build/tools/xyce_metis_ordering_1790/assessment.json';r=json.loads(build.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    paths=[build,Path(__file__).resolve(),Path(__file__).with_name('check_metis_ordering_1791.py')];results={}
    for label in ['base','trace']:
        p=source/label;o=json.loads((p/'native.process.json').read_text())
        if identity(o['pid'])==o['birth']:raise ValueError('completed workers required')
        log=(p/'native.log').read_text()
        if '***** Solution Summary *****' not in log or '***** Total Elapsed Run Time:' not in log:raise ValueError('normal final native summaries required')
        if label=='trace' and 'OPENPLL_ORDERING requested=METIS used=3' not in log:raise ValueError('METIS not used')
        rows=list(csv.reader((p/'dc.csv').read_text().splitlines()))
        if len(rows)!=2 or rows[0]!=['V(N0)','V(N3500)','V(N7000)']:raise ValueError('one explicit completed divider row required')
        actual=list(map(float,rows[1]));expected=[1,.75,.5]
        errors=[abs(a-b)/math.ulp(b)for a,b in zip(actual,expected)]
        if len(actual)!=3 or any(not math.isfinite(v)or v>1 for v in errors):raise ValueError('divider exceeds one-ULP analytical bound')
        results[label]=dict(values=actual,error_ULP=errors)
        paths += [p/n for n in ['native.process.json','native.log','control.spice','dc.csv']]
    out=ROOT/'build/signoff400/selected_metis_control_assessment_1792';out.mkdir(exist_ok=False)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p)for p in paths},analytical_divider_within_one_ULP=True,METIS_ordering_observed=True,results=results,native_cases_rerun=False,exact_output_equality=False,prior_checker_failure='Both native workers completed; strict output equality rejected a one-ULP baseline error at 0.5V.',full_backend_qualified=False,release_ready=False))

if __name__=='__main__':run()
