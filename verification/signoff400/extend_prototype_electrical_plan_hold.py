"""Attach two explicitly measured ordinary-data deficits to a pinned branch plan."""
import argparse
import json
from pathlib import Path
from common_v3 import save,sha,verify

def run(plan,inventory,budgets,output):
    pp=plan/'plan.json';p=json.loads(pp.read_text());verify(p['input_sha256'])
    ir=inventory/'assessment.json';a=json.loads(ir.read_text());verify(a['artifacts'])
    design=inventory/'routed.json';m=json.loads(design.read_text())['modules']['IntegerPLL_ProgrammedCore'];cells={n.lstrip('\\'):c for n,c in m['cells'].items()}
    targets={};inputs={**p['input_sha256'],str(pp):sha(pp),str(ir):sha(ir),str(design):sha(design),str(Path(__file__).resolve()):sha(Path(__file__).resolve())}
    for directory in budgets:
        receipt=directory/'assessment.json';record=json.loads(receipt.read_text());verify(record['input_sha256']);verify(record['artifacts'])
        if record['input_sha256'].get(str(ir))!=sha(ir):raise ValueError('different routed state inventory')
        paths=directory/'paths.json'
        for row in json.loads(paths.read_text()):
            name=row['endpoint']
            if row['kind']=='min' and row['slack_ns']<0 and name!='$auto$ff.cc:337:slice$17893':
                if row['slack_ns']<-.02:raise ValueError('residual short path exceeds bounded one-buffer repair')
                targets[name]=dict(capture_cell=name,capture_pin='D',capture_master=cells[name]['type'],buffers=1)
        inputs.update({str(receipt):sha(receipt),str(paths):sha(paths)})
    if set(targets)!={'$auto$ff.cc:337:slice$17246','$auto$ff.cc:337:slice$17346'}:raise ValueError('expected two ordinary REF-domain deficits')
    verify(inputs);output.mkdir(parents=True,exist_ok=False);p.update(input_sha256=inputs,short_data_targets=list(targets.values()),first_stage_CDC_aperture_excluded_from_ordinary_hold_repair=True)
    save(output/'plan.json',p)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('plan','inventory','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--budgets',type=Path,action='append',required=True)
    a=p.parse_args();run(a.plan.resolve(),a.inventory.resolve(),[x.resolve() for x in a.budgets],a.output.resolve())
