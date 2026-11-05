"""Independent graph controls for a conductor-block preconditioner pattern."""
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
from test_C_factor_pattern_v2 import graph_counts


def run(output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    source=ROOT/'tools/sheet_charge/analyze_component_CG_pattern.cpp';compiler=Path(shutil.which('g++')).resolve()
    paths=[source,*[source.with_name(n) for n in ('sparse_runs_v2.hpp','zero_C_mask.hpp','conductor_map.hpp')],
        ROOT/'tools/charge_compiler/json.hpp',Path('/usr/include/suitesparse/cholmod.h'),Path('/usr/include/suitesparse/SuiteSparse_config.h'),compiler,
        *[(Path('/lib/x86_64-linux-gnu')/('lib'+n+'.so')).resolve() for n in ('cholmod','amd','colamd','camd','ccolamd','suitesparseconfig','blas','lapack')],
        Path(__file__).resolve(),Path(__file__).with_name('test_conservative_C.py'),Path(__file__).with_name('test_C_factor_pattern_v2.py')]
    pins={str(p):sha(p) for p in paths};binary=output/'analyze_component_CG_pattern'
    n=7;groups=[0,1,1,1,2,2,2];c_edges={(0,1),(1,2),(1,3),(2,4),(4,5),(4,6),(5,6)}
    g_edges=[{(1,2),(2,3),(4,5),(5,6)},{(2,3)}]
    with lease(2,4,deadline):
        execute([compiler,'-std=c++20','-O3','-I/usr/include/suitesparse',source,'-lcholmod','-o',binary],output/'build.log',deadline,4)
        for label,masked in [('all',set()),('source_zero_C',{3})]:
            p=output/label;p.mkdir();c=p/'C.bin';matrix(c,sorted([(i,i,F(1)) for i in range(n)]+[(i,j,F(-1)) for i,j in c_edges]))
            gs=[]
            for k,edges in enumerate(g_edges):
                g=p/f'G_{k}.bin';matrix(g,sorted((i,j,F(-2)) for i,j in edges));gs.append(g)
            zero=p/'zero.bin';zero.write_bytes(b'CZEROR01'+struct.pack('<Q',n)+bytes(i in masked for i in range(n)))
            components=p/'components.bin';components.write_bytes(b'CNETDOF1'+struct.pack('<QQ',n,3)+struct.pack('<7I',*groups))
            cfg,report=p/'config.json',p/'report.json';base=dict(matrix=str(c),G_matrices=list(map(str,gs)),zero_rows=str(zero),
                components=str(components),node_count=n,maximum_pattern_bytes=1024**3,deadline_uptime=deadline,report=str(report));save(cfg,base)
            execute([binary,cfg],p/'run.log',deadline,4);r=json.loads(report.read_text())
            kept={(a,b) for a,b in c_edges if a not in masked and b not in masked and groups[a]==groups[b]}|set.union(*g_edges)
            expected=graph_counts(n,sorted(kept),r['permutation'])
            assert r['column_counts']==expected and r['pattern_upper_nonzeros']==n+len(kept)
            assert int(r['symbolic_factor_nonzeros_exact'])==sum(expected)
            assert r['cross_component_C_keys_excluded_from_preconditioner']==2
            assert r['all_G_edges_retained_including_source_zero_C_states'] and not r['numeric_factorization_started']
            for fault in ('cross_G','duplicate_source','small_budget'):
                bad=dict(base)
                if fault=='cross_G':
                    path=p/'cross_G.bin';matrix(path,[(1,5,F(-1))]);bad['G_matrices']=[str(path)]
                if fault=='duplicate_source':bad['G_matrices']=[str(c)]
                if fault=='small_budget':bad['maximum_pattern_bytes']=1
                path=p/(fault+'.json');save(path,bad)
                rejected=subprocess.run([str(binary),str(path)],capture_output=True,text=True,timeout=30)
                save(p/(fault+'.result.json'),dict(returncode=rejected.returncode,stderr=rejected.stderr));assert rejected.returncode!=0
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file()},
             component_CG_pattern_controls_pass=True,independent_graph_elimination_counts_match=True,
             duplicate_C_G_keys_coalesced=True,G_edges_on_source_zero_C_states_retained=True,
             cross_component_G_and_memory_guards_checked=True,native_solver_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    run(p.parse_args().output.resolve())
