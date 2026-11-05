"""Compose complete stock exterior C with a bounded mapped-fill DCO operator.

Retains every exterior capacitor and remote dynamic endpoint. The output is a
fixed-supply capacitor operator, not a transistor deck or a qualified load model.
"""
import argparse
from collections import defaultdict
from fractions import Fraction as F
import json
from pathlib import Path
from common_v3 import save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from prepare_prototype_BBPD_receiver_v3 import header
from prototype_capacitance_aliases_v2 import flatten
from bind_prototype_spef_pins_v2 import hierarchy
from rebind_prototype_floating_reduction import capacitor_pairs
from project_prototype_fixed_rail_C_v2 import project,RAILS,FIXED
from check_prototype_capacitance_short_paths_v2 import certify


def compose(exterior,interior,boundary,fixed):
    if set(boundary)&set(fixed):raise ValueError('signal boundary overlaps fixed supplies')
    result=defaultdict(F)
    def point(n):
        if n in fixed:return FIXED
        return boundary.get(n,'__exterior/'+n)
    for pair,value in exterior.items():
        a,b=map(point,pair)
        if a!=b:result[tuple(sorted((a,b)))]+=value
    for pair,value in project(interior,set(RAILS)).items():
        if any(n.startswith('__exterior/') for n in pair):raise ValueError('reserved exterior namespace collision')
        result[pair]+=value
    return {p:v for p,v in result.items() if v}


def run(converted,boundary,bindings,reduced,output):
    receipts=[p/'assessment.json' for p in (converted,boundary,bindings,reduced)]
    cr,br,bind,rr=records=[json.loads(p.read_text()) for p in receipts]
    for r in records:verify(r['input_sha256']);verify(r['artifacts'])
    if br['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]):raise ValueError('boundary and converted hierarchy differ')
    if any(bind['input_sha256'].get(str(p))!=sha(p) for p in (receipts[1],receipts[3])):
        raise ValueError('completed boundary binding must match both models')
    if not bind['all_signal_capacitor_boundaries_bound'] or not br.get('canonical_supply_aliases_excluded_from_signal_boundary'):
        raise ValueError('complete signal-only capacitor boundary binding required')
    if not rr['bounded_floating_C_terminal_reduction_verified'] or not cr['exact_expanded_conversion_reparse_pass']:
        raise ValueError('bounded interior and compatible source hierarchy required')
    source=converted/'ng47.spice';bf=boundary/'boundary.json';binding=bindings/'bindings.json'
    model=reduced/(rr['attachment']+'.spice')
    deps=('prototype_capacitance_aliases_v2.py','bind_prototype_spef_pins_v2.py','rebind_prototype_floating_reduction.py','project_prototype_fixed_rail_C_v2.py','check_prototype_capacitance_short_paths_v2.py','prepare_prototype_analog_reference.py','prepare_prototype_BBPD_receiver_v3.py','native_spice_comments.py')
    pins={str(p):sha(p) for p in [*receipts,source,bf,binding,model,Path(__file__).resolve(),*[Path(__file__).with_name(n) for n in deps]]}
    data=json.loads(bf.read_text());bound=json.loads(binding.read_text())
    text=source.read_text();blocks=subcircuits(text);top=data['top'];target=data['target']
    ports,instances,root_alias=hierarchy(text,top)
    if sum(i['model']==target for i in instances.values())!=1:raise ValueError('one actual oscillator required')
    blocks[target]='.subckt '+target+' '+' '.join(header(blocks[target]))+'\n.ends '+target+'\n'
    print('FLATTENING_COMPLETE_EXTERIOR',flush=True)
    exterior,counts,canonical=flatten(blocks,top)
    def signal(n):
        n=root_alias(n);return canonical(n if n in ports or n=='0' else top+'/'+n)
    fixed=set(RAILS)|{signal(p) for p in ports if p in RAILS}
    fixed.update(signal(n) for i in instances.values() for p,n in i['pins'].items() if p in RAILS)
    mapping=bound['exterior_conductor_to_capacitor_attachment']
    if not set(mapping).issubset({n for pair in exterior for n in pair}):
        # Signal pins may have only active-device loading and no geometric C.
        # They remain bound, but require no capacitor stamp.
        absent=sorted(set(mapping)-{n for pair in exterior for n in pair})
    else:absent=[]
    interior=capacitor_pairs(model.read_text())
    result=compose(exterior,interior,mapping,fixed)
    output.mkdir(parents=True,exist_ok=False)
    pairs=output/'dynamic.pairs.jsonl'
    with pairs.open('w') as stream:
        for pair,value in sorted(result.items()):stream.write(json.dumps(dict(nodes=list(pair),farads=str(value)))+'\n')
    print('CERTIFYING_COMBINED_OPERATOR',len(result),flush=True)
    proof=certify(result);save(output/'fixed_rail_passivity.json',proof)
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in output.iterdir()},
        attachment=rr['attachment'],candidate_gds_sha256=rr['candidate_gds_sha256'],
        assembled_candidate_gds_sha256=rr['assembled_candidate_gds_sha256'],
        complete_exterior_capacitor_operator_retained=True,exterior_counts=counts,
        exterior_pairs=len(exterior),combined_dynamic_pairs=len(result),
        fixed_supply_parent_nodes=sorted(fixed),signal_pins_without_exterior_geometric_C=absent,
        combined_fixed_supply_passivity_certified=proof['passivity_certified'],
        remote_dynamic_endpoints_grounded=False,interior_reduction_absolute_error_certificate_unchanged=True,
        combined_relative_error_bound_claimed=False,exterior_device_models_included=False,
        FOM_fill_electrical_coverage_complete=False,parent_loading_complete=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('converted','boundary','bindings','reduced','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*[getattr(a,n).resolve() for n in ('converted','boundary','bindings','reduced','output')])
