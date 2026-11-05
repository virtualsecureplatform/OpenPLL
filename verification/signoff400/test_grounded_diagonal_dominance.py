"""Exact sufficient passivity certificate, explicitly inconclusive when DD fails."""
import argparse,json,os,subprocess,time
from pathlib import Path
from fractions import Fraction
from concurrent.futures import ThreadPoolExecutor
from common import save,sha
from resources import lease,identity
from compiled_charge import execute
from test_G_edge_operator_v2 import matrix


def run(out):
    out.mkdir(parents=True,exist_ok=False);root=Path.cwd();base=root/'build/signoff400'
    proofs=[base/'startup_timing_ideal_substrate_references_001/assessment.json',base/'startup_timing_native_SPICE_C_matrix_001/assessment.json']
    p,s=[json.loads(x.read_text()) for x in proofs]
    inputs=[('physical_integral',Path(p['folded_matrices']['physical_integral']),p['ideal_native_conductor_nets'],p),('native_SPICE',Path(s['matrix']),s['results']['ideal_conductor_nodes'],s)]
    source=root/'tools/sheet_charge/certify_grounded_diagonal_dominance.cpp';paths=[*proofs,source,root/'tools/sheet_charge/sparse_runs_v2.hpp',root/'tools/charge_compiler/json.hpp',Path(__file__).resolve(),root/'verification/signoff400/test_G_edge_operator_v2.py',*[x[1] for x in inputs]]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),cpu_slots=2,memory_GiB=8,deadline_uptime=deadline,automatic_identical_retry=False))
    def status(state,**kw):save(out/'status.json',dict(state=state,release_qualified=False,**kw))
    status('waiting_for_shared_resources')
    try:
        with lease(2,8,deadline):
            pins={str(x):sha(x) for x in paths}
            for _,path,_,receipt in inputs:
                if pins[str(path)]!=receipt['artifacts'][str(path)]:raise ValueError('matrix lineage hash mismatch')
            binary=out/'certify_grounded_diagonal_dominance'
            with (out/'build.log').open('x') as log:subprocess.run(['g++','-std=c++20','-O3','-fno-fast-math','-ffp-contract=off',str(source),'-lgmpxx','-lgmp','-o',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120)
            controls=out/'controls';controls.mkdir()
            fixtures=[('strict',[(0,0,1),(0,1,-1),(1,1,2),(1,2,-1),(2,2,2)],0,True,True),('weak',[(1,1,1),(1,2,-1),(2,2,1)],0,True,False),('SPD_but_not_DD',[(1,1,1),(1,2,2),(2,2,5)],0,False,False),('indefinite',[(1,1,1),(1,2,2),(2,2,1)],0,False,False),('tiny_negative_margin',[(1,1,Fraction((1<<64)-1,1<<64)),(1,2,-1),(2,2,1)],0,False,False),('different_ground',[(0,0,2),(0,1,-1),(1,1,2),(1,2,-1),(2,2,1)],2,True,True)]
            artifacts={str(binary):sha(binary)}
            def evaluate(label,path,n,ground,destination):
                cfg=destination/(label+'.json');report=destination/(label+'.report.json');save(cfg,dict(matrix=str(path),node_count=n,ground_id=ground,deadline_uptime=deadline,report=str(report)));execute([binary,cfg],destination/(label+'.log'),deadline,4);return json.loads(report.read_text())
            for name,entries,ground,weak,strict in fixtures:
                path=controls/(name+'.bin');matrix(path,entries);found=evaluate(name,path,3,ground,controls)
                if found['grounded_PSD_certified_by_exact_diagonal_dominance']!=weak or found['grounded_SPD_certified_by_strict_diagonal_dominance']!=strict or found['indefiniteness_proved']:raise ValueError('exact sufficient certificate control mismatch')
                if name=='tiny_negative_margin' and found['largest_negative_margin_integer']!='-1':raise ValueError('tiny exact margin lost')
            status('checking_full_grounded_matrices_exactly')
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures={name:pool.submit(evaluate,name,path,n,0,out) for name,path,n,_ in inputs}
                results={name:f.result() for name,f in futures.items()}
            for name in results:artifacts[str(out/(name+'.report.json'))]=sha(out/(name+'.report.json'))
            if any(sha(x)!=pins[str(x)] for x in paths):raise ValueError('input changed during exact audit')
            save(out/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,exact_grounded_diagonal_dominance_controls_pass=True,all_grounded_rows_checked_exactly=True,reference_voltage_fixed_to_zero=True,scope='ideal original conductor principal matrices only; not the full spatial voltage matrix',failed_sufficient_certificate_is_not_indefiniteness=True,physical_RC_qualified=False,release_qualified=False))
            status('exact_grounded_diagonal_dominance_audit_complete')
    except BaseException as e:
        status('stopped_without_promotion',reason=repr(e));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
