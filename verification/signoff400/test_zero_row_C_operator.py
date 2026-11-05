"""Validate exact coefficient changes and evaluation for source-certified zero rows."""
import argparse
from fractions import Fraction as Q
import json
from pathlib import Path
import struct
import subprocess
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import lease
from test_conservative_C import matrix


def mask(path,values):path.write_bytes(b'CZEROR01'+struct.pack('<Q',len(values))+bytes(values))


def run(output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    d=ROOT/'tools/sheet_charge';names=['certify_conservative_C_v2','evaluate_C_edge_operator_v2']
    paths=[*[d/(name+'.cpp') for name in names],d/'zero_C_mask.hpp',d/'C_edge_operator_v2.hpp',d/'sparse_runs_v2.hpp',
           ROOT/'tools/charge_compiler/json.hpp',Path('/usr/bin/g++').resolve(),Path(__file__).resolve(),Path(__file__).with_name('test_conservative_C.py')]
    pins={str(p):sha(p) for p in paths}
    with lease(8,4,deadline):
        binaries={}
        for name in names:
            binary=output/name;binaries[name]=binary
            execute(['g++','-std=c++20','-O3','-fopenmp','-fno-fast-math','-ffp-contract=off',d/(name+'.cpp'),'-lgmpxx','-lgmp','-o',binary],output/(name+'.build.log'),deadline,4)
        trials=[('identity',[0,0,0],[(0,0,Q(2)),(0,1,Q(-1)),(0,2,Q(-1)),(1,1,Q(1)),(2,2,Q(1))]),
                ('large_change_rejected',[0,1],[(0,0,Q(-1)),(0,1,Q(1)),(1,1,Q(-1))]),
                ('tiny_ghost',[0,1,0],[(0,0,Q(0)),(0,1,Q(2)**-70),(1,1,-Q(2)**-70),(1,2,-Q(2)**-72),(2,2,Q(2)**-72)])]
        results=[]
        for label,zero,entries in trials:
            folder=output/label;folder.mkdir();path=folder/'matrix.bin';matrix(path,entries);z=folder/'zero.bin';mask(z,zero)
            n=len(zero);dense=[[Q(0) for _ in range(n)] for _ in range(n)]
            for i,j,value in entries:dense[i][j]=dense[j][i]=value
            desired=[-sum(dense[i][j] for j in range(n) if i!=j and not zero[i] and not zero[j]) for i in range(n)]
            outside=0
            for i in range(n):
                bound=Q(1e-8)+Q(2e-12)*max(abs(dense[i][i]),abs(desired[i]));outside+=abs(desired[i]-dense[i][i])>bound
            edge_outside=sum(abs(v)>Q(1e-8)+Q(2e-12)*abs(v) for i,j,v in entries if i!=j and (zero[i] or zero[j]))
            cfg,report,rows=folder/'certificate.json',folder/'certificate.report.json',folder/'rows.jsonl'
            save(cfg,dict(matrix=str(path),zero_rows=str(z),node_count=n,deadline_uptime=deadline,row_certificate=str(rows),report=str(report)))
            execute([binaries[names[0]],cfg],folder/'certificate.log',deadline,4);r=json.loads(report.read_text());quantum=Q(2)**r['common_binary_quantum_exponent']
            for i,row in enumerate(map(json.loads,rows.read_text().splitlines())):
                assert int(row['conservative_diagonal_integer'])*quantum==desired[i]
                assert int(row['diagonal_correction_integer'])*quantum==desired[i]-dense[i][i]
                assert row['source_proven_zero_row']==bool(zero[i])
            assert r['rows_outside_coefficient_tolerance']==outside
            assert r['masked_offdiagonal_entries_outside_coefficient_tolerance']==edge_outside
            assert r['all_corrections_within_existing_coefficient_tolerance']==(outside+edge_outside==0)
            assert r['negative_new_conservative_diagonals']==sum(v<0 for v in desired)
            voltage=[Q(i+1,4) for i in range(n)]
            expected=[sum(-dense[i][j]*(voltage[i]-voltage[j]) for j in range(n) if i!=j and not zero[i] and not zero[j]) for i in range(n)]
            cfg,report=folder/'evaluate.json',folder/'evaluate.report.json'
            save(cfg,dict(matrix=str(path),zero_rows=str(z),node_count=n,deadline_uptime=deadline,maximum_adjacency_bytes=1024**3,
                          vector_mode='explicit',voltage=list(map(float,voltage)),threads=[1,4,8],report=str(report)))
            execute([binaries[names[1]],cfg],folder/'evaluate.log',deadline,4);evaluated=json.loads(report.read_text())
            assert evaluated['currents']==list(map(float,expected))
            assert evaluated['all_requested_thread_vectors_bit_identical']
            results.append(dict(case=label,corrections_within_tolerance=r['all_corrections_within_existing_coefficient_tolerance']))
        good=(output/'identity/zero.bin').read_bytes()
        for label,data in [('truncated',good[:-1]),('trailing',good+b'x'),('nonbinary',good[:-1]+b'\2'),('reference',good[:16]+b'\1'+good[17:]),('wrong_namespace',good[:8]+struct.pack('<Q',4)+good[16:])]:
            z=output/(label+'.bin');z.write_bytes(data)
            for name,binary in binaries.items():
                cfg=output/(label+'_'+name+'.json');save(cfg,dict(matrix=str(output/'identity/matrix.bin'),zero_rows=str(z),node_count=3,
                    deadline_uptime=deadline,row_certificate=str(output/'invalid.rows'),report=str(output/'invalid.report'),maximum_adjacency_bytes=1024**3,vector_mode='explicit',voltage=[0,0,0],threads=[1]))
                p=subprocess.run([str(binary),str(cfg)],capture_output=True,text=True,timeout=30)
                save(output/(label+'_'+name+'.result.json'),dict(returncode=p.returncode,stderr=p.stderr));assert p.returncode!=0,(label,name)
        verify(pins);artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file()}
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
             source_zero_row_C_operator_controls_pass=True,exact_fraction_coefficient_changes_and_currents_checked=True,
             large_uncertified_coefficient_changes_rejected=True,mask_namespace_and_reference_guards_checked=True,
             threads_checked=[1,4,8],physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    run(p.parse_args().output.resolve())
