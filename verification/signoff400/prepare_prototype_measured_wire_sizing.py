"""Size measured wire-envelope drivers by one available characterized strength step."""
import argparse
import json
from pathlib import Path
import re
from common_v3 import save,sha,verify


def run(route,electrical,inventory,obligations,views,output):
    receipts=[p/'assessment.json' for p in (route,electrical,inventory,obligations,views)]
    r,e,i,o,v=[json.loads(p.read_text()) for p in receipts]
    for a in (r,e,i,o,v):verify(a['input_sha256']);verify(a['artifacts'])
    if (not e['all_five_corners_reviewed'] or e['electrical_limits_passed']
            or i['input_sha256'].get(str(receipts[0]))!=sha(receipts[0])):
        raise ValueError('same-route all-corner nonpass required')
    proof={n:h for n,h in i['input_sha256'].items() if n.endswith('/assessment.json') and 'equivalence' in n}
    timing=[Path(n) for n in e['input_sha256'] if n.endswith('/assessment.json') and 'wire_timing_' in n]
    if len(proof)!=1 or len(timing)!=5:raise ValueError('five bound wire-RC screens required')
    for p in timing:
        a=json.loads(p.read_text())
        if not a['minmax_wire_RC_used'] or any(a['input_sha256'].get(n)!=h for n,h in proof.items()):
            raise ValueError('wire screen route/proof differs')
    graph=inventory/'routed.json';chains=obligations/'obligations.json';violations=electrical/'violations.json'
    cells={n.lstrip('\\'):c for n,c in json.loads(graph.read_text())['modules']['IntegerPLL_ProgrammedCore']['cells'].items()}
    synchronizers=json.loads(chains.read_text())['synchronizers']
    if len(synchronizers)!=13:raise ValueError('thirteen synchronizers required')
    protected={c['stages'][0]['routed_cell'].lstrip('\\') for c in synchronizers}
    libraries=[views/f'{c}_{edge}.lib' for c in ('tt','ff','ss','sf','fs') for edge in ('early','late')]
    available=[set(re.findall(r'cell \(([^)]+)\)',p.read_text())) for p in libraries]
    common=set.intersection(*available)
    drivers={}
    for row in json.loads(violations.read_text()):
        if (row['measurement_kind'],row['unit']) not in {('max_slew','ns'),('max_capacitance','pF')}:
            raise ValueError('electrical kind/unit mismatch')
        if len(row['drivers'])!=1 or not row['measured']>row['limit'] or row['slack']>=0:
            raise ValueError('measured unique-driver violation required')
        d=row['drivers'][0];name=d['cell']
        if cells[name]['type']!=d['master']:raise ValueError('source master differs')
        drivers[name]=d
    targets=[];unresolved=[]
    for name,d in sorted(drivers.items()):
        family,strength=d['master'].rsplit('_',1)
        choices=sorted((int(m.rsplit('_',1)[1]),m) for m in common
            if m.rsplit('_',1)[0]==family and int(m.rsplit('_',1)[1])>int(strength))
        if name in protected or not choices:
            unresolved.append(dict(driver=d,reason='protected_first_stage' if name in protected else 'no_larger_characterized_strength'))
            continue
        targets.append(dict(action='resize',capture_cell=name,capture_master=d['master'],replacement_master=choices[0][1]))
    if not targets:raise ValueError('no measured characterized size changes available')
    inputs={str(p):sha(p) for p in (*receipts,graph,chains,violations,*libraries,route/'route.odb',
        Path(__file__).resolve(),Path(__file__).with_name('common_v3.py'))}
    verify(inputs);output.mkdir(parents=True,exist_ok=False)
    save(output/'plan.json',dict(input_sha256=inputs,route_sha256=sha(route/'route.odb'),targets=targets,
        branches=[],short_data_targets=[],protected_first_stage_cells=sorted(protected),
        measured_drivers=len(drivers),unresolved_drivers=unresolved,
        all_first_stage_synchronizer_masters_preserved=True,all_replacements_have_native_early_late_tables=True,
        RTL_and_timing_exceptions_unchanged=True,independent_postroute_minmax_RC_recheck_required=True,
        electrical_closure_claimed=False,release_ready=False))
    print(json.dumps(dict(resizes=len(targets),unresolved=len(unresolved))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('route','electrical','inventory','obligations','views','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ('route','electrical','inventory','obligations','views','output')))
