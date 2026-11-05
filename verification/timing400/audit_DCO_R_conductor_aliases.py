#!/usr/bin/env python3
"""Bind retained R voltage nodes to native pre-R conductors through actual terminals.

Collapse explicit wire R only for conductor identity, retaining every voltage
node separately. Compare this canonical identity against provenance group names
and count coordinates for each conductor. No cap assignment or R interpolation.
"""
from collections import defaultdict,Counter
from pathlib import Path
import json,time,signal,math
from audit_active_dco_rc_capacitance import parse,terminals
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001'
    owner=base/'distributed_RC_model_qualification_001/owner.json';deadline=json.loads(owner.read_text())['deadline_uptime']
    left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME);assert left>0;signal.alarm(max(1,math.floor(left)))
    old_path=base/'active_dco_lumped_capacitance_export_001/lumped_full.spice'
    top='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    source=base/'DCO_R_node_trace_controls_002/trace';raw_path=source/(top+'.rcx.spice')
    before,after=parse(old_path),parse(raw_path);parent={}
    def find(n):
        parent.setdefault(n,n)
        while parent[n]!=n:parent[n]=parent[parent[n]];n=parent[n]
        return n
    for a,b,r in after['R']:assert r>0;parent[find(a)]=find(b)
    labels=defaultdict(set)
    for p in before['ports']:labels[find(p)].add(p)
    for name,row in before['X'].items():
        other=after['X'][name];n=terminals(row)
        assert n==terminals(other) and row[n]==other[n]
        assert dict(x.split('=',1) for x in row[n+1:])['w']==dict(x.split('=',1) for x in other[n+1:])['w']
        assert dict(x.split('=',1) for x in row[n+1:])['l']==dict(x.split('=',1) for x in other[n+1:])['l']
        for a,b in zip(row[:n],other[:n]):labels[find(b)].add(a)
    assert all(len(v)==1 for v in labels.values()),[(k,v) for k,v in labels.items() if len(v)!=1][:5]
    active=set(after['ports'])|{n for a,b,r in after['R'] for n in [a,b]}
    for row in after['X'].values():active.update(row[:terminals(row)])
    unbound=[n for n in active if len(labels[find(n)])!=1];assert not unbound,unbound[:5]
    canonical={n:next(iter(labels[find(n)])) for n in active}
    metadata=base/'DCO_R_node_provenance_inspection_002/node_metadata.json'
    rows=json.loads(metadata.read_text());mismatches=[];by_net=defaultdict(set);coords=defaultdict(set);groups=defaultdict(set)
    for row in rows:
        name=row['name']
        if name not in canonical:continue
        label=canonical[name];by_net[label].add(name);coords[label].add(tuple(row['point_internal']));groups[label].add(row['original_conductor'])
        if label!=row['original_conductor']:mismatches.append(dict(node=name,printed_group=row['original_conductor'],canonical=label,point_internal=row['point_internal']))
    target='COARSETHERMAL_CODE[23]';component_nodes=by_net[target]
    target_X=[]
    for name,row in after['X'].items():
        n=terminals(row)
        for i,node in enumerate(row[:n]):
            if canonical[node]==target:target_X.append(dict(instance=name,terminal=i,node=node,model=row[n]))
    out=base/'DCO_R_conductor_alias_audit_001';out.mkdir(exist_ok=False)
    save(out/'node_conductors.json',canonical);save(out/'group_differences.json',mismatches)
    save(out/'conductor_summary.json',{k:dict(retained_nodes=len(by_net[k]),coordinate_count=len(coords[k]),printed_groups=sorted(groups[k])) for k in sorted(by_net)})
    save(out/'coarse23.json',dict(nodes=sorted(component_nodes),coordinates=sorted(map(list,coords[target])),X_terminals=target_X,
        wire_R=[(a,b,str(r)) for a,b,r in after['R'] if a in component_nodes or b in component_nodes]))
    paths=[Path(__file__).resolve(),Path(__file__).with_name('audit_active_dco_rc_capacitance.py'),owner,old_path,raw_path,metadata]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={str(p):sha(p) for p in out.iterdir()},
        retained_R_MOS_and_port_nodes=len(active),original_conductors=len(by_net),
        ambiguous_or_missing_conductor_bindings=0,provenance_group_name_difference_records=len(mismatches),
        conductor_identity_only_R_voltage_nodes_not_merged=True,physical_C_placement_or_transient_error_qualified=False,release_qualified=False,adopted=False))
    print('Retained R conductor aliases:',len(mismatches),'group-name differences;',target,len(component_nodes),'nodes,',len(coords[target]),'coordinates,',len(target_X),'device terminals.')


if __name__=='__main__':main()
