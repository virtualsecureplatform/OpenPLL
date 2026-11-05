"""Enclose stored G diagonal roundoff exactly against its positive-edge graph."""
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
    sign=0x8000 if v<0 else 0;v=abs(v);k=v.denominator.bit_length()-1
    if v.denominator!=1<<k:raise ValueError('dyadic fixture required')
    n=v.numerator;bits=n.bit_length()
    if bits>64:raise ValueError('exact fixture significand')
    return struct.pack('<QH',n<<(64-bits),sign+16383+bits-1-k)


def matrix(path,entries):
    with path.open('wb') as out:
        out.write(b'SPCRUN01'+struct.pack('<Q',len(entries)))
        for i,j,v in entries:out.write(struct.pack('<Q',i<<32|j)+x87(v)+x87(max(abs(v),1))+struct.pack('<Q',1)+bytes(4))


def run(output):
    output.mkdir(parents=True,exist_ok=False);base=Path('build/signoff400').resolve()
    assembly=base/'startup_timing_known_conductance_001/assessment.json';components=base/'startup_timing_G_components_001/assessment.json'
    graph=base/'startup_timing_nominal_G_edge_graph_certificate_001/assessment.json'
    a,g,certificate=[json.loads(p.read_text()) for p in (assembly,components,graph)]
    component_map=components.parent/'constrained_voltage_conductors.bin'
    matrices=[('known',Path(a['zero_R_constrained_known_G_matrix'])),*[(f'family_{i}',Path(f['zero_R_constrained_unit_square_matrix'])) for i,f in enumerate(a['symbolic_material_families']['material_families'])]]
    source=Path('tools/sheet_charge/audit_G_dyadic_rounding.cpp').resolve();headers=[Path('tools/charge_compiler/json.hpp').resolve(),Path('tools/sheet_charge/sparse_runs_v2.hpp').resolve()]
    paths=[assembly,components,graph,component_map,*[p for _,p in matrices],source,*headers,Path(__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),cpu_slots=1,memory_GiB=4,deadline_uptime=deadline,automatic_identical_retry=False))
    def status(state,**more):save(output/'status.json',dict(state=state,release_qualified=False,**more))
    status('waiting_for_one_shared_CPU_slot')
    try:
        with lease(1,4,deadline):
            status('pinning_exact_dyadic_sources');pins={str(p):sha(p) for p in paths}
            if g['input_sha256'][str(assembly)]!=pins[str(assembly)] or certificate['input_sha256'][str(assembly)]!=pins[str(assembly)]:raise ValueError('graph assembly lineage differs')
            for proof,path in ((g,component_map),*((a,p) for _,p in matrices)):
                if proof['artifacts'][str(path)]!=pins[str(path)]:raise ValueError('G or component map changed')
            save(output/'input_manifest.json',dict(input_sha256=pins));binary=output/'audit_G_dyadic_rounding'
            with (output/'build.log').open('x') as log:subprocess.run(['g++','-std=c++20','-O3','-fno-fast-math',str(source),'-lgmpxx','-lgmp','-o',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120)
            fixture=output/'controls';fixture.mkdir();cm=fixture/'components.bin';cm.write_bytes(b'CNETDOF1'+struct.pack('<QQIII',3,2,0,1,1))
            trials=[('tiny_negative',[(1,1,Fraction((1<<64)-1,1<<64)),(1,2,-1),(2,2,1)],Fraction(1,(1<<65)-1),True),
                    ('above_screen',[(1,1,Fraction(5,4)),(1,2,-1),(2,2,1)],Fraction(1,9),False),('zero',[],Fraction(0),True)]
            for label,entries,ratio,within in trials:
                path=fixture/(label+'.bin');matrix(path,entries);cfg=fixture/(label+'.json');report=fixture/(label+'.report.json');save(cfg,dict(matrix=str(path),components=str(cm),node_count=3,deadline_uptime=deadline,report=str(report)))
                execute([binary,cfg],fixture/(label+'.log'),deadline,4);r=json.loads(report.read_text());observed=Fraction(int(r['maximum_scaled_diagonal_perturbation_numerator']),int(r['maximum_scaled_diagonal_perturbation_denominator']))
                if observed!=ratio or r['within_existing_1e12_gauge_screen_exact']!=within:raise ValueError('exact dyadic ratio controls')
                if label=='tiny_negative':
                    witness=r['first_negative_component_constant_witness']
                    if not r['stored_matrix_exact_PSD_disproved_by_witness'] or witness['component_id']!=1 or Fraction(int(witness['energy_integer']))*Fraction(2)**witness['energy_binary_exponent']!=-Fraction(1,1<<64):raise ValueError('negative constant-mode energy control')
            # A positive offdiagonal cannot receive this edge-graph certificate.
            path=fixture/'wrong_sign.bin';matrix(path,[(1,1,1),(1,2,1),(2,2,1)]);cfg=fixture/'wrong_sign.json';save(cfg,dict(matrix=str(path),components=str(cm),node_count=3,deadline_uptime=deadline,report=str(fixture/'wrong_sign.report.json')))
            bad=subprocess.run([str(binary),str(cfg)],capture_output=True,text=True);save(fixture/'wrong_sign.result.json',dict(returncode=bad.returncode,stderr=bad.stderr))
            if bad.returncode==0:raise ValueError('positive offdiagonal accepted')
            results={};artifacts={str(binary):sha(binary)}
            for label,path in matrices:
                status('exactly_accumulating_all_G_row_roundoff',matrix=label);cfg=output/(label+'.json');report=output/(label+'.report.json');save(cfg,dict(matrix=str(path),components=str(component_map),node_count=g['results']['constrained_voltage_nodes'],deadline_uptime=deadline,report=str(report)))
                execute([binary,cfg],output/(label+'.log'),deadline,4);results[label]=json.loads(report.read_text());artifacts[str(report)]=sha(report)
            if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('G input changed during exact audit')
            save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
                 stored_G_diagonal_difference_from_positive_edge_graph_exactly_enclosed=True,
                 exact_dyadic_controls_and_negative_energy_witness_pass=True,
                 all_matrices_within_existing_1e12_gauge_screen_exact=all(r['within_existing_1e12_gauge_screen_exact'] for r in results.values()),
                 bound_applies_to_exact_nonnegative_linear_combinations_of_audited_families=True,
                 additional_numeric_scaling_and_assembly_roundoff_enclosed=False,graph_operator_implemented_in_native_solver=False,
                 physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
            status('exact_G_diagonal_roundoff_audit_complete')
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
