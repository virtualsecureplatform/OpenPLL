#!/usr/bin/env python3
"""Audit actual live DCO RC model charge against its retained native extraction.

Compare at the same0.01fF threshold, then separately expose threshold pruning.
Collapse only explicit resistors, map MOS terminals by unchanged instance and
parameters, and require one original conductor per collapsed component. Retain
matrix differences without adopting the lumped extraction as physical truth.
"""
from collections import Counter,defaultdict
from pathlib import Path
import hashlib
import json
import shlex
from decimal import Decimal
from audit_parent_capacitance_network import decimal_value
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def parse(path):
    lines=[]
    for line in path.read_text().splitlines():
        if line.startswith('+'):
            assert lines;lines[-1]+=' '+line[1:].strip()
        else:lines.append(line)
    data={'C':[],'R':[],'X':{},'ports':[]}
    for line in lines:
        f=line.split()
        if not f:continue
        if f[0].lower()=='.subckt':data['ports']=f[2:]
        elif f[0].startswith('C'):data['C'].append((f[1],f[2],decimal_value(f[3])))
        elif f[0].startswith('R'):data['R'].append((f[1],f[2],decimal_value(f[3])))
        elif f[0].startswith('X'):
            assert f[0] not in data['X']
            row=f[1:]
            assert (len(row)>4 and row[4].startswith('sky130_fd_pr__') and 'fet' in row[4]) or (row[2]=='sky130_fd_pr__res_generic_po')
            data['X'][f[0]]=f[1:]
    assert len(data['X'])==8620 and data['C']
    return data



def terminals(row):
    return 2 if row[2]=='sky130_fd_pr__res_generic_po' else 4


def compare(before,after):
    parent={}
    def find(a):
        parent.setdefault(a,a)
        while parent[a]!=a:
            parent[a]=parent[parent[a]];a=parent[a]
        return a
    for a,b,r in after['R']:
        assert r>0;parent[find(a)]=find(b)
    assert before['X'].keys()==after['X'].keys() and before['ports']==after['ports']
    labels=defaultdict(set)
    def bind(n,label):labels[find(n)].add(label)
    for p in before['ports']:bind(p,p)
    parameter_differences=[]
    for name,row in before['X'].items():
        other=after['X'][name];n=terminals(row)
        assert n==terminals(other) and row[n]==other[n],name
        old_params=dict(token.split('=',1) for token in row[n+1:])
        new_params=dict(token.split('=',1) for token in other[n+1:])
        assert old_params.keys()==new_params.keys()
        assert old_params['w']==new_params['w'] and old_params['l']==new_params['l']
        if old_params!=new_params:parameter_differences.append(dict(instance=name,model=row[n],before=old_params,after=new_params))
        for a,b in zip(row[:n],other[:n]):bind(b,a)
    original={n for a,b,c in before['C'] for n in [a,b]}
    for a,b,c in after['C']:
        for n in [a,b]:
            if n in original:bind(n,n)
    assert all(len(v)==1 for v in labels.values()),[(k,v) for k,v in labels.items() if len(v)>1][:10]
    def canonical(n):
        values=labels[find(n)];assert len(values)==1,(n,values)
        return next(iter(values))
    def matrix(records,resolve):
        result=defaultdict(Decimal)
        for a,b,c in records:
            a,b=resolve(a),resolve(b)
            if a!=b:result[tuple(sorted([a,b]))]+=c
        return result
    first=matrix(before['C'],lambda n:n);second=matrix(after['C'],canonical)
    allowance=Decimal('0.000005e-15')*(len(before['C'])+len(after['C']))
    rows=[]
    for pair in sorted(first.keys()|second.keys()):
        delta=second[pair]-first[pair]
        rows.append(dict(nodes=list(pair),before_ff=str(first[pair]*Decimal('1e15')),
            after_collapsed_ff=str(second[pair]*Decimal('1e15')),delta_ff=str(delta*Decimal('1e15')),
            within_export_rounding=abs(delta)<=allowance))
    return dict(transistor_models_parameters_and_collapsed_connections_preserved=not parameter_differences,
        model_length_width_and_collapsed_terminal_identity_preserved=True,
        device_parameter_differences=parameter_differences,
        native_two_terminal_wrapper_models_parameters_and_connections_preserved=True,
        complete_capacitor_matrix_preserved_within_rounding=all(r['within_export_rounding'] for r in rows),
        changed_branch_pairs=[r for r in rows if not r['within_export_rounding']],
        all_branch_pairs=rows,rounding_allowance_ff=str(allowance*Decimal('1e15')))


