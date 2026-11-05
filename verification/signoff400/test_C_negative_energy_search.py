"""Search controls with independently checked exact energies, including a higher-order witness."""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import shutil
import struct
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import lease
from test_conservative_C import matrix


def run(energy_controls,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    receipt=energy_controls/'assessment.json';a=json.loads(receipt.read_text());energy=energy_controls/'certify_C_vector_energy'
    if a.get('exact_signed_C_vector_energy_controls_pass') is not True or sha(energy)!=a['artifacts'][str(energy)]:raise ValueError('controlled exact energy verifier required')
    verify(a['input_sha256']);source=ROOT/'tools/sheet_charge/search_C_negative_energy.cpp';compiler=Path(shutil.which('g++')).resolve()
    paths=[receipt,energy,source,*[source.with_name(n) for n in ('C_edge_operator_v2.hpp','sparse_runs_v2.hpp','zero_C_mask.hpp')],
           ROOT/'tools/charge_compiler/json.hpp',compiler,Path(__file__).resolve(),Path(__file__).with_name('test_conservative_C.py'),
           *[(Path('/lib/x86_64-linux-gnu')/('lib'+n+'.so')).resolve() for n in ('lapack','blas')]]
    pins={str(p):sha(p) for p in paths};binary=output/'search_C_negative_energy';n=4
    with lease(2,4,deadline):
        execute([compiler,'-std=c++20','-O3','-fopenmp','-fno-fast-math','-ffp-contract=off',source,'-llapack','-lblas','-o',binary],output/'build.log',deadline,4)
        cases=[('PSD_signed',[(0,1,F(-3)),(0,2,F(-7)),(1,2,F(2))],False),
               ('negative_higher_order',[(0,1,F(-5,2)),(0,2,F(-1)),(0,3,F(-1)),
                  (1,2,F(3,4)),(1,3,F(3,4)),(2,3,F(-3,4))],True)]
        for label,edges,wanted in cases:
            p=output/label;p.mkdir();path=p/'C.bin';matrix(path,sorted(edges))
            diagonal=[-sum(v for i,j,v in edges if k in (i,j)) for k in range(n)]
            rows=p/'rows.jsonl';rows.write_text(''.join(json.dumps(dict(row=i,conservative_diagonal_integer=str(int(d*2**166))))+'\n' for i,d in enumerate(diagonal)))
            zero=p/'zero.bin';zero.write_bytes(b'CZEROR01'+struct.pack('<Q',n)+bytes(n))
            vector=p/'vector.bin';cfg,report=p/'search.json',p/'search.report.json'
            base=dict(matrix=str(path),zero_rows=str(zero),node_count=n,coefficient_quantum_exponent=-166,deadline_uptime=deadline)
            save(cfg,dict(base,diagonal_certificate=str(rows),threads=2,iterations=16,maximum_adjacency_bytes=1024**3,
                vector=str(vector),progress=str(p/'progress.json'),report=str(report)))
            execute([binary,cfg],p/'search.log',deadline,4)
            found=p/'energy.report.json';cfg=p/'energy.json';save(cfg,dict(base,vector=str(vector),report=str(found)))
            execute([energy,cfg],p/'energy.log',deadline,4);r=json.loads(found.read_text())
            values=struct.unpack('<4d',vector.read_bytes()[16:]);expected=sum((-v*(F(values[i])-F(values[j]))**2 for i,j,v in edges),F(0))
            assert r['indefiniteness_proved']==wanted and (expected<0)==wanted
            assert F(r['energy_integer'])*(F(2)**r['energy_quantum_exponent'])==expected
            assert not json.loads(report.read_text())['candidate_is_passivity_or_indefiniteness_proof']
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file()},
             C_negative_energy_search_controls_pass=True,higher_order_negative_vector_found_and_exactly_checked=True,
             signed_PSD_control_not_misclassified=True,candidate_float_ritz_values_never_promoted_to_proof=True,
             physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('energy-controls','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();run(a.energy_controls.resolve(),a.output.resolve())
