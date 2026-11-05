"""Independent Fraction checks of constructive negative-energy witnesses."""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import shutil
import subprocess
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import lease
from test_conservative_C import matrix


def run(output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    source=ROOT/'tools/sheet_charge/check_logical_C_principal_pairs.cpp'
    paths=[source,source.with_name('sparse_runs_v2.hpp'),source.with_name('zero_C_mask.hpp'),
           ROOT/'tools/charge_compiler/json.hpp',Path(shutil.which('g++')).resolve(),
           Path(__file__).resolve(),Path(__file__).with_name('test_conservative_C.py')]
    pins={str(p):sha(p) for p in paths};binary=output/'check_logical_C_principal_pairs'
    cases=[('PSD',[[F(1),F(1,2)],[F(1,2),F(1)]],False),
           ('negative_minor',[[F(1),F(2)],[F(2),F(1)]],True),
           ('zero_coupled',[[F(0),F(1)],[F(1),F(1)]],True),
           ('pair_screen_insufficient',[[F(1),F(3,4),F(3,4)],
                                         [F(3,4),F(1),F(-3,4)],[F(3,4),F(-3,4),F(1)]],False)]
    with lease(2,4,deadline):
        execute([paths[4],'-std=c++20','-O3','-fno-fast-math','-ffp-contract=off',source,'-lgmpxx','-lgmp','-o',binary],
                output/'build.log',deadline,4)
        for label,grounded,wanted in cases:
            p=output/label;p.mkdir();n=len(grounded)+1;dense=[[F(0) for _ in range(n)] for _ in range(n)]
            for i,row in enumerate(grounded,1):
                for j,value in enumerate(row,1):dense[i][j]=value
                dense[0][i]=dense[i][0]=-sum(row)
            dense[0][0]=-sum(dense[0]);assert all(sum(row)==0 for row in dense)
            mat=p/'matrix.bin';matrix(mat,[(i,j,dense[i][j]) for i in range(n) for j in range(i,n) if dense[i][j]])
            import struct
            zero=p/'zero.bin';zero.write_bytes(b'CZEROR01'+struct.pack('<Q',n)+bytes(n))
            rows=p/'rows.jsonl';rows.write_text(''.join(json.dumps(dict(row=i,conservative_diagonal_integer=str(int(dense[i][i]*2**128))))+'\n' for i in range(n)))
            cfg=p/'config.json';report=p/'report.json';save(cfg,dict(matrix=str(mat),zero_rows=str(zero),diagonal_certificate=str(rows),
                node_count=n,ground_id=0,coefficient_quantum_exponent=-128,deadline_uptime=deadline,report=str(report)))
            execute([binary,cfg],p/'run.log',deadline,4);r=json.loads(report.read_text())
            assert r['indefiniteness_proved']==wanted and not r['full_matrix_passivity_verified']
            expected=sum(grounded[i][i]*grounded[j][j]<grounded[i][j]**2 for i in range(n-1) for j in range(i+1,n-1))
            assert r['negative_principal_pairs']==expected
            for w in r['witnesses']:
                i,j=w['i'],w['j'];x,y=F(w['x']),F(w['y'])
                energy=dense[i][i]*x*x+2*dense[i][j]*x*y+dense[j][j]*y*y
                assert energy<0 and energy==F(w['energy_in_coefficient_quantum'])*F(1,2**128)
            if label=='pair_screen_insufficient':
                v=[F(-1),F(1),F(1)];assert sum(v[i]*grounded[i][j]*v[j] for i in range(3) for j in range(3))<0
            bad=json.loads(cfg.read_text());bad['ground_id']=1;save(p/'bad_ground.json',bad)
            rejected=subprocess.run([str(binary),str(p/'bad_ground.json')],capture_output=True,text=True,timeout=30)
            assert rejected.returncode!=0
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file()},
             exact_principal_pair_controls_pass=True,negative_energy_witnesses_checked_by_Fraction=True,
             zero_diagonal_coupled_case_checked=True,passing_pair_screen_not_full_PSD_checked=True,
             physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    run(p.parse_args().output.resolve())
