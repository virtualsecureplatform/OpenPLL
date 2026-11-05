"""Control native selected-diagonal integration, zero-R aliases, and interval reuse."""
import argparse
import copy
from fractions import Fraction as Q
import json
import os
from pathlib import Path
import struct
import subprocess
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import lease
from test_fringe_interval import atan,endpoint


def run(output,headers):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    os.environ.update(OMP_THREAD_LIMIT='4',OMP_NUM_THREADS='4')
    directory=ROOT/'tools/sheet_charge';sources=[directory/name for name in (
        'enclose_selected_C_diagonals.cpp','main_registered_mpfr_v2.cpp','registered_fringe_interval.hpp',
        'main_registered_mpfr.cpp','main_registered_rational.cpp','fringe_interval.hpp','runtime_geometry_v2.hpp','bounded_jsonl_range.hpp')]
    prior=ROOT/'build/signoff400/registered_mpfr_controls_001';old=json.loads((prior/'assessment.json').read_text())
    paths=[*sources,ROOT/'tools/charge_compiler/json.hpp',headers/'mpfr.h',Path('/lib/x86_64-linux-gnu/libmpfr.so.6').resolve(),
           Path('/usr/bin/g++').resolve(),Path(__file__).resolve(),prior/'assessment.json']
    pins={str(p):sha(p) for p in paths}
    prefix=(directory/'main_registered_mpfr.cpp').read_text().split('int main(int argc',1)[0]
    assert (directory/'registered_fringe_interval.hpp').read_text()=='#pragma once\n'+prefix
    with lease(4,4,deadline):
        binaries={}
        for name in ('enclose_selected_C_diagonals','main_registered_mpfr_v2'):
            binary=output/name;binaries[name]=binary
            execute(['g++','-std=c++20','-O3','-fopenmp','-fno-fast-math','-ffp-contract=off','-I'+str(headers),
                     directory/(name+'.cpp'),'-l:libmpfr.so.6','-lgmpxx','-lgmp','-o',binary],output/(name+'.build.log'),deadline,4)
        for bits in (128,256,512,1024):
            casefile=prior/'cases.json';expected=prior/f'{bits}.rows.jsonl'
            assert sha(casefile)==old['artifacts'][str(casefile)] and sha(expected)==old['artifacts'][str(expected)]
            cfg,rows=output/f'legacy_{bits}.json',output/f'legacy_{bits}.rows.jsonl'
            save(cfg,dict(cases=str(casefile),precision_bits=bits,output=str(rows),deadline_uptime=deadline))
            execute([binaries['main_registered_mpfr_v2'],cfg],output/f'legacy_{bits}.log',deadline,4)
            assert rows.read_bytes()==expected.read_bytes()
        mesh=output/'mesh.jsonl';mesh.write_text(json.dumps(dict(tile_serial=1,box=[0,0,1,1],
             points=[[0,0],[1,0],[1,1],[0,1]],point_nodes=['a','b','c','d'],triangles=[[0,1,2],[0,2,3]]))+'\n')
        index=output/'index.bin';index.write_bytes(b'RBSIDX01'+struct.pack('<Q',2)+struct.pack('<QII',2**64-1,0,0)+struct.pack('<QII',0,1,0))
        bundles=output/'bundles.jsonl';bundles.write_text(json.dumps(dict(bundle_id=0,tile_references=[[0,0,'g',1]]))+'\n')
        aliases=output/'shape_aliases.json';save(aliases,[]);templates=output/'templates.jsonl';templates.write_text('')
        floating=[]
        for i in range(7):f=output/f'floating_{i}.jsonl';f.write_text('');floating.append(str(f))
        geometry=dict(global_fields=2,R_parts=[str(mesh)],expected_R_tiles=1,R_index=str(index),expected_R_fields=1,
            R_bundles=str(bundles),template_aliases=str(aliases),templates=str(templates),floating_parts=floating,
            expected_floating_fields=0,expected_floating_nodes=0,deadline_uptime=deadline)
        mapfile=output/'field_map.json';save(mapfile,[0,1])
        ops=[['A',1,0,1,[0,0,1,1],1],['L',1,0,2,[0,0,1,0],[0,2,1,2],2,2,0],
             ['F',1,0,3,[0,0,0,1],[0,0,1,1],4,.75,.25],['A',1,0,4,[0,0,0,0],1]]
        source=output/'source.jsonl';raw=''.join(json.dumps(op)+'\n' for op in ops);source.write_text(raw)
        selected=output/'selected.jsonl';selected.write_text(raw);offsets=output/'offsets.bin';offset=0
        with offsets.open('wb') as stream:
            for line in raw.splitlines(keepends=True):stream.write(struct.pack('<Q',offset));offset+=len(line.encode())
        task=dict(task=0,field_map=str(mapfile),operators=str(source),begin_byte=0,end_byte=source.stat().st_size,
                  selected_operators=str(selected),selected_offsets=str(offsets),selected_count=len(ops))
        targets=output/'targets.json';normal=dict(energy_binary_quantum_exponent=-64,negative_nodes=[
            dict(row=1,energy_integer='-1',original_voltage_nodes=[dict(node=2,name='b')]),
            dict(row=2,energy_integer='-1',original_voltage_nodes=[dict(node=4,name='d')])]);save(targets,normal)
        base=dict(geometry=geometry,targets=str(targets),expected_voltage_nodes=5,tasks=[task],precision_bits=128,
                  threads=4,deadline_uptime=deadline,expected_selected_operators=len(ops))
        a=atan(Q(1,4),160);factor=Q(.75)*Q(.6366)/3
        references={1:(Q(3,4),Q(3,4)),2:(Q(1,12)+factor*a[0],Q(1,12)+factor*a[1])}
        for label in ('ordinary','aliases'):
            case=copy.deepcopy(base)
            if label=='aliases':
                alternate=output/'alias_targets.json';save(alternate,dict(energy_binary_quantum_exponent=-64,negative_nodes=[
                    dict(row=1,energy_integer='-1',original_voltage_nodes=[dict(node=1,name='a'),dict(node=3,name='c')])]))
                case['targets']=str(alternate);references={1:(Q(7,6)+factor*a[0],Q(7,6)+factor*a[1])}
            cfg,report=output/(label+'.json'),output/(label+'.report.json');save(cfg,dict(case,report=str(report)))
            execute([binaries['enclose_selected_C_diagonals'],cfg],output/(label+'.log'),deadline,4)
            found=json.loads(report.read_text());assert found['target_diagonal_rows']==len(references)
            for row in found['rows']:
                lo,hi=endpoint(row['interval']['lower_dyadic']),endpoint(row['interval']['upper_dyadic']);truth=references[row['row']]
                assert lo<=truth[0]<=truth[1]<=hi,(label,row['row'])
                assert row['sign']=='strictly_positive' and row['stored_coefficient_below_interval']
        for fault in ('wrong_source_bytes','wrong_count','wrong_node_name','wrong_namespace'):
            case=copy.deepcopy(base)
            if fault=='wrong_source_bytes':
                changed=output/'wrong_source.jsonl';changed.write_text(raw.replace(', 1]',', 2]',1));case['tasks'][0]['operators']=str(changed)
            if fault=='wrong_count':case['tasks'][0]['selected_count']+=1
            if fault=='wrong_node_name':
                changed=output/'wrong_targets.json';bad=copy.deepcopy(normal);bad['negative_nodes'][0]['original_voltage_nodes'][0]['name']='bad';save(changed,bad);case['targets']=str(changed)
            if fault=='wrong_namespace':case['expected_voltage_nodes']=6
            cfg=output/(fault+'.json');save(cfg,dict(case,report=str(output/(fault+'.report.json'))))
            p=subprocess.run([str(binaries['enclose_selected_C_diagonals']),str(cfg)],capture_output=True,text=True,timeout=60)
            save(output/(fault+'.result.json'),dict(returncode=p.returncode,stderr=p.stderr));assert p.returncode!=0,fault
        verify(pins);artifacts={str(p):sha(p) for p in output.iterdir() if p.is_file()}
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
             selected_C_diagonal_enclosure_controls_pass=True,exact_area_line_and_independent_fringe_reference_checked=True,
             zero_R_alias_offdiagonal_double_count_checked=True,zero_measure_terms_checked=True,
             MPFR_spatial_predecessor_outputs_byte_identical_at_all_four_precisions=True,
             original_source_bytes_and_namespace_guards_checked=True,physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--headers',required=True,type=Path);a=p.parse_args();run(a.output.resolve(),a.headers.resolve())
