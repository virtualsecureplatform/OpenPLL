"""Compiled positive-vector search followed by exact weighted DD verification."""
import argparse,json,os,subprocess,time,struct
from pathlib import Path
from common import save,sha
from resources import lease,identity
from compiled_charge import execute
from test_G_edge_operator_v2 import matrix


def run(out):
    out.mkdir(parents=True,exist_ok=False);root=Path.cwd();base=root/'build/signoff400'
    proof=base/'startup_timing_ideal_substrate_references_001/assessment.json';a=json.loads(proof.read_text());full=Path(a['folded_matrices']['physical_integral'])
    prior=base/'startup_timing_grounded_C_diagonal_dominance_001/assessment.json'
    sources=[root/'tools/sheet_charge/search_weighted_DD.cpp',root/'tools/sheet_charge/certify_weighted_diagonal_dominance.cpp']
    paths=[proof,prior,full,*sources,root/'tools/sheet_charge/sparse_runs_v2.hpp',root/'tools/charge_compiler/json.hpp',Path(__file__).resolve(),root/'verification/signoff400/test_G_edge_operator_v2.py']
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),cpu_slots=8,memory_GiB=8,deadline_uptime=deadline,automatic_identical_retry=False))
    def status(state,**kw):save(out/'status.json',dict(state=state,release_qualified=False,**kw))
    status('waiting_for_shared_resources')
    try:
        with lease(8,8,deadline):
            pins={str(p):sha(p) for p in paths}
            if pins[str(full)]!=a['artifacts'][str(full)]:raise ValueError('matrix lineage hash mismatch')
            binaries=[]
            for source in sources:
                binary=out/source.stem;binaries.append(binary)
                with (out/(source.stem+'.build.log')).open('x') as log:subprocess.run(['g++','-std=c++20','-O3','-fopenmp','-fno-fast-math','-ffp-contract=off',str(source),'-lgmpxx','-lgmp','-o',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120)
            search,verify=binaries;controls=out/'controls';controls.mkdir();artifacts={str(p):sha(p) for p in binaries}
            def check_vector(label,m,n,z,destination):
                vector=destination/(label+'.vec')
                if isinstance(z,list):vector.write_bytes(b'DDVEC001'+struct.pack('<Q',n)+struct.pack('<'+'d'*n,*z))
                else:vector=z
                cfg=destination/(label+'.verify.json');report=destination/(label+'.verify.report.json');save(cfg,dict(matrix=str(m),node_count=n,ground_id=0,vector=str(vector),deadline_uptime=deadline,report=str(report)));execute([verify,cfg],destination/(label+'.verify.log'),deadline,6);return json.loads(report.read_text())
            def search_matrix(label,m,n,destination):
                vector=destination/(label+'.vec');cfg=destination/(label+'.search.json');report=destination/(label+'.search.report.json')
                save(cfg,dict(matrix=str(m),node_count=n,ground_id=0,threads=8,iterations=256,maximum_adjacency_bytes=3*1024**3,deadline_uptime=deadline,vector=str(vector),report=str(report)))
                execute([search,cfg],destination/(label+'.search.log'),deadline,6)
                return vector,json.loads(report.read_text())
            spd=controls/'SPD_not_DD.bin';matrix(spd,[(1,1,1),(1,2,2),(2,2,5)])
            r=check_vector('explicit_positive_weight',spd,3,[0,2.25,1],controls)
            if not r['grounded_SPD_certified_by_strict_weighted_diagonal_dominance']:raise ValueError('exact positive weight certificate')
            v,s=search_matrix('searched_positive_weight',spd,3,controls);r=check_vector('searched_positive_weight',spd,3,v,controls)
            if not r['grounded_SPD_certified_by_strict_weighted_diagonal_dominance']:raise ValueError('search plus exact certificate')
            indefinite=controls/'indefinite.bin';matrix(indefinite,[(1,1,1),(1,2,2),(2,2,1)])
            r=check_vector('indefinite',indefinite,3,[0,2.25,1],controls)
            if r['grounded_PSD_certified_by_exact_weighted_diagonal_dominance'] or r['indefiniteness_proved']:raise ValueError('sufficient certificate semantics')
            for label,vector in [('zero_weight',[0,0,1]),('negative_weight',[0,-1,1]),('nonzero_reference',[1,1,1])]:
                v=controls/(label+'.vec');v.write_bytes(b'DDVEC001'+struct.pack('<Q',3)+struct.pack('<ddd',*vector));cfg=controls/(label+'.json');save(cfg,dict(matrix=str(spd),node_count=3,ground_id=0,vector=str(v),deadline_uptime=deadline,report=str(controls/(label+'.report.json'))));f=subprocess.run([str(verify),str(cfg)],capture_output=True,text=True,timeout=30);save(controls/(label+'.result.json'),dict(returncode=f.returncode,stderr=f.stderr))
                if f.returncode==0:raise ValueError('invalid weight accepted')
            status('searching_full_physical_integral_weight_vector');vector,search_result=search_matrix('physical_integral',full,a['ideal_native_conductor_nets'],out)
            status('verifying_every_weighted_row_exactly');result=check_vector('physical_integral',full,a['ideal_native_conductor_nets'],vector,out)
            for p in [vector,out/'physical_integral.search.report.json',out/'physical_integral.verify.report.json']:artifacts[str(p)]=sha(p)
            if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('inputs changed during weighted certificate')
            save(out/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,search=search_result,result=result,exact_weighted_diagonal_dominance_controls_pass=True,all_grounded_rows_checked_exactly=True,candidate_vector_strictly_positive=True,grounded_ideal_conductor_PSD_certified=result['grounded_PSD_certified_by_exact_weighted_diagonal_dominance'],grounded_ideal_conductor_SPD_certified=result['grounded_SPD_certified_by_strict_weighted_diagonal_dominance'],scope='ideal original-conductor physical-integral principal matrix; not full spatial C',failed_sufficient_certificate_is_not_indefiniteness=True,full_spatial_passivity_verified=False,physical_RC_qualified=False,release_qualified=False))
            status('exact_weighted_diagonal_dominance_audit_complete')
    except BaseException as e:
        status('stopped_without_promotion',reason=repr(e));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
