"""Inventory capacitor-only components without losing any active terminal net."""
import argparse
from collections import defaultdict
from fractions import Fraction as F
import json
from pathlib import Path
from common_v3 import save,sha,verify
from project_prototype_fixed_rail_C_v2 import FIXED


def inventory(pairs,retained):
    all_nodes={n for pair in pairs for n in pair};floating=all_nodes-set(retained)
    parent={n:n for n in floating}
    def find(n):
        while parent[n]!=n:parent[n]=parent[parent[n]];n=parent[n]
        return n
    for a,b in pairs:
        if a in floating and b in floating:parent[find(a)]=find(b)
    groups={}
    for n in sorted(floating):
        key=find(n);groups.setdefault(key,dict(nodes=[],boundaries=set(),incident_pairs=0,negative_incident_pairs=0))['nodes'].append(n)
    for (a,b),value in pairs.items():
        involved={find(n) for n in (a,b) if n in floating}
        for key in involved:
            r=groups[key];r['incident_pairs']+=1;r['negative_incident_pairs']+=value<0
            r['boundaries'].update(n for n in (a,b) if n not in floating)
    for r in groups.values():r['boundaries']=sorted(r['boundaries'])
    result=sorted(groups.values(),key=lambda r:(-len(r['nodes']),r['nodes'][0]))
    return result,dict(capacitor_nodes=len(all_nodes),retained_nodes_with_C=len(all_nodes&set(retained)),
        active_terminal_nodes_without_geometric_C=len(set(retained)-all_nodes),capacitor_only_nodes=len(floating),
        capacitor_only_components=len(result),all_primitive_and_named_port_nodes_retained=True)


def run(source,certificate,device_graph,output):
    receipts=[p/'assessment.json' for p in (source,certificate,device_graph)]
    sr,cr,dr=records=[json.loads(p.read_text()) for p in receipts]
    for r in records:verify(r['input_sha256']);verify(r['artifacts'])
    if not cr['complete_context_geometric_operator_passivity_certified'] or not cr['rational_allocation_witnesses_independently_replayed']:
        raise ValueError('independently replayed complete context passivity certificate required')
    if cr['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]):raise ValueError('certificate and source differ')
    if not dr['all_physical_primitive_parameters_and_connections_unchanged'] or not dr['primitive_terminal_conductor_bijection_verified']:
        raise ValueError('complete physical primitive graph identity required')
    native=source/'dynamic.pairs.jsonl';mapping=device_graph/'primitive_conductor_bijection.json'
    # Both reviews must bind the same newly extracted hierarchy.
    candidates={p for p in sr['input_sha256'] if p.endswith('/capacitance.spice')}
    if len(candidates)!=1 or any(dr['input_sha256'].get(p)!=sr['input_sha256'][p] for p in candidates):
        raise ValueError('capacitor and active-device hierarchy identities differ')
    paths=[*receipts,native,mapping,Path(__file__).resolve()]
    pins={str(p):sha(p) for p in paths}
    retained=set(json.loads(mapping.read_text()).values())
    retained.difference_update(sr['explicit_fixed_supply_nodes']);retained.add(FIXED)
    pairs={}
    for line in native.open():
        r=json.loads(line);key=tuple(r['nodes'])
        if key in pairs:raise ValueError('duplicate source pair')
        pairs[key]=F(r['farads'])
    groups,stats=inventory(pairs,retained)
    verify(pins);output.mkdir(parents=True,exist_ok=False)
    file=output/'components.json';save(file,dict(groups=groups,**stats))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(file):sha(file)},**stats,
        largest_components=[dict(nodes=len(r['nodes']),boundaries=len(r['boundaries']),incident_pairs=r['incident_pairs'],negative_incident_pairs=r['negative_incident_pairs']) for r in groups[:10]],
        geometric_operator_unchanged=True,capacitor_only_nodes_grounded=False,
        floating_charge_reduction_performed=False,loaded_native_model_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','certificate','device-graph','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.certificate.resolve(),a.device_graph.resolve(),a.output.resolve())
