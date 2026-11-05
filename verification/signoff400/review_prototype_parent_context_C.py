"""Review the complete native context-matched capacitor operator.

No isolated interior is substituted and no exterior endpoint is discarded.
Fixed supplies alone are projected. Diagonal comparisons are geometric
operator checks, not effective terminal-capacitance measurements.
"""
import argparse
from collections import defaultdict
from fractions import Fraction as F
import json
from pathlib import Path
from common_v3 import save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from prototype_capacitance_aliases_v2 import flatten
from bind_prototype_spef_pins_v2 import hierarchy
from project_prototype_fixed_rail_C_v2 import project,RAILS
from check_prototype_capacitance_short_paths_v2 import certify


def diagonal_values(pairs, requested):
    found=set();values={n:F() for n in requested}
    for pair,value in pairs.items():
        for n in pair:
            if n in values:values[n]+=value;found.add(n)
    if found!=set(requested):raise ValueError('requested conductor absent from complete operator')
    return values


def run(extraction,view,layout,reference,output):
    paths=[extraction/'assessment.json',extraction/'native_assessment.json',view/'assessment.json',layout/'assessment.json',reference/'assessment.json',reference/'diagonals.json']
    er,nr,vr,lr,ref=[json.loads(p.read_text()) for p in paths[:5]]
    for r in (er,nr,vr,lr,ref):verify(r['input_sha256']);verify(r['artifacts'])
    if not er.get('completed_native_extraction_verified_in_pinned_image') or not er.get('complete_parent_context_preserved'):
        raise ValueError('completed full-context native extraction required')
    if not vr.get('complete_parent_context_preserved') or not vr.get('selected_fill_purpose_removed_after_conductor_mapping'):
        raise ValueError('context-preserving view without fill/conductor overlays required')
    gds=view/'capacitance_view.gds';manufacturing=layout/'assembly.gds'
    if nr['input_sha256'].get(str(gds))!=sha(gds) or er['input_sha256'].get(str(view/'assessment.json'))!=sha(view/'assessment.json'):
        raise ValueError('native extraction and view identities differ')
    if vr['source_manufacturing_GDS_sha256']!=sha(manufacturing) or lr['artifacts'].get(str(manufacturing))!=sha(manufacturing):
        raise ValueError('manufacturing candidate differs')
    top=vr['top'];source=extraction/top/'capacitance.spice'
    if nr['artifacts'].get(str(source))!=sha(source):raise ValueError('complete native source artifact required')
    deps=('prepare_prototype_analog_reference.py','prototype_capacitance_aliases_v2.py','native_spice_comments.py','bind_prototype_spef_pins_v2.py','project_prototype_fixed_rail_C_v2.py','check_prototype_capacitance_short_paths_v2.py')
    paths.extend((gds,manufacturing,source,Path(__file__).resolve(),*[Path(__file__).with_name(n) for n in deps]))
    pins={str(p):sha(p) for p in paths}
    output.mkdir(parents=True,exist_ok=False)
    save(output/'status.json',dict(state='aggregating_complete_context_operator',release_ready=False))
    text=source.read_text();blocks=subcircuits(text);ports,instances,root_alias=hierarchy(text,top)
    pairs,counts,canonical=flatten(blocks,top)
    def signal(n):
        n=root_alias(n);return canonical(n if n in ports or n=='0' else top+'/'+n)
    fixed=set(RAILS)|{signal(p) for p in ports if p in RAILS}
    fixed.update(signal(n) for i in instances.values() for p,n in i['pins'].items() if p in RAILS)
    comparisons=json.loads((reference/'diagonals.json').read_text())
    # Re-resolve actual exported pins, rather than assuming extraction-generated
    # parent instance names survive a changed capacitance context.
    targets=[i for i in instances.values() if i['model'].startswith('IntegerPLL_DCO_')]
    if len(targets)!=1:raise ValueError('one actual oscillator hierarchy required')
    chosen=targets[0];resolved={}
    for r in comparisons:
        if r['pin'] not in chosen['pins']:raise ValueError('affected conductor missing from native interface')
        resolved[r['pin']]=signal(chosen['pins'][r['pin']])
    values=diagonal_values(pairs,set(resolved.values()))
    rows=[dict(pin=r['pin'],native_parent_node=resolved[r['pin']],
        current_context_diagonal_F=str(values[resolved[r['pin']]]),
        previous_stock_parent_diagonal_F=r['full_parent_stock_diagonal_F'],
        quarantined_mixed_diagonal_F=r['composed_diagonal_F']) for r in comparisons]
    save(output/'affected_diagonals.json',rows)
    dynamic=project(pairs,fixed)
    target=output/'dynamic.pairs.jsonl'
    with target.open('w') as stream:
        for pair,value in sorted(dynamic.items()):stream.write(json.dumps(dict(nodes=list(pair),farads=str(value)))+'\n')
    save(output/'status.json',dict(state='certifying_complete_context_operator',release_ready=False))
    proof=certify(dynamic);save(output/'fixed_rail_passivity.json',proof)
    verify(pins)
    state='passivity_certified' if proof['passivity_certified'] else ('negative_geometric_energy' if proof.get('negative_diagonal_witnesses') else 'sufficient_certificate_inconclusive')
    save(output/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in (target,output/'fixed_rail_passivity.json',output/'affected_diagonals.json')},
        assembled_candidate_gds_sha256={str(manufacturing):sha(manufacturing)},
        native_full_context_operator_independently_aggregated=True,complete_exterior_and_interior_C_retained=True,
        separate_interior_substitution_performed=False,expanded_counts=counts,aggregated_pairs=len(pairs),dynamic_pairs=len(dynamic),
        explicit_fixed_supply_nodes=sorted(fixed),complete_geometric_operator_passivity_certified=proof['passivity_certified'],
        passivity_review_state=state,affected_diagonals_nonnegative=all(values[n]>=0 for n in resolved.values()),
        diagonal_values_are_effective_terminal_capacitances=False,device_intrinsic_C_included=False,
        FOM_fill_electrical_coverage_complete=False,neighborhood_convergence_verified=False,
        loaded_native_model_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state=state,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('extraction','view','layout','reference','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(*[getattr(a,n).resolve() for n in ('extraction','view','layout','reference','output')])
