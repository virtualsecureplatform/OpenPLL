"""Check CHOLMOD symbolic counts against independent graph elimination."""
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


def graph_counts(n,edges,permutation):
    if sorted(permutation)!=list(range(n)):raise ValueError('complete permutation required')
    adjacency=[set() for _ in range(n)]
    for a,b in edges:adjacency[a].add(b);adjacency[b].add(a)
    result=[]
    for node in permutation:
        neighbors=adjacency[node];result.append(len(neighbors)+1)
        for a in neighbors:adjacency[a].update(neighbors-{a});adjacency[a].discard(node)
        adjacency[node]=set()
    return result


def run(output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    source=ROOT/'tools/sheet_charge/analyze_C_factor_pattern.cpp';compiler=Path(shutil.which('g++')).resolve()
    libs=[Path('/lib/x86_64-linux-gnu')/('lib'+n+'.so') for n in ('cholmod','amd','colamd','camd','ccolamd','suitesparseconfig','blas','lapack')]
    paths=[source,source.with_name('sparse_runs_v2.hpp'),source.with_name('zero_C_mask.hpp'),ROOT/'tools/charge_compiler/json.hpp',
        Path('/usr/include/suitesparse/cholmod.h'),Path('/usr/include/suitesparse/SuiteSparse_config.h'),compiler,
        *[p.resolve() for p in libs],Path(__file__).resolve(),Path(__file__).with_name('test_conservative_C.py')]
    pins={str(p):sha(p) for p in paths};binary=output/'analyze_C_factor_pattern'
    cases=[('path',6,[(i,i+1) for i in range(5)],set()),('cycle',6,[(i,(i+1)%6) for i in range(6)],set()),
           ('complete',5,[(i,j) for i in range(5) for j in range(i+1,5)],set()),
           ('masked',6,[(i,i+1) for i in range(5)],{2})]
    with lease(2,4,deadline):
        execute([compiler,'-std=c++20','-O3','-I/usr/include/suitesparse',source,'-lcholmod','-o',binary],output/'build.log',deadline,4)
        for label,n,edges,masked in cases:
            p=output/label;p.mkdir();path=p/'matrix.bin';edges=sorted({tuple(sorted(e)) for e in edges})
            matrix(path,sorted([(i,i,F(1)) for i in range(n)]+[(i,j,F(-1)) for i,j in edges]))
            mask=p/'mask.bin';mask.write_bytes(b'CZEROR01'+struct.pack('<Q',n)+bytes(i in masked for i in range(n)))
            cfg,report=p/'config.json',p/'report.json';save(cfg,dict(matrix=str(path),zero_rows=str(mask),node_count=n,
                maximum_pattern_bytes=1024**3,deadline_uptime=deadline,report=str(report)))
            execute([binary,cfg],p/'run.log',deadline,4);r=json.loads(report.read_text())
            expected=graph_counts(n,[(a,b) for a,b in edges if a not in masked and b not in masked],r['permutation'])
            assert r['column_counts']==expected
            assert int(r['symbolic_factor_nonzeros_exact'])==sum(expected)
            assert int(r['predicted_simplicial_L_index_value_bytes_exact'])==16*sum(expected)
            assert int(r['sum_squared_column_counts_exact'])==sum(x*x for x in expected)
            assert not r['numeric_factorization_started'] and not r['full_matrix_passivity_verified']
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file()},
             symbolic_C_factor_pattern_controls_pass=True,independent_graph_elimination_counts_match=True,
             numeric_factorization_started=False,native_solver_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output.resolve())
