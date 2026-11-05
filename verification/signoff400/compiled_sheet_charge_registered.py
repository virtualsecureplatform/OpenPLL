"""Build/invoke the exact-geometry C++ sheet-charge integration candidate."""
from fractions import Fraction as F
from pathlib import Path
import shutil
import subprocess
import time
from common import ROOT,save,sha
from compiled_charge import execute
SOURCE=ROOT/'tools/sheet_charge/main_registered.cpp';HEADER=ROOT/'tools/charge_compiler/json.hpp'
def payload(template,prefix,point_nodes=None):
    points=[]
    for pair in template['points']:
        row=[]
        for value in pair:
            value=F(value);numeric=float(value)
            if F(numeric)!=value:raise ValueError('mesh coordinate is not exactly serializable as binary64')
            row.append(numeric)
        points.append(row)
    result=dict(points=points,triangles=template['triangles'],prefix=prefix)
    if point_nodes is not None:
        if len(point_nodes)!=len(points):raise ValueError('point/node identity count differs')
        result['point_nodes']=list(point_nodes)
    return result
def encode_reference(basis,positions):
    if 'constant' in basis:return dict(constant=basis['constant'])
    names=sorted(positions,key=lambda n:int(n.rsplit('::',1)[1]));prefix=names[0].rsplit('::',1)[0]+'::';points=[positions[n] for n in names];indices={p:i for i,p in enumerate(points)}
    return payload(dict(points=points,triangles=[[indices[p] for p in triangle] for triangle,_ in basis['patches']]),prefix)
def build(output,deadline=None):
    out=Path(output);out.mkdir(parents=True,exist_ok=True);deadline=deadline or time.clock_gettime(time.CLOCK_BOOTTIME)+43200;compiler=Path(shutil.which('g++')).resolve();binary=out/'sheet_charge'
    if binary.exists():raise FileExistsError('fresh compiled sheet binary required')
    multiarch=subprocess.check_output([compiler,'-print-multiarch'],text=True).strip();headers=[Path('/usr/include/gmpxx.h'),Path('/usr/include')/multiarch/'gmp.h'];libraries=[Path(subprocess.check_output([compiler,'-print-file-name='+n],text=True).strip()).resolve() for n in ('libgmp.so','libgmpxx.so')]
    paths=[SOURCE,HEADER,compiler,Path(__file__).resolve(),*headers,*libraries];pins={str(p):sha(p) for p in paths}
    command=[compiler,'-std=c++20','-O3','-Wall','-Wextra','-Wpedantic','-fopenmp','-fno-fast-math','-ffp-contract=off',SOURCE,'-lgmpxx','-lgmp','-o',binary];execute(command,out/'build.log',deadline,8)
    for p,h in pins.items():
        if sha(p)!=h:raise ValueError('compiled sheet build input changed')
    save(out/'build.json',dict(command=list(map(str,command)),input_sha256=pins,artifacts={str(binary.resolve()):sha(binary)},compiler_version=subprocess.check_output([compiler,'--version'],text=True)))
    return binary

def invoke(binary,cases,output,threads=1,repeat=1,panel_fraction=.25,emit_exact=True,deadline=None,cache_mib=16):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);deadline=deadline or time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    rows=out/'cases.json';save(rows,cases);cfg=out/'config.json';save(cfg,dict(cases=str(rows),output=str(out/'matrices.jsonl'),deadline_uptime=deadline,threads=threads,repeat=repeat,panel_fraction=panel_fraction,emit_exact=emit_exact,cache_limit_bytes_per_thread=int(cache_mib*1024**2)))
    execute([binary,cfg],out/'native.log',deadline,8)
    import json
    return [json.loads(s) for s in (out/'matrices.jsonl').read_text().splitlines()],json.loads((out/'native.log').read_text())
def decode(row,exact=False):
    names=row['nodes']
    if exact:return {(names[a],names[b]):F(int(n),int(d)) for a,b,n,d in row['exact_matrix']}
    return {(names[a],names[b]):v for a,b,v in row['matrix']}
