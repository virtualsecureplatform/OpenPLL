"""Benchmark conductor-block C/G preconditioner fill while preserving full-equation obligations."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import identity,lease


def run(candidate,controls,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,
         cpu_slots=4,memory_GiB=32,computation_wall_limit_s=43200,automatic_identical_retry=False))
    def status(state,**kw):save(output/'status.json',dict(state=state,release_qualified=False,**kw))
    try:
        receipt=candidate/'assessment.json';a=json.loads(receipt.read_text());op_path=Path(a['logical_operator_manifest'])
        if a.get('conservative_C_stored_coefficient_derivative_certified') is not True:raise ValueError('complete candidate receipt required')
        op=json.loads(op_path.read_text());matrix=Path(op['source_matrix']['path']);mask=Path(op['zero_rows']['path'])
        control=controls/'assessment.json';c=json.loads(control.read_text());verify(c['input_sha256'])
        if c.get('component_CG_pattern_controls_pass') is not True:raise ValueError('independent graph elimination controls required')
        binary=controls/'analyze_component_CG_pattern'
        g_receipt=ROOT/'build/signoff400/startup_timing_G_components_001/assessment.json'
        g_config=g_receipt.parent/'config.json';g=json.loads(g_receipt.read_text());gc=json.loads(g_config.read_text())
        ns_receipt=ROOT/'build/signoff400/startup_timing_final_projection_namespace_reconciliation_001/assessment.json'
        ns=json.loads(ns_receipt.read_text());mapping_receipt=Path(ns['source_mapping'])/'assessment.json'
        mapping=json.loads(mapping_receipt.read_text());transform_path=Path(op['voltage_namespace_receipt']['path'])
        transform=json.loads(transform_path.read_text());projection=Path(ns['source_projection'])/'assessment.json'
        zero_map=Path(gc['zero_map']);original_map=Path(gc['original_net_map']);components=Path(gc['component_map'])
        gs=list(map(Path,gc['matrices']))
        if (g.get('all_conductance_graph_components_match_original_conductors') is not True
                or ns.get('both_final_node_maps_byte_identical') is not True
                or ns.get('independent_original_map_audit_bound') is not True
                or sha(mapping_receipt)!=ns['mapping_assessment_sha256']
                or g['input_sha256'][str(original_map)]!=mapping['artifacts'][str(original_map)]
                or g['input_sha256'][str(zero_map)]!=transform['input_sha256'][str(zero_map)]
                or transform['input_sha256'].get(str(projection))!=sha(projection)
                or ns['voltage_nodes']!=transform['transform_summary']['original_voltage_nodes']):
            raise ValueError('certified C/G component and final projection namespaces required')
        expected={str(op_path):a['artifacts'][str(op_path)],str(matrix):op['source_matrix']['sha256'],
                  str(mask):op['zero_rows']['sha256'],str(binary):c['artifacts'][str(binary)]}
        expected.update({str(components):g['artifacts'][str(components)],str(original_map):g['input_sha256'][str(original_map)],
                         str(zero_map):g['input_sha256'][str(zero_map)],str(transform_path):op['voltage_namespace_receipt']['sha256']})
        expected.update({str(path):g['input_sha256'][str(path)] for path in gs})
        paths=list(dict.fromkeys([receipt,op_path,matrix,mask,control,binary,g_receipt,g_config,ns_receipt,mapping_receipt,
             transform_path,projection,components,original_map,zero_map,*gs,*map(Path,c['input_sha256']),Path(__file__).resolve()]))
        os.environ.update(OMP_NUM_THREADS='4',OMP_THREAD_LIMIT='4',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        status('waiting_for_full_C_pattern_resource_lease')
        with lease(4,32,deadline):
            status('hashing_full_C_pattern_inputs')
            with ThreadPoolExecutor(max_workers=4) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            if any(pins[p]!=h for p,h in expected.items()):raise ValueError('pattern benchmark inputs changed')
            save(output/'input_manifest.json',dict(input_sha256=pins))
            cfg,report=output/'config.json',output/'report.json'
            save(cfg,dict(matrix=str(matrix),G_matrices=list(map(str,gs)),components=str(components),zero_rows=str(mask),node_count=op['node_count'],
                 maximum_pattern_bytes=24*1024**3,deadline_uptime=deadline,report=str(report)))
            status('building_component_CG_preconditioner_pattern_and_analyzing_AMD_fill')
            execute([binary,cfg],output/'run.log',deadline,32);result=json.loads(report.read_text())
            with ThreadPoolExecutor(max_workers=4) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):raise ValueError('pattern benchmark inputs changed')
            save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (cfg,report)},results=result,
                 component_CG_preconditioner_pattern_symbolic_analysis_completed=True,
                 simplicial_L_storage_alone_exceeds_native_48GiB_budget=int(result['predicted_simplicial_L_index_value_bytes_exact'])>48*1024**3,
                 benchmark_scope='conductor-block C plus all G-family patterns including unknown-law unit ndiode; structure only, not physical values',
                 full_cross_component_C_and_floating_charge_constraints_still_required=True,full_equations_modified=False,
                 numeric_factorization_started=False,native_solver_qualified=False,KLU_memory_or_fill_bound_proved=False,
                 full_matrix_passivity_verified=False,physical_RC_qualified=False,release_qualified=False))
            status('component_CG_preconditioner_pattern_symbolic_analysis_complete',factor_nonzeros=result['symbolic_factor_nonzeros_exact'])
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','controls','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();run(a.candidate.resolve(),a.controls.resolve(),a.output.resolve())
