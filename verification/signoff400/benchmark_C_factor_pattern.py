"""Benchmark symbolic factor fill on a complete spatial C pattern; no numeric solve."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import time
from common import save,sha,verify
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
        if c.get('symbolic_C_factor_pattern_controls_pass') is not True:raise ValueError('independent graph elimination controls required')
        binary=controls/'analyze_C_factor_pattern'
        expected={str(op_path):a['artifacts'][str(op_path)],str(matrix):op['source_matrix']['sha256'],
                  str(mask):op['zero_rows']['sha256'],str(binary):c['artifacts'][str(binary)]}
        paths=list(dict.fromkeys([receipt,op_path,matrix,mask,control,binary,*map(Path,c['input_sha256']),Path(__file__).resolve()]))
        os.environ.update(OMP_NUM_THREADS='4',OMP_THREAD_LIMIT='4',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        status('waiting_for_full_C_pattern_resource_lease')
        with lease(4,32,deadline):
            status('hashing_full_C_pattern_inputs')
            with ThreadPoolExecutor(max_workers=4) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            if any(pins[p]!=h for p,h in expected.items()):raise ValueError('pattern benchmark inputs changed')
            save(output/'input_manifest.json',dict(input_sha256=pins))
            cfg,report=output/'config.json',output/'report.json'
            save(cfg,dict(matrix=str(matrix),zero_rows=str(mask),node_count=op['node_count'],
                 maximum_pattern_bytes=24*1024**3,deadline_uptime=deadline,report=str(report)))
            status('building_complete_C_pattern_and_analyzing_AMD_fill')
            execute([binary,cfg],output/'run.log',deadline,32);result=json.loads(report.read_text())
            with ThreadPoolExecutor(max_workers=4) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):raise ValueError('pattern benchmark inputs changed')
            save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (cfg,report)},results=result,
                 full_C_pattern_symbolic_analysis_completed=True,
                 simplicial_L_storage_alone_exceeds_native_48GiB_budget=int(result['predicted_simplicial_L_index_value_bytes_exact'])>48*1024**3,
                 benchmark_scope='C pattern only, all voltage states and explicit reference retained; G and nonlinear devices absent',
                 numeric_factorization_started=False,native_solver_qualified=False,KLU_memory_or_fill_bound_proved=False,
                 full_matrix_passivity_verified=False,physical_RC_qualified=False,release_qualified=False))
            status('full_C_pattern_symbolic_analysis_complete',factor_nonzeros=result['symbolic_factor_nonzeros_exact'])
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','controls','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();run(a.candidate.resolve(),a.controls.resolve(),a.output.resolve())
