"""Reuse a completed native boolean proof only for byte-identical netlists.

Routed geometry may differ. Independent physical connectivity and new RC/timing
checks remain required; no native solver is rerun or its exit code inferred.
"""
import argparse
import json
from pathlib import Path
import shutil
from common_v3 import save,sha,verify


def run(source,proof,route,output):
    receipts=[p/'assessment.json' for p in (source,proof,route)]
    old,p,new=[json.loads(f.read_text()) for f in receipts]
    for r in (old,p,new):verify(r['input_sha256']);verify(r['artifacts'])
    required=('all_transition_and_output_functions_equivalent',
              'corrupted_reset_function_rejected',
              'all_projected_pg_only_cells_have_no_signal_connections',
              'passive_load_effects_excluded_from_boolean_proof')
    count=p.get('matched_state_primitives')
    states=sum(v for k,v in new['cell_inventory'].items() if '__dfrtp_' in k or '__dfstp_' in k)
    if (any(p.get(k) is not True for k in required) or type(count) is not int
            or count<=0 or count!=states or not p['artifacts']
            or old['candidate_source_sha256']!=new['candidate_source_sha256']
            or old['cell_inventory']!=new['cell_inventory']
            or any(r.get('digital_routing_completed') is not True or r.get('router_drc_violations')!=0
                   for r in (old,new))
            or p['input_sha256'].get(str(receipts[0]))!=sha(receipts[0])
            or p['input_sha256'].get(str(source/'route.v'))!=sha(source/'route.v')):
        raise ValueError('complete same-candidate source proof and matching state inventory required')
    for name in ('route.v','powered.v'):
        if sha(source/name)!=sha(route/name):
            raise ValueError('native proof reuse requires byte-identical '+name)
    copies=[]
    for name,digest in p['artifacts'].items():
        original=Path(name);relative=original.relative_to(proof)
        if relative==Path('assessment.json'):raise ValueError('recursive proof assessment artifact')
        copies.append((original,relative,digest))
    inputs=dict(p['input_sha256'])
    inputs.update({str(f):sha(f) for f in (*receipts,source/'powered.v',route/'route.v',route/'powered.v',
                   Path(__file__).resolve(),Path(__file__).with_name('common_v3.py'))})
    verify(inputs);output.mkdir(parents=True,exist_ok=False)
    artifacts={}
    for original,relative,digest in copies:
        target=output/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(original,target)
        if sha(target)!=digest:raise ValueError('proof artifact changed during reuse')
        artifacts[str(target)]=digest
    reference=output/'native_proof_reference.json'
    save(reference,dict(source_proof=str(receipts[1]),source_proof_sha256=sha(receipts[1]),
         source_route=str(receipts[0]),new_route=str(receipts[2]),
         functional_netlist_sha256=sha(route/'route.v'),powered_netlist_sha256=sha(route/'powered.v')))
    artifacts[str(reference)]=sha(reference);verify(inputs)
    p.update(input_sha256=inputs,artifacts=artifacts,native_proof_reused_from=str(receipts[1]),
             native_proof_rerun=False,exact_functional_and_powered_netlist_identity_verified=True,
             native_exit_codes_not_inferred_for_reused_reports=True,
             physical_connectivity_and_timing_rechecks_required=True,
             physical_timing_qualified=False,release_qualified=False,release_ready=False,
             scope=__doc__)
    save(output/'assessment.json',p)
    print(json.dumps(dict(native_boolean_proof_reused=True,matched_state_primitives=count)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','proof','route','output'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();run(*(getattr(a,n).resolve() for n in ('source','proof','route','output')))
