"""Positive and rejecting controls for a full logical-C passivity certificate."""
import argparse
import copy
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


def run(output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    d=ROOT/'tools/sheet_charge';names=['search_logical_C_weighted_DD','certify_logical_C_weighted_DD']
    paths=[*[d/(name+'.cpp') for name in names],d/'sparse_runs_v2.hpp',d/'zero_C_mask.hpp',ROOT/'tools/charge_compiler/json.hpp',
           Path('/usr/bin/g++').resolve(),Path(__file__).resolve(),Path(__file__).with_name('test_conservative_C.py')]
    pins={str(p):sha(p) for p in paths};binaries={}
    with lease(4,4,deadline):
        for name in names:
            binary=output/name;binaries[name]=binary
            execute(['g++','-std=c++20','-O3','-fopenmp','-fno-fast-math','-ffp-contract=off',d/(name+'.cpp'),
                     '-lgmpxx','-lgmp','-o',binary],output/(name+'.build.log'),deadline,4)
        for label,diagonal,coupling in [('PSD_not_uniform_DD',[10,1,5,0],2),('indefinite',[6,1,1,0],2)]:
            folder=output/label;folder.mkdir();path=folder/'matrix.bin'
            # The full matrix is a signed-edge Laplacian; node 3 is an exact zero row.
            entries=[(0,0,Q(diagonal[0])),(0,1,Q(-diagonal[1]-coupling)),(0,2,Q(-diagonal[2]-coupling)),
                     (1,1,Q(diagonal[1])),(1,2,Q(coupling)),(2,2,Q(diagonal[2]))]
            matrix(path,entries);zero=folder/'zero.bin';zero.write_bytes(b'CZEROR01'+struct.pack('<Q',4)+bytes([0,0,0,1]))
            rows=folder/'rows.jsonl';rows.write_text(''.join(json.dumps(dict(row=i,conservative_diagonal_integer=str(value*2**128)))+'\n' for i,value in enumerate(diagonal)))
            base=dict(matrix=str(path),zero_rows=str(zero),node_count=4,ground_id=0,coefficient_quantum_exponent=-128,
                      diagonal_certificate=str(rows),deadline_uptime=deadline)
            vector=folder/'explicit.vec';vector.write_bytes(b'DDVEC001'+struct.pack('<Q',4)+struct.pack('<4d',0,2.25,1,1))
            cfg,report=folder/'explicit.json',folder/'explicit.report.json';save(cfg,dict(base,vector=str(vector),report=str(report)))
            execute([binaries[names[1]],cfg],folder/'explicit.log',deadline,4);found=json.loads(report.read_text())
            assert found['full_matrix_passivity_verified']==(label=='PSD_not_uniform_DD')
            assert found['exact_implicit_diagonal_identity_verified'] and not found['indefiniteness_proved']
            if label=='PSD_not_uniform_DD':assert found['zero_margin_rows']==1 and not found['grounded_SPD_verified']
            cfg,report,vector=folder/'search.json',folder/'search.report.json',folder/'searched.vec'
            save(cfg,dict(base,threads=4,iterations=256,maximum_adjacency_bytes=1024**3,vector=str(vector),report=str(report)))
            execute([binaries[names[0]],cfg],folder/'search.log',deadline,4)
            checked=folder/'searched.report.json';cfg=folder/'searched.json';save(cfg,dict(base,vector=str(vector),report=str(checked)))
            execute([binaries[names[1]],cfg],folder/'searched.log',deadline,4)
            assert json.loads(checked.read_text())['full_matrix_passivity_verified']==(label=='PSD_not_uniform_DD')
            if label!='PSD_not_uniform_DD':continue
            for fault in ('wrong_diagonal','nonzero_reference','zero_weight','negative_weight','wrong_ground'):
                bad=copy.deepcopy(base);vector=folder/(fault+'.vec');weights=[0,2.25,1,1]
                if fault=='nonzero_reference':weights[0]=1
                if fault=='zero_weight':weights[1]=0
                if fault=='negative_weight':weights[1]=-1
                if fault=='wrong_ground':bad['ground_id']=1
                if fault=='wrong_diagonal':
                    changed=folder/'wrong_rows.jsonl';changed.write_text(rows.read_text().replace(str(2**128),str(2*2**128),1));bad['diagonal_certificate']=str(changed)
                vector.write_bytes(b'DDVEC001'+struct.pack('<Q',4)+struct.pack('<4d',*weights))
                cfg=folder/(fault+'.json');save(cfg,dict(bad,vector=str(vector),report=str(folder/(fault+'.report.json'))))
                p=subprocess.run([str(binaries[names[1]]),str(cfg)],capture_output=True,text=True,timeout=30)
                save(folder/(fault+'.result.json'),dict(returncode=p.returncode,stderr=p.stderr));assert p.returncode!=0,fault
        verify(pins);artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file()}
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
             logical_C_exact_weighted_DD_controls_pass=True,nonuniform_positive_vector_certificate_checked=True,
             exact_zero_rows_supported=True,implicit_diagonal_identity_checked_independently=True,
             bad_diagonal_vector_and_reference_guards_checked=True,failed_sufficient_certificate_not_indefiniteness=True,
             physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    run(p.parse_args().output.resolve())
