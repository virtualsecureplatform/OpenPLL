"""Control rectangular P_float^T C with independent full symmetric matrices."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import struct
import subprocess
import time
from common import save,sha
from compiled_charge import execute
from resources import lease


def x87(n):
    n=int(n)
    if n==0:return bytes(10)
    sign=0x8000 if n<0 else 0;n=abs(n);bits=n.bit_length()
    return struct.pack('<QH',n<<(64-bits),sign+16383+bits-1)


def source_matrix(path,dense):
    rows=[(i,j,v) for i,row in enumerate(dense) for j,v in enumerate(row) if i<=j and v]
    with path.open('wb') as out:
        out.write(b'SPCRUN01'+struct.pack('<Q',len(rows)))
        for i,j,v in rows:out.write(struct.pack('<Q',i<<32|j)+x87(v)+x87(abs(v)+3)+struct.pack('<Q',1)+bytes(4))


def values(path):
    result={}
    with path.open('rb') as stream:
        if stream.read(8)!=b'QCRUN001':raise ValueError('charge control format')
        rows,columns,count=struct.unpack('<QQQ',stream.read(24))
        for _ in range(count):
            b=stream.read(40);key,=struct.unpack_from('<Q',b);sig,exp=struct.unpack_from('<QH',b,8)
            exponent=(exp&0x7fff)-16383-63
            if exp&0x7fff==0:exponent=1-16383-63
            result[key>>32,key&0xffffffff]=Fraction((-1 if exp&0x8000 else 1)*sig)*Fraction(2)**exponent
        if stream.read(1):raise ValueError('charge control trailing bytes')
    return rows,columns,{k:v for k,v in result.items() if v}


def run(output):
    output.mkdir(parents=True,exist_ok=False);root=Path.cwd();directory=root/'tools/sheet_charge'
    sources=[directory/n for n in ('project_floating_charge_rows.cpp','merge_charge_rows.cpp','charge_rows.hpp','sparse_run_slice.hpp','sparse_runs_v2.hpp')]+[root/'tools/charge_compiler/json.hpp',Path(__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    with lease(8,8,deadline):
        pins={str(p):sha(p) for p in sources};binaries=[]
        for name in ('project_floating_charge_rows','merge_charge_rows'):
            binary=output/name
            with (output/(name+'.build.log')).open('x') as log:subprocess.run(['g++','-std=c++20','-O3','-fopenmp','-fno-fast-math','-ffp-contract=off',str(directory/(name+'.cpp')),'-o',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120)
            binaries.append(binary)
        projector,merger=binaries;N=24;component=[0,1]+[2]*11+[3]*11;roles=[0,1,2,2];dense=[[0]*N for _ in range(N)]
        edges=[(0,i,i%7+1) for i in range(2,N)]+[(1,i,3) for i in range(2,N)]+[(i,i+1,5) for i in range(2,N-1)]+[(3,17,-2)]
        for a,b,c in edges:dense[a][a]+=c;dense[b][b]+=c;dense[a][b]-=c;dense[b][a]-=c
        results=[]
        for label,permutation in (('normal',list(range(N))),('permuted',[0,1]+list(range(N-1,1,-1)))):
            matrix=[[dense[i][j] for j in permutation] for i in permutation];comps=[component[i] for i in permutation]
            expected={(r,j):Fraction(sum(matrix[i][j] for i in range(N) if comps[i]==r+2)) for r in range(2) for j in range(N)};expected={k:v for k,v in expected.items() if v}
            for threads in (1,4,8):
                where=output/f'{label}_{threads}';where.mkdir();source=where/'C.bin';source_matrix(source,matrix)
                cm=where/'components.bin';cm.write_bytes(b'CNETDOF1'+struct.pack('<QQ',N,4)+struct.pack('<'+'I'*N,*comps));rm=where/'roles.bin';rm.write_bytes(b'GROLE001'+struct.pack('<QQ',4,4)+bytes(roles))
                cfg=where/'project.json';save(cfg,dict(matrix=str(source),components=str(cm),roles=str(rm),threads=threads,max_accumulator_entries=16,deadline_uptime=deadline,output=str(where/'runs')))
                execute([projector,cfg],where/'project.log',deadline,4);summary=json.loads((where/'project.log').read_text());runs=sorted((where/'runs').glob('part_*_run_*.bin'))
                if summary['sparse_runs']!=len(runs):raise ValueError('charge run coverage control')
                cfg=where/'merge.json';merged=where/'Q.bin';save(cfg,dict(inputs=list(map(str,runs)),output=str(merged),deadline_uptime=deadline))
                execute([merger,cfg],where/'merge.log',deadline,4)
                if values(merged)!=(2,N,expected):raise ValueError('independent full symmetric charge restriction differs')
                report=json.loads((where/'merge.log').read_text())
                if report['maximum_scaled_global_voltage_gauge_residual']!=0 or report['zero_charge_rows']!=0:raise ValueError('charge gauge control')
                results.append(dict(label=label,threads=threads,runs=len(runs),entries=report['entries']))
        if not any(r['runs']>r['threads'] for r in results):raise ValueError('forced flush control required')
        # Preserve a zero operator with all of its declared charge rows.
        empty=output/'empty';empty.mkdir();source=empty/'C.bin';source_matrix(source,[[0]*N for _ in range(N)])
        cfg=empty/'project.json';save(cfg,dict(matrix=str(source),components=str(cm),roles=str(rm),threads=4,max_accumulator_entries=16,deadline_uptime=deadline,output=str(empty/'runs')))
        execute([projector,cfg],empty/'project.log',deadline,4);merged=empty/'Q.bin';cfg=empty/'merge.json';save(cfg,dict(inputs=list(map(str,sorted((empty/'runs').glob('part_*_run_*.bin')))),output=str(merged),deadline_uptime=deadline));execute([merger,cfg],empty/'merge.log',deadline,4)
        if values(merged)!=(2,N,{}):raise ValueError('zero charge row preservation')
        malformed=[]
        valid=output/'normal_1/Q.bin'
        for label,content in (('wrong_magic',(output/'normal_1/C.bin').read_bytes()),('trailing',valid.read_bytes()+b'x'),('truncated',valid.read_bytes()[:-1])):
            path=output/(label+'.bin');path.write_bytes(content);cfg=output/(label+'.json');save(cfg,dict(inputs=[str(path)],output=str(output/(label+'.out')),deadline_uptime=deadline));r=subprocess.run([str(merger),str(cfg)],capture_output=True,text=True);save(output/(label+'.result.json'),dict(returncode=r.returncode,stderr=r.stderr))
            if r.returncode==0:raise ValueError('malformed charge run accepted')
            malformed.append(label)
        if any(sha(p)!=pins[str(p)] for p in sources):raise ValueError('charge controls source changed')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in binaries},results=results,
             rectangular_floating_charge_projection_controls_pass=True,full_symmetric_reference_checked=True,
             threads_checked=[1,4,8],two_voltage_permutations_checked=True,forced_flush_and_zero_rows_pass=True,
             malformed_formats_rejected=malformed,initial_charge_values_assigned=False,physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
