"""Fraction controls for exact full-vector signed C energy and rejecting inputs."""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import shutil
import struct
import subprocess
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import lease
from test_conservative_C import matrix


def run(output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    source=ROOT/'tools/sheet_charge/certify_C_vector_energy.cpp';compiler=Path(shutil.which('g++')).resolve()
    paths=[source,source.with_name('sparse_runs_v2.hpp'),source.with_name('zero_C_mask.hpp'),ROOT/'tools/charge_compiler/json.hpp',
           compiler,Path(__file__).resolve(),Path(__file__).with_name('test_conservative_C.py')]
    pins={str(p):sha(p) for p in paths};binary=output/'certify_C_vector_energy';n=4
    with lease(2,4,deadline):
        execute([compiler,'-std=c++20','-O3',source,'-lgmpxx','-lgmp','-o',binary],output/'build.log',deadline,4)
        cases=[('PSD',[(0,1,F(-1)),(1,2,F(-2)),(2,3,F(-3))],[0,-1,2.25,3],set()),
               ('negative_but_every_pair_minor_positive',[(0,1,F(-5,2)),(0,2,F(-1)),(0,3,F(-1)),
                  (1,2,F(3,4)),(1,3,F(3,4)),(2,3,F(-3,4))],[0,-1,1,1],set()),
               ('masked',[(0,1,F(-1)),(1,2,F(2)),(2,3,F(-3))],[0,0.125,-0.25,2],{2}),
               ('zero',[(0,1,F(-1))],[0,0,0,0],set()),
               ('wide_signed_vector',[(0,1,F(-1)),(1,2,F(-1))],[0,1e200,-1e-200,0],set())]
        for label,edges,voltage,masked in cases:
            p=output/label;p.mkdir();path=p/'C.bin';matrix(path,sorted(edges))
            zero=p/'zero.bin';zero.write_bytes(b'CZEROR01'+struct.pack('<Q',n)+bytes(i in masked for i in range(n)))
            vector=p/'vector.bin';vector.write_bytes(b'DDVEC001'+struct.pack('<Q',n)+struct.pack('<4d',*voltage))
            cfg,report=p/'config.json',p/'report.json';base=dict(matrix=str(path),zero_rows=str(zero),vector=str(vector),
                 node_count=n,coefficient_quantum_exponent=-166,deadline_uptime=deadline,report=str(report));save(cfg,base)
            execute([binary,cfg],p/'run.log',deadline,4);r=json.loads(report.read_text())
            values=[-v*(F(voltage[i])-F(voltage[j]))**2 for i,j,v in edges if i not in masked and j not in masked]
            expected=sum(values,F(0));actual=F(r['energy_integer'])*(F(2)**r['energy_quantum_exponent'])
            assert actual==expected and r['indefiniteness_proved']==(expected<0)
            assert F(r['absolute_contribution_integer'])*(F(2)**r['energy_quantum_exponent'])==sum(map(abs,values),F(0))
            assert not r['full_matrix_passivity_verified']
            for fault in ('nonzero_reference','nonfinite','truncated'):
                bad=p/(fault+'.bin');v=list(voltage)
                if fault=='nonzero_reference':v[0]=1
                if fault=='nonfinite':v[1]=float('nan')
                data=b'DDVEC001'+struct.pack('<Q',n)+struct.pack('<4d',*v);bad.write_bytes(data[:-1] if fault=='truncated' else data)
                cfg=p/(fault+'.json');save(cfg,dict(base,vector=str(bad)))
                q=subprocess.run([str(binary),str(cfg)],capture_output=True,text=True,timeout=30)
                save(p/(fault+'.result.json'),dict(returncode=q.returncode,stderr=q.stderr));assert q.returncode!=0
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file()},
             exact_signed_C_vector_energy_controls_pass=True,independent_Fraction_energy_and_absolute_sum_match=True,
             higher_order_negative_energy_witness_checked=True,nonnegative_energy_not_PSD_checked=True,
             signed_wide_range_and_zero_vectors_checked=True,invalid_vector_guards_checked=True,
             physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    run(p.parse_args().output.resolve())
