"""Verify deterministic parallel G evaluation against the controlled serial graph."""
import argparse
from fractions import Fraction
import json
import os
from pathlib import Path
import struct
import subprocess
import time
from common import save,sha
from compiled_charge import execute
from resources import identity,lease


def x87(v):
    v=Fraction(v)
    if not v:return bytes(10)
    sign=0x8000 if v<0 else 0;v=abs(v);k=v.denominator.bit_length()-1;n=v.numerator;bits=n.bit_length()
    if v.denominator!=1<<k or bits>64:raise ValueError('exact dyadic fixture')
    return struct.pack('<QH',n<<(64-bits),sign+16383+bits-1-k)


def matrix(path,entries):
    with path.open('wb') as out:
        out.write(b'SPCRUN01'+struct.pack('<Q',len(entries)))
        for i,j,v in entries:out.write(struct.pack('<Q',i<<32|j)+x87(v)+x87(max(abs(v),1))+struct.pack('<Q',1)+bytes(4))


def run(output):
    output.mkdir(parents=True,exist_ok=False);root=Path.cwd();base=root/'build/signoff400'
    assembly=base/'startup_timing_known_conductance_001/assessment.json';components=base/'startup_timing_G_components_001/assessment.json'
    rounding=base/'startup_timing_G_dyadic_rounding_001/assessment.json';a,g,r=[json.loads(p.read_text()) for p in (assembly,components,rounding)]
    component_map=components.parent/'constrained_voltage_conductors.bin';matrices=[('known',Path(a['zero_R_constrained_known_G_matrix'])),*[(f'family_{i}',Path(f['zero_R_constrained_unit_square_matrix'])) for i,f in enumerate(a['symbolic_material_families']['material_families'])]]
    serial=base/'startup_timing_G_edge_operator_controls_001/assessment.json';serial_proof=json.loads(serial.read_text())
    source=root/'tools/sheet_charge/evaluate_G_edge_operator_v2.cpp';headers=[root/'tools/sheet_charge/G_edge_operator_v2.hpp',root/'tools/sheet_charge/sparse_runs_v2.hpp',root/'tools/charge_compiler/json.hpp']
    paths=[serial,assembly,components,rounding,component_map,*[p for _,p in matrices],source,*headers,Path(__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),cpu_slots=8,memory_GiB=8,deadline_uptime=deadline,automatic_identical_retry=False))
    def status(state,**more):save(output/'status.json',dict(state=state,release_qualified=False,**more))
    status('waiting_for_eight_shared_CPU_slots')
    try:
        with lease(8,8,deadline):
            pins={str(p):sha(p) for p in paths}
            if r['input_sha256'][str(assembly)]!=pins[str(assembly)] or g['input_sha256'][str(assembly)]!=pins[str(assembly)]:raise ValueError('exact graph source lineage differs')
            for proof,path in ((g,component_map),*((a,p) for _,p in matrices)):
                if proof['artifacts'][str(path)]!=pins[str(path)]:raise ValueError('graph source artifact changed')
            binary=output/'evaluate_G_edge_operator_v2'
            with (output/'build.log').open('x') as log:subprocess.run(['g++','-std=c++20','-O3','-fopenmp','-fno-fast-math','-ffp-contract=off',str(source),'-o',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120)
            fixture=output/'controls';fixture.mkdir();tiny=fixture/'tiny_negative.bin';matrix(tiny,[(1,1,Fraction((1<<64)-1,1<<64)),(1,2,-1),(2,2,1)])
            trials=[('constant',tiny,[0,1,1],[0,0,0]),('nonconstant',tiny,[0,1.5,.5],[0,1,-1])]
            dense=[[Fraction(0) for _ in range(7)] for _ in range(7)]
            for i,j,w in ((0,1,Fraction(3,8)),(1,2,Fraction(7,16)),(1,4,Fraction(1,1024)),(3,5,Fraction(1024)),(4,6,Fraction(15,32)),(5,6,Fraction(1,4))):dense[i][i]+=w;dense[j][j]+=w;dense[i][j]-=w;dense[j][i]-=w
            ordinary=fixture/'ordinary.bin';matrix(ordinary,[(i,j,dense[i][j]) for i in range(7) for j in range(i,7) if dense[i][j]])
            vector=[Fraction(1,8),Fraction(7,8),Fraction(-1,4),Fraction(5,4),Fraction(3,8),Fraction(1,2),Fraction(11,8)];expected=[sum(dense[i][j]*vector[j] for j in range(7)) for i in range(7)]
            trials.append(('dyadic_reference',ordinary,list(map(float,vector)),list(map(float,expected))))
            for label,path,voltage,expected in trials:
                cfg=fixture/(label+'.json');report=fixture/(label+'.report.json');save(cfg,dict(matrix=str(path),node_count=len(voltage),maximum_adjacency_bytes=4*1024**3,threads=[1,4,8],vector_mode='explicit',voltage=voltage,deadline_uptime=deadline,report=str(report)))
                execute([binary,cfg],fixture/(label+'.log'),deadline,4);found=json.loads(report.read_text())
                if found['currents']!=expected or not found['independent_streamed_edge_scatter_matches_every_row']:raise ValueError('independent exact graph-vector control')
            bad=fixture/'wrong_sign.bin';matrix(bad,[(1,1,1),(1,2,1),(2,2,1)]);cfg=fixture/'wrong_sign.json';save(cfg,dict(matrix=str(bad),node_count=3,maximum_adjacency_bytes=4*1024**3,threads=[1,4,8],vector_mode='explicit',voltage=[0,1,1],deadline_uptime=deadline,report=str(fixture/'wrong_sign.report.json')))
            failed=subprocess.run([str(binary),str(cfg)],capture_output=True,text=True);save(fixture/'wrong_sign.result.json',dict(returncode=failed.returncode,stderr=failed.stderr))
            if failed.returncode==0:raise ValueError('nonpositive conductance edge accepted')
            results={};artifacts={str(binary):sha(binary)}
            for label,path in matrices:
                for mode in ('conductor_constants','vertex_pattern'):
                    status('evaluating_full_G_edge_operator',matrix=label,vector_mode=mode);cfg=output/f'{label}_{mode}.json';report=output/f'{label}_{mode}.report.json'
                    save(cfg,dict(matrix=str(path),node_count=g['results']['constrained_voltage_nodes'],maximum_adjacency_bytes=2*1024**3,threads=[1,4,8],vector_mode=mode,components=str(component_map),deadline_uptime=deadline,report=str(report)))
                    execute([binary,cfg],output/f'{label}_{mode}.log',deadline,4);found=json.loads(report.read_text())
                    if mode=='conductor_constants' and not found['exact_conductor_constant_annihilation']:raise ValueError('full conductor nullspace current leak')
                    prior=serial_proof['results'][label+'_'+mode]
                    for key in ('node_count','edges','nonzero_row_currents','maximum_absolute_current','absolute_current_sum'):
                        if found[key]!=prior[key]:raise ValueError('parallel graph result differs from controlled serial operator')
                    if not found['all_requested_thread_vectors_bit_identical']:raise ValueError('parallel graph determinism')
                    results[label+'_'+mode]=found;artifacts[str(report)]=sha(report)
            if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('source changed during graph operator controls')
            save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
                 compiled_incidence_form_G_evaluator_controls_pass=True,all_full_graph_rows_match_independent_edge_scatter=True,
                 all_conductor_constant_modes_annihilated_exactly=True,small_exact_dyadic_matrix_vector_controls_pass=True,
                 stored_diagonal_rounding_not_used_in_graph_current_evaluation=True,single_thread_execution_validated=True,multi_thread_execution_validated=True,threads_checked=[1,4,8],all_full_vectors_bit_identical_across_threads=True,timing_observations_nonisolated=True,
                 full_native_MNA_solver_integration_complete=False,material_parameters_selected=False,physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
            status('full_G_edge_evaluator_controls_complete')
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
