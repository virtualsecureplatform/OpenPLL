"""Controls for exact interval overrides, untouched entries, and tolerance boundaries."""
import argparse
import copy
from fractions import Fraction as Q
import json
from pathlib import Path
import subprocess
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import lease
from test_conservative_C import matrix


def run(output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    source=ROOT/'tools/sheet_charge/compare_sparse_interval_reference.cpp'
    paths=[source,ROOT/'tools/sheet_charge/sparse_runs_v2.hpp',ROOT/'tools/charge_compiler/json.hpp',
           Path('/usr/bin/g++').resolve(),Path(__file__).resolve(),Path(__file__).with_name('test_conservative_C.py')]
    pins={str(p):sha(p) for p in paths};binary=output/'compare_sparse_interval_reference'
    with lease(1,2,deadline):
        execute(['g++','-std=c++20','-O3','-fno-fast-math','-ffp-contract=off',source,'-lgmpxx','-lgmp','-o',binary],output/'build.log',deadline,2)
        reference=dict(diagonal_0_interval=dict(lower_dyadic=['3',-2],upper_dyadic=['3',-2]),
                       edge_0_1_interval=dict(lower_dyadic=['-1',-2],upper_dyadic=['-1',-2]))
        left=[(0,0,Q(100)),(0,1,Q(20)),(1,1,Q(1)),(1,2,Q(-1)),(2,2,Q(1))]
        right=[(0,0,Q(3,4)),(0,1,Q(-1,4)),(1,1,Q(1)),(1,2,Q(-1)),(2,2,Q(1))]
        results=[]
        for name in ('corrected_reference','changed_coupling','wrong_reference','wide_interval','exact_boundary','above_boundary','missing_reference','unordered_interval'):
            folder=output/name;folder.mkdir();a,b=copy.deepcopy(left),copy.deepcopy(right);r=copy.deepcopy(reference)
            expected=name in ('corrected_reference','exact_boundary')
            if name=='changed_coupling':b[3]=(1,2,Q(-3,2))
            if name=='wrong_reference':r['edge_0_1_interval']=dict(lower_dyadic=['1',-2],upper_dyadic=['1',-2])
            if name=='wide_interval':r['diagonal_0_interval']=dict(lower_dyadic=[str(3*2**27-1),-29],upper_dyadic=[str(3*2**27+1),-29])
            if name in ('exact_boundary','above_boundary'):
                a[2]=(1,1,Q(0));b[2]=(1,1,Q(1e-8)+(Q(2)**-90 if name=='above_boundary' else Q(0)))
            if name=='missing_reference':a=[v for v in a if v[:2]!=(0,1)];b=[v for v in b if v[:2]!=(0,1)]
            if name=='unordered_interval':r['diagonal_0_interval']=dict(lower_dyadic=['1',0],upper_dyadic=['0',0])
            lpath,rpath=folder/'left.bin',folder/'right.bin';matrix(lpath,a);matrix(rpath,b)
            scalar=folder/'reference.json';save(scalar,r);cfg,report=folder/'config.json',folder/'report.json'
            save(cfg,dict(left=str(lpath),right=str(rpath),interval_reference_report=str(scalar),node_count=3,
                 absolute_tolerance=1e-8,relative_tolerance=0,deadline_uptime=deadline,require_match=False,report=str(report)))
            p=subprocess.run([str(binary),str(cfg)],capture_output=True,text=True,timeout=60)
            save(folder/'execution.json',dict(returncode=p.returncode,stderr=p.stderr))
            if name in ('missing_reference','unordered_interval'):assert p.returncode!=0,name
            else:
                assert p.returncode==0,(name,p.stderr);v=json.loads(report.read_text())
                assert v['within_tolerance']==expected,name
                if name in ('exact_boundary','above_boundary'):assert v['exact_GMP_boundary_fallbacks']>=1
                if name=='wide_interval':assert not v['all_reference_intervals_narrow_enough'] and v['outside_tolerance_entries']==0
                results.append(dict(case=name,within_tolerance=v['within_tolerance']))
        verify(pins);artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file()}
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
             interval_reference_comparator_controls_pass=True,unchanged_entry_and_reference_namespace_guards_checked=True,
             exact_boundary_GMP_fallback_checked=True,whole_interval_and_width_criteria_checked=True,
             physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    run(p.parse_args().output.resolve())
