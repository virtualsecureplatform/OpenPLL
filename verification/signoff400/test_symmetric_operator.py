"""Validate parallel stored-symmetric matrix application; no physical promotion."""
import argparse,json,os,subprocess,time
from pathlib import Path
from fractions import Fraction
from common import save,sha
from resources import lease,identity
from compiled_charge import execute
from test_G_edge_operator_v2 import matrix


def run(output):
    output.mkdir(parents=True,exist_ok=False);root=Path.cwd()
    source=root/'tools/sheet_charge/evaluate_symmetric_operator.cpp'
    proof=root/'build/signoff400/startup_timing_native_SPICE_C_matrix_001/assessment.json'
    a=json.loads(proof.read_text());full=Path(a['matrix'])
    paths=[proof,full,source,root/'tools/sheet_charge/symmetric_operator.hpp',root/'tools/sheet_charge/sparse_runs_v2.hpp',root/'tools/charge_compiler/json.hpp',Path(__file__).resolve(),root/'verification/signoff400/test_G_edge_operator_v2.py']
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),cpu_slots=8,memory_GiB=8,deadline_uptime=deadline,automatic_identical_retry=False))
    def status(state,**kw):save(output/'status.json',dict(state=state,release_qualified=False,**kw))
    status('waiting_for_shared_resources')
    try:
        with lease(8,8,deadline):
            pins={str(p):sha(p) for p in paths}
            if pins[str(full)]!=a['artifacts'][str(full)]:raise ValueError('matrix receipt hash mismatch')
            binary=output/'evaluate_symmetric_operator'
            with (output/'build.log').open('x') as log:subprocess.run(['g++','-std=c++20','-O3','-fopenmp','-fno-fast-math','-ffp-contract=off',str(source),'-o',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120)
            fixture=output/'controls';fixture.mkdir()
            entries=[(0,0,Fraction(3,8)),(0,1,Fraction(-1,4)),(0,3,Fraction(7,16)),(1,1,Fraction(-5,8)),(1,2,Fraction(1,32)),(2,2,Fraction(9,4)),(2,3,Fraction(-1,8))]
            m=fixture/'signed.bin';matrix(m,entries)
            dense=[[Fraction(0) for _ in range(5)] for _ in range(5)]
            for i,j,v in entries:
                dense[i][j]=v;dense[j][i]=v
            results={};artifacts={str(binary):sha(binary)}
            def evaluate(label,matrix_path,n,mode,voltage=None,**kw):
                report=output/(label+'.report.json');cfg=output/(label+'.json')
                conf=dict(matrix=str(matrix_path),node_count=n,maximum_adjacency_bytes=4*1024**3,threads=[1,4,8],vector_mode=mode,deadline_uptime=deadline,report=str(report))
                if voltage is not None:conf['voltage']=voltage
                conf.update(kw);save(cfg,conf)
                execute([binary,cfg],output/(label+'.log'),deadline,6)
                found=json.loads(report.read_text());artifacts[str(report)]=sha(report)
                if not found['all_requested_thread_vectors_bit_identical'] or not found['independent_streamed_edge_scatter_matches_every_row']:raise ValueError('operator consistency failure')
                return found
            for label,v in [('constant',[1]*5),('signed',[.125,-.5,1.25,2,-3]),('zero',[0]*5)]:
                expected=[float(sum(dense[i][j]*Fraction(v[j]) for j in range(5))) for i in range(5)]
                found=evaluate('small_'+label,m,5,'explicit',v)
                if found['currents']!=expected:raise ValueError('exact dense signed symmetric reference mismatch')
            empty=fixture/'empty.bin';matrix(empty,[])
            if evaluate('empty',empty,5,'explicit',[1]*5)['currents']!=[0]*5:raise ValueError('empty matrix')
            # Reject invalid dimensions, memory limits, thread counts and nonfinite inputs.
            for label,change in [('bounds',dict(node_count=3)),('memory',dict(maximum_adjacency_bytes=1)),('thread_zero',dict(threads=[0])),('thread_excess',dict(threads=[33])),('short_vector',dict(voltage=[1]))]:
                cfg=fixture/(label+'.json');conf=dict(matrix=str(m),node_count=5,maximum_adjacency_bytes=4*1024**3,threads=[1],vector_mode='explicit',voltage=[1]*5,deadline_uptime=deadline,report=str(fixture/(label+'.report.json')));conf.update(change);save(cfg,conf)
                trial=subprocess.run([str(binary),str(cfg)],capture_output=True,text=True,timeout=30);save(fixture/(label+'.result.json'),dict(returncode=trial.returncode,stderr=trial.stderr))
                if trial.returncode==0:raise ValueError('invalid input accepted: '+label)
            for mode in ('constant','vertex_pattern'):
                status('evaluating_full_native_SPICE_C',vector_mode=mode)
                results[mode]=evaluate('full_'+mode,full,a['results']['ideal_conductor_nodes'],mode)
            if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('operator input changed during controls')
            save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,compiled_stored_symmetric_operator_controls_pass=True,exact_signed_dense_controls_pass=True,invalid_dimension_memory_thread_vector_controls_pass=True,all_full_rows_match_independent_streamed_scatter=True,threads_checked=[1,4,8],all_full_vectors_bit_identical_across_threads=True,stored_diagonal_and_signed_offdiagonal_coefficients_preserved=True,matrix_units='raw EXT capacitance unit = 1e-18 F; output requires explicit SI scaling in future MNA integration',timing_observations_nonisolated=True,full_spatial_C_operator_validated=False,full_native_MNA_solver_integration_complete=False,physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
            status('symmetric_operator_controls_complete')
    except BaseException as e:
        status('stopped_without_promotion',reason=repr(e));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);run(p.parse_args().output.resolve())
