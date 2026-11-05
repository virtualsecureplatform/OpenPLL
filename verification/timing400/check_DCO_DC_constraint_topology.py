#!/usr/bin/env python3
"""Audit exact finite-R components and point constraints for slow DC diagnosis."""
from collections import Counter,defaultdict
import json
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest,save


def main():
    base=Path(__file__).resolve().parents[2]/'build/timing400/release_001'
    owner=base/'distributed_RC_model_qualification_001/owner.json'
    deadline=json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    family=base/'DCO_complete_domain_model_primitives_001'
    boundary=base/'DCO_direct_native_planes_and_boundaries_001'
    nodes=json.loads((family/'nodes.json').read_text())
    original={r['private_id']:r['original_conductor'] for r in nodes}
    parent={n:n for n in original}
    def find(n):
        parent.setdefault(n,n)
        while parent[n]!=n:
            parent[n]=parent[parent[n]]
            n=parent[n]
        return n
    def join(a,b):
        a,b=find(a),find(b)
        if a==b:return False
        parent[a]=b
        return True
    branch_count=0
    for line in (family/'branches.jsonl').open():
        row=json.loads(line)
        a,b=row['private_nodes']
        assert original[a]==original[b]==row['original_conductor']
        assert float(row['resistance_ohm'])>0
        join(a,b)
        branch_count+=1
    components=defaultdict(set)
    for n,net in original.items():components[net].add(find(n))
    assert len(components)==2686 and all(len(v)==1 for v in components.values())
    rows=json.loads((boundary/'boundary_connections.json').read_text())
    anchors=Counter()
    for row in rows:anchors[original[row['private_node']]]+=1
    gates,conducting=Counter(),Counter()
    for row in json.loads((family/'device_connections.json').read_text()).values():
        terminals=row['private_terminals']
        assert len(terminals) in [2,4]
        for i,n in enumerate(terminals):
            (gates if len(terminals)==4 and i==1 else conducting)[original[n]]+=1
    no_device_or_port=[n for n in components if not(anchors[n] or gates[n] or conducting[n])]
    gate_only=[n for n in components if gates[n] and not(anchors[n] or conducting[n])]
    # A separate graph contains only ideal constraints, never finite resistors.
    parent.clear()
    cycles=[]
    for row in rows:
        if not join('public:'+row['public_port'],row['private_node']):cycles.append(row['index'])
    assert len(rows)==328 and len({r['private_node'] for r in rows})==328
    assert not cycles and not no_device_or_port and not gate_only
    assert branch_count==166286
    out=base/'DCO_DC_constraint_topology_001'
    out.mkdir(exist_ok=False)
    inputs=[Path(__file__).resolve(),owner,family/'nodes.json',family/'branches.jsonl',
        family/'device_connections.json',boundary/'boundary_connections.json',
        boundary/'point_connections_unqualified.spice']
    save(out/'assessment.json',dict(finite_R_components=2686,finite_R_branches=branch_count,
        each_original_conductor_has_exactly_one_R_component=True,
        unique_private_point_constraints=328,ideal_point_constraint_cycles=cycles,
        pure_R_components_without_device_or_port=no_device_or_port,
        gate_only_components_without_conducting_terminal_or_port=gate_only,
        DC_convergence_or_bias_qualified=False,no_circuit_change=True,
        runtime_model_eligible=False,release_qualified=False,adopted=False,deadline_uptime=deadline,
        input_sha256={str(p.resolve()):digest(p) for p in inputs}))
    print('DC structure:328 unique point constraints,0 ideal cycles,2686 connected R conductors,0 device/port-free or gate-only islands.')


if __name__=='__main__':main()
