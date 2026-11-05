"""Trace CDC source cones directly from the independently proved routed logic projection."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from inventory_mapped_CDC import inventory
from compare_mapped_routed_CDC import normalized


def run(route,proof,mapped,output):
    rr,pr,mr=[p/'assessment.json' for p in (route,proof,mapped)]
    r,p,m=[json.loads(f.read_text()) for f in (rr,pr,mr)]
    # The proof pins native tools inside its image; verify all local artifacts here.
    for a in (r,p,m):verify(a['artifacts'])
    source=proof/'proof/physical.json';mi=mapped/'inventory.json'
    if not p['all_transition_and_output_functions_equivalent'] or p['input_sha256'].get(str(route/'route.v'))!=sha(route/'route.v'):raise ValueError('matching routed logic proof required')
    if p['artifacts'].get(str(source))!=sha(source):raise ValueError('proved physical projection changed')
    gold=next(Path(f) for f in m['input_sha256'] if f.endswith('/mapped.json'))
    design=json.loads(source.read_text());module=design['modules']['IntegerPLL_ProgrammedCore'];result=inventory(module)
    expected=sum(v for k,v in r['cell_inventory'].items() if '__dfrtp_' in k or '__dfstp_' in k)
    if result['sequential_cells']!=expected:raise ValueError('every routed state element must be traced')
    original=json.loads(gold.read_text())['modules']['IntegerPLL_ProgrammedCore'];old=json.loads(mi.read_text())
    before,bc=normalized(original,old);after,ac=normalized(module,result)
    if before!=after:raise ValueError('state sources or clock roots changed during physical implementation')
    output.mkdir(parents=True,exist_ok=False);report=output/'inventory.json';converted=output/'routed.json'
    save(report,result);converted.write_bytes(source.read_bytes())
    detail=output/'comparison.json';save(detail,dict(mapped_crossings=bc,routed_crossings=ac))
    pins={str(f):sha(f) for f in (rr,pr,mr,source,mi,gold,Path(__file__).resolve(),Path(__file__).with_name('inventory_mapped_CDC.py'),Path(__file__).with_name('compare_mapped_routed_CDC.py'))};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(f):sha(f) for f in (report,converted,detail)},
        sequential_cells=expected,all_routed_sequential_data_and_control_cones_traced=True,
        state_source_cones_and_clock_roots_match=True,clock_inversion_parity_retained=True,
        mapped_normalized_crossing_candidates=len(bc),routed_normalized_crossing_candidates=len(ac),
        physical_only_cell_projection_bound_by_equivalence_proof=True,
        complete_structural_inventory_qualified=False,physical_CDC_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('route','proof','mapped','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();run(a.route.resolve(),a.proof.resolve(),a.mapped.resolve(),a.output.resolve())