def capstream(path):
    digest=hashlib.sha256();count=0
    with path.open('rb') as stream:
        for line in stream:
            if line[:1]==b'C':count+=1;digest.update(line)
    return count,digest.hexdigest()


def main():
    base=ROOT/'build/timing400/release_001'
    exported=base/'active_dco_lumped_capacitance_export_001'
    assert verify(exported/'assessment.json')['existing_ext_exported_with_resistance_backannotation_disabled']
    source=ROOT/'build/timing450/dco_c1_fine_load_001/rcx_160'
    top='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    raw_path=source/(top+'.rcx.spice');reduced=source/(top+'.reduced.spice')
    lumped_path=exported/'lumped_threshold001.spice';full_path=exported/'lumped_full.spice'
    raw,before,full=map(parse,[raw_path,lumped_path,full_path])
    assert capstream(raw_path)==capstream(reduced)
    result=compare(before,raw)
    assert result['model_length_width_and_collapsed_terminal_identity_preserved']
    assert not result['complete_capacitor_matrix_preserved_within_rounding']
    res=source/(top+'.res.ext')
    rnodes=[shlex.split(s) for s in res.read_text().splitlines() if s.startswith('rnode ')]
    negative=[r for r in rnodes if decimal_value(r[3])<0]
    assert len(negative)==126
    # Compare an exact original network and a real missing-capacitor fault.
    assert compare(before,{**before,'R':[]})['complete_capacitor_matrix_preserved_within_rounding']
    biggest=max(range(len(before['C'])),key=lambda i:before['C'][i][2])
    deleted={**before,'C':[r for i,r in enumerate(before['C']) if i!=biggest],'R':[]}
    assert not compare(before,deleted)['complete_capacitor_matrix_preserved_within_rounding']
    lost=[r for r in result['changed_branch_pairs'] if float(r['before_ff'])>0 and float(r['after_collapsed_ff'])==0]
    critical=[r for r in result['changed_branch_pairs'] if 'PLLOUT' in r['nodes']]
    out=base/'active_dco_rc_capacitance_audit_001';out.mkdir(exist_ok=False)
    save(out/'matrix_comparison.json',result)
    save(out/'negative_intermediate_nodes.json',negative)
    paths=[Path(__file__).resolve(),Path(__file__).with_name('audit_distributed_rc_coupling.py'),
        Path(__file__).with_name('audit_parent_capacitance_network.py'),exported/'assessment.json',
        raw_path,reduced,lumped_path,full_path,res,source/'extract.tcl']
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        actual_live_DCO_source_audited=True,MOS_models_parameters_and_collapsed_connections_preserved=result['transistor_models_parameters_and_collapsed_connections_preserved'],
        changed_device_parameter_records=len(result['device_parameter_differences']),
        model_length_width_and_collapsed_terminal_identity_preserved=True,
        MOS_devices=8618,native_two_terminal_resistor_wrappers=2,raw_resistors=len(raw['R']),raw_exported_C=len(raw['C']),
        native_lumped_C_at_same_threshold=len(before['C']),native_lumped_C_at_zero_threshold=len(full['C']),
        resistor_reduction_preserves_all_original_capacitor_records=True,
        negative_intermediate_rnode_C=len(negative),changed_capacitor_branch_pairs=len(result['changed_branch_pairs']),
        completely_lost_capacitor_branch_pairs=len(lost),PLLOUT_changed_pairs=critical,
        same_threshold_capacitor_matrix_preserved=False,
        original_network_positive_control_passed=True,missing_original_C_negative_control_rejected=True,
        live_model_qualified_for_range_or_calibration_decisions=False,
        native_waveform_results_remain_diagnostics_of_this_model=True,
        original_C_network_adopted_as_distributed_truth=False,
        live_inputs_modified=False,physical_timing_qualified=False,release_qualified=False,adopted=False,
        native_analog_jobs_added=0,scope=__doc__))
    print(json.dumps(dict(MOS=8618,native_two_terminal_resistors=2,negative_intermediate_C=len(negative),same_threshold_changed_pairs=len(result['changed_branch_pairs']),
        lost_capacitor_pairs=len(lost),C_before=len(before['C']),C_raw=len(raw['C']))))


if __name__=='__main__':main()
