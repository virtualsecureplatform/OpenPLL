"""Exact symbolic row cancellation controls, including a one-ULP noncancellation."""
import argparse
import copy
from fractions import Fraction as Q
import json
import math
import os
from pathlib import Path
import struct
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import lease


def run(output,headers):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    os.environ.update(OMP_NUM_THREADS='4',OMP_THREAD_LIMIT='4')
    d=ROOT/'tools/sheet_charge';source=d/'prove_selected_C_zero_rows.cpp'
    paths=[source,*[d/name for name in ('symbolic_fringe.hpp','registered_fringe_interval.hpp','main_registered_rational.cpp',
           'fringe_interval.hpp','runtime_geometry_v2.hpp','bounded_jsonl_range.hpp','conductor_map.hpp')],
           ROOT/'tools/charge_compiler/json.hpp',headers/'mpfr.h',Path('/lib/x86_64-linux-gnu/libmpfr.so.6').resolve(),
           Path('/usr/bin/g++').resolve(),Path(__file__).resolve()]
    prior=ROOT/'build/signoff400/selected_C_diagonal_controls_002';assessment=prior/'assessment.json'
    old=json.loads(assessment.read_text());assert old['selected_C_diagonal_enclosure_controls_pass']
    paths.append(assessment);pins={str(p):sha(p) for p in paths};binary=output/'prove_selected_C_zero_rows'
    with lease(4,4,deadline):
        execute(['g++','-std=c++20','-O3','-fopenmp','-fno-fast-math','-ffp-contract=off','-I'+str(headers),
                 source,'-l:libmpfr.so.6','-lgmpxx','-lgmp','-o',binary],output/'build.log',deadline,4)
        base=json.loads((prior/'ordinary.json').read_text());base['deadline_uptime']=deadline;base['geometry']['deadline_uptime']=deadline
        base['geometry']=copy.deepcopy(base['geometry']);base['threads']=4
        verify({p:h for p,h in old['artifacts'].items() if p in [base['geometry'][k] for k in ('R_index','R_bundles','template_aliases','templates')]+base['geometry']['R_parts']+base['geometry']['floating_parts']})
        source_ops=[json.loads(s) for s in (prior/'source.jsonl').read_text().splitlines()]
        target=output/'targets.json';save(target,dict(energy_binary_quantum_exponent=-64,negative_nodes=[
             dict(row=2,energy_integer='-1',original_voltage_nodes=[dict(node=2,name='b')]),
             dict(row=4,energy_integer='-1',original_voltage_nodes=[dict(node=4,name='d')])]))
        def reverse(op):
            changed=copy.deepcopy(op);i=5 if op[0]=='A' else 6 if op[0]=='L' else 7;changed[i]=-op[i];return changed
        results=[]
        for label in ('nonzero','cancelled','split_fringe','one_ulp','aliases'):
            folder=output/label;folder.mkdir();case=copy.deepcopy(base);case['targets']=str(target)
            ops=copy.deepcopy(source_ops)
            if label in ('cancelled','one_ulp'):ops += [reverse(op) for op in source_ops]
            if label=='one_ulp':ops[-2][7]=math.nextafter(ops[-2][7],-math.inf)
            if label=='split_fringe':
                first=copy.deepcopy(source_ops[2]);first[5]=[0,0,2,1]
                low=reverse(source_ops[2]);high=reverse(source_ops[2]);high[5]=[1,0,2,1]
                ops=[first,low,high]
            if label=='aliases':
                other=folder/'targets.json';save(other,dict(energy_binary_quantum_exponent=-64,negative_nodes=[
                    dict(row=1,energy_integer='-1',original_voltage_nodes=[dict(node=1,name='a'),dict(node=3,name='c')])]))
                case['targets']=str(other);mapping=[0,1,2,1,3];nodes=4
            else:mapping=list(range(5));nodes=5
            compact=folder/'voltage_map.bin';compact.write_bytes(b'CNETDOF1'+struct.pack('<QQ',5,nodes)+struct.pack('<5I',*mapping));case['voltage_map']=str(compact)
            raw=''.join(json.dumps(op)+'\n' for op in ops);records=folder/'source.jsonl';records.write_text(raw)
            offsets=folder/'offsets.bin';offset=0
            with offsets.open('wb') as stream:
                for line in raw.splitlines(keepends=True):stream.write(struct.pack('<Q',offset));offset+=len(line.encode())
            task=dict(base['tasks'][0],operators=str(records),selected_operators=str(records),selected_offsets=str(offsets),
                      begin_byte=0,end_byte=records.stat().st_size,selected_count=len(ops))
            cfg,report=folder/'config.json',folder/'report.json';save(cfg,dict(case,tasks=[task],expected_selected_operators=len(ops),report=str(report)))
            execute([binary,cfg],folder/'run.log',deadline,4);found=json.loads(report.read_text())
            assert found['all_target_rows_exactly_zero']==(label in ('cancelled','split_fringe')),label
            if label in ('nonzero','aliases'):
                diagonal={r['row']:r['expression'] for r in found['nonzero_expressions'] if r['row']==r['column']}
                if label=='nonzero':
                    assert diagonal[2]==dict(rational='3/4',atoms=[])
                    assert Q(diagonal[4]['rational'])==Q(1,12)
                else:assert Q(diagonal[1]['rational'])==Q(7,6)
                key=4 if label=='nonzero' else 1
                assert diagonal[key]['atoms']==[['atan','1/4',str(Q(.75)*Q(.6366)/3)]]
                sums={}
                for row in found['nonzero_expressions']:
                    terms=sums.setdefault(row['row'],{});e=row['expression'];terms['rational']=terms.get('rational',Q(0))+Q(e['rational'])
                    for kind,arg,coefficient in e['atoms']:
                        token=(kind,arg);terms[token]=terms.get(token,Q(0))+Q(coefficient)
                assert all(all(v==0 for v in terms.values()) for terms in sums.values())
            results.append(dict(case=label,all_rows_exact_zero=found['all_target_rows_exactly_zero'],nonzero_coefficients=found['nonzero_symbolic_coefficients']))
        verify(pins);artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file()}
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
             exact_symbolic_C_zero_row_controls_pass=True,exact_A_L_F_cancellation_checked=True,
             split_interval_telescoping_checked=True,one_ulp_nonzero_coefficient_not_discarded=True,
             complete_row_gauge_and_zero_R_aliases_checked=True,physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--headers',required=True,type=Path);a=p.parse_args();run(a.output.resolve(),a.headers.resolve())
