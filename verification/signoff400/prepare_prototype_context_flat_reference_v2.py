"""Flatten one native context into an independently reparsed reference model.

Preserves actual supply incidence, every capacitor, primitive geometry and named
port alias. No distributed wire R or domain stimulus is introduced.
"""
import argparse
from collections import Counter
from fractions import Fraction as F
import json
from pathlib import Path
from common_v3 import save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from compare_prototype_physical_primitive_graphs import parsed,expand
from prototype_capacitance_aliases_v2 import flatten
from project_prototype_fixed_rail_C_v2 import project
from rebind_prototype_floating_reduction import capacitor_pairs
from build_prototype_DCO_rc import decimal


def original_node(node,inverse,top):
    if node in inverse:return inverse[node]
    prefix=top+'/'
    if node.startswith(prefix) and node[len(prefix):] in inverse:return inverse[node[len(prefix):]]
    raise ValueError('reparsed node outside the emitted compact namespace: '+node)


def run(extraction,converted,review,certificate,device_graph,floating,output):
    receipts=[p/'assessment.json' for p in (extraction,converted,review,certificate,device_graph,floating)]
    er,cv,sr,cr,dr,fr=records=[json.loads(p.read_text()) for p in receipts]
    for r in records:verify(r['input_sha256']);verify(r['artifacts'])
    if not cv['exact_expanded_conversion_reparse_pass'] or not dr['all_physical_primitive_parameters_and_connections_unchanged']:
        raise ValueError('compatible units and full physical primitive graph proof required')
    if not cr['complete_context_geometric_operator_passivity_certified'] or not cr['rational_allocation_witnesses_independently_replayed']:
        raise ValueError('complete context passivity certificate required')
    if cr['input_sha256'].get(str(receipts[2]))!=sha(receipts[2]):raise ValueError('passivity certificate source differs')
    if fr['input_sha256'].get(str(receipts[2]))!=sha(receipts[2]) or fr['input_sha256'].get(str(receipts[4]))!=sha(receipts[4]):
        raise ValueError('floating classification source differs')
    source=converted/'ng47.spice';top='IntegerPLL_400MHz_PrototypeTop'
    raw=extraction/top/'capacitance.spice';native=extraction/'native_assessment.json';nr=json.loads(native.read_text())
    verify(nr['input_sha256']);verify(nr['artifacts'])
    if cv['input_sha256'].get(str(raw))!=sha(raw) or nr['artifacts'].get(str(raw))!=sha(raw):raise ValueError('converted native hierarchy identity differs')
    source_pairs=review/'dynamic.pairs.jsonl';physical_map=device_graph/'primitive_conductor_bijection.json';components=floating/'components.json'
    deps=('compare_prototype_physical_primitive_graphs.py','prototype_capacitance_aliases_v2.py','prepare_prototype_analog_reference.py','project_prototype_fixed_rail_C_v2.py','rebind_prototype_floating_reduction.py','build_prototype_DCO_rc.py','native_spice_comments.py','audit_hierarchical_capacitance.py')
    paths=[*receipts,native,raw,source,source_pairs,physical_map,components,Path(__file__).resolve(),*[Path(__file__).with_name(n) for n in deps]]
    paths.extend(Path(p) for p in nr['artifacts'] if p.endswith('.ext'))
    pins={str(p):sha(p) for p in paths}
    text=source.read_text();ports,primitives,alias,_,_=expand(parsed(text),top,extraction/top)
    pairs,counts,canonical=flatten(subcircuits(text),top)
    actual={alias.find(n) for _,ns,_ in primitives.values() for n in ns}|{alias.find(p) for p in ports}|{'0'}
    expected=set(json.loads(physical_map.read_text()).values())
    if actual!=expected:raise ValueError('active terminal basis differs from physical graph proof')
    if any(canonical(n)!=n for n in actual):raise ValueError('primitive and capacitor alias resolvers disagree')
    dynamic={}
    for line in source_pairs.open():
        r=json.loads(line);k=tuple(r['nodes'])
        if k in dynamic:raise ValueError('duplicate certified dynamic pair')
        dynamic[k]=F(r['farads'])
    if project(pairs,set(sr['explicit_fixed_supply_nodes']))!=dynamic:raise ValueError('full native fixed-supply projection differs from certified operator')
    all_nodes=set(ports)|actual|{n for pair in pairs for n in pair}
    if any(n.startswith('__context_node_') for n in all_nodes):raise ValueError('reserved compact node namespace collision')
    names={n:n if n in ports or n=='0' else '__context_node_'+str(i) for i,n in enumerate(sorted(all_nodes))}
    inverse={v:k for k,v in names.items()};lines=['* Complete native context reference; no wire R or domain stimuli.','.subckt '+top+' '+' '.join(ports)]
    instances=[]
    for i,(key,(model,ns,params)) in enumerate(primitives.items()):
        terminals=tuple(alias.find(n) for n in ns)
        lines.append('Xflat'+str(i)+' '+' '.join(names[n] for n in terminals)+' '+model+' '+' '.join(k+'='+decimal(F(v)) for k,v in params))
        identity,master,signature,ordinal=key
        instances.append(dict(instance='Xflat'+str(i),physical_hierarchy_identity=identity,leaf_master=master,local_primitive_signature=signature,parallel_ordinal=ordinal))
    aliases=0
    for port in ports:
        target=alias.find(port)
        if target!=port:
            lines.append('RwirePort'+str(aliases)+' '+names[port]+' '+names[target]+' 0');aliases+=1
    lines.extend('Cflat'+str(i)+' '+names[a]+' '+names[b]+' '+decimal(v) for i,((a,b),v) in enumerate(sorted(pairs.items())))
    lines.append('.ends '+top);model_text='\n'.join(lines)+'\n'
    # Reparse the emitted primitive graph and C cards independently, undoing
    # compact names. Alias ports retain their original electrical relation.
    p2,d2,u2,_,_=expand(parsed(model_text),top,extraction/top)
    before=Counter((m,tuple(alias.find(n) for n in ns),ps) for m,ns,ps in primitives.values())
    after=Counter((m,tuple(original_node(u2.find(n),inverse,top) for n in ns),ps) for m,ns,ps in d2.values())
    if before!=after or ports!=p2:raise ValueError('flat primitive graph or interface differs after reparse')
    recovered={tuple(sorted(inverse[n] for n in k)):v for k,v in capacitor_pairs(model_text).items()}
    if recovered!=pairs:raise ValueError('flat complete capacitor operator differs after reparse')
    floating_nodes={n for g in json.loads(components.read_text())['groups'] for n in g['nodes']}
    raw_negative_incident=sum(v<0 and bool(set(k)&floating_nodes) for k,v in pairs.items())
    verify(pins);output.mkdir(parents=True,exist_ok=False)
    model=output/'context.spice';model.write_text(model_text)
    save(output/'nodes.json',dict(original_to_emitted=names,physical_instances=instances,
        capacitor_only_nodes=[names[n] for n in sorted(floating_nodes)],
        original_fixed_supply_nodes=sr['explicit_fixed_supply_nodes']))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in output.iterdir()},
        assembled_candidate_gds_sha256=sr['assembled_candidate_gds_sha256'],top=top,
        complete_native_C_operator_identity_independently_reparsed=True,all_primitive_cards_and_named_ports_independently_reparsed=True,
        complete_fixed_supply_passivity_certificate_bound=True,actual_supply_capacitor_incidence_preserved=True,
        primitive_instances=len(primitives),geometric_pairs=len(pairs),zero_R_port_aliases=aliases,
        capacitor_only_nodes=len(floating_nodes),unprojected_negative_pairs_incident_to_floating_nodes=raw_negative_incident,
        distributed_wire_R_added=False,domain_partition_performed=False,domain_stimuli_supplied=False,
        loaded_native_model_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('extraction','converted','review','certificate','device-graph','floating','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*[getattr(a,n).resolve() for n in ('extraction','converted','review','certificate','device_graph','floating','output')])
