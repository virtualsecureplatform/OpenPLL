#!/usr/bin/env python3
"""Collapse extracted R and compare the complete parsed capacitor matrices.

Map split MOS terminals by native instance identity and public/floating nodes
by original names. This is a necessary charge preservation check, not a proof
of distributed geometry or physical timing. Keep nonpasses visible.
"""
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
from audit_parent_capacitance_network import decimal_value
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def parse(path):
    data={'C':[],'R':[],'X':{},'ports':[]}
    for line in path.read_text().splitlines():
        f=line.split()
        if not f:continue
        if f[0].lower()=='.subckt':data['ports']=f[2:]
        elif f[0].startswith('C'):data['C'].append((f[1],f[2],decimal_value(f[3])))
        elif f[0].startswith('R'):data['R'].append((f[1],f[2],decimal_value(f[3])))
        elif f[0].startswith('X'):
            assert f[0] not in data['X'];data['X'][f[0]]=f[1:]
    assert len(data['X'])==4 and data['C']
    return data


def compare(before,after):
    parent={}
    def find(a):
        parent.setdefault(a,a)
        while parent[a]!=a:
            parent[a]=parent[parent[a]];a=parent[a]
        return a
    for a,b,r in after['R']:
        assert r>0
        parent[find(a)]=find(b)
    assert before['X'].keys()==after['X'].keys()
    labels=defaultdict(set)
    def bind(a,original):labels[find(a)].add(original)
    assert before['ports']==after['ports']
    for p in before['ports']:bind(p,p)
    for name,device in before['X'].items():
        distributed=after['X'][name]
        assert device[4:]==distributed[4:],name
        for old,new in zip(device[:4],distributed[:4]):bind(new,old)
    original_nodes={x for a,b,c in before['C'] for x in [a,b]}
    for a,b,c in after['C']:
        for n in [a,b]:
            if n in original_nodes:bind(n,n)
    assert all(len(s)==1 for s in labels.values()),dict(labels)
    def canonical(n):
        values=labels[find(n)];assert len(values)==1,(n,values)
        return next(iter(values))
    def matrix(records,resolve):
        result=defaultdict(Decimal)
        for a,b,c in records:
            a,b=resolve(a),resolve(b)
            if a!=b:result[tuple(sorted([a,b]))]+=c
        return result
    first=matrix(before['C'],lambda n:n)
    second=matrix(after['C'],canonical)
    rows=[]
    # Native values are printed to 0.00001 fF; account for per-term rounding.
    allowance=Decimal('0.000005e-15')*(len(before['C'])+len(after['C']))
    for pair in sorted(first.keys()|second.keys()):
        delta=second[pair]-first[pair]
        rows.append(dict(nodes=list(pair),before_ff=str(first[pair]*Decimal('1e15')),
            after_collapsed_ff=str(second[pair]*Decimal('1e15')),
            delta_ff=str(delta*Decimal('1e15')),within_export_rounding=abs(delta)<=allowance))
    return dict(distributed_resistors=len(after['R']),before_capacitors=len(before['C']),
        after_capacitors=len(after['C']),all_resistors_positive=True,
        transistor_models_parameters_and_collapsed_connections_preserved=True,
        rounding_allowance_ff=str(allowance*Decimal('1e15')),
        complete_capacitor_matrix_preserved_within_rounding=all(r['within_export_rounding'] for r in rows),
        changed_branch_pairs=[r for r in rows if not r['within_export_rounding']],all_branch_pairs=rows)


def main():
    base=ROOT/'build/timing400/release_001'
    source=base/'driven_distributed_rc_coupling_controls_003'
    receipt=verify(source/'assessment.json');assert receipt['two_native_controls_completed']
    out=base/'distributed_rc_coupling_audit_002';out.mkdir(exist_ok=False)
    paths=[Path(__file__).resolve(),Path(__file__).with_name('audit_parent_capacitance_network.py'),source/'assessment.json']
    records={}
    for name in ['floating_tile','ported_tile']:
        case=source/name
        before_path,after_path=case/'lumped.spice',case/'distributed.spice'
        before,after=parse(before_path),parse(after_path)
        log=(case/'extract.log').read_text()
        assert 'Port index' not in log and 'electrically shorted' not in log and 'Exactly one label' not in log
        assert ('AGG' in before['ports'])==(name=='ported_tile')
        result=compare(before,after)
        result['negative_exported_capacitors']=[dict(nodes=[a,b],value_ff=str(c*Decimal('1e15'))) for a,b,c in after['C'] if c<0]
        assert result['distributed_resistors']>0
        # An exact unchanged matrix passes; deleting the actual tile coupling fails.
        same={**before,'R':[]}
        assert compare(before,same)['complete_capacitor_matrix_preserved_within_rounding']
        tile='AGG' if name=='ported_tile' else next(n for a,b,c in before['C'] for n in [a,b] if n.startswith('m1_'))
        damaged={**same,'C':[(a,b,c) for a,b,c in same['C'] if {a,b}!={'X',tile}]}
        assert not compare(before,damaged)['complete_capacitor_matrix_preserved_within_rounding']
        result['negative_missing_tile_coupling_rejected']=True
        records[name]=result
        paths += [before_path,after_path,case/'extract.log',case/'DRIVEN_COUPLING_CONTROL.ext']
    save(out/'comparison.json',records)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(out/'comparison.json'):sha(out/'comparison.json')},
        actual_driver_controls=2,unique_ports_verified=True,transistor_and_positive_R_checks_passed=True,
        exact_matrix_positive_control_passed=True,missing_coupling_negative_control_rejected=True,
        complete_capacitor_matrix_preserved=all(r['complete_capacitor_matrix_preserved_within_rounding'] for r in records.values()),
        changed_branch_pairs={k:len(v['changed_branch_pairs']) for k,v in records.items()},
        default_extresist_C_export_approved_for_full_layout=False,
        full_distributed_rc_qualified=False,physical_timing_qualified=False,release_qualified=False,
        adopted=False,native_analog_jobs_added=0,scope=__doc__))
    print(json.dumps({k:{'R':v['distributed_resistors'],'changed_pairs':len(v['changed_branch_pairs']),
        'matrix_preserved':v['complete_capacitor_matrix_preserved_within_rounding']} for k,v in records.items()}))


if __name__=='__main__':main()
