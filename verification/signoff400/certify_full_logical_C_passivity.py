"""Search a positive scaling, then verify full logical-C passivity with exact integers."""
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
    output.mkdir(parents=True,exist_ok=False);parent=json.loads((candidate/'owner.json').read_text())
    wait_deadline=parent['deadline_uptime']+60
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),producer_pid=parent['pid'],producer_birth=parent['birth'],
         wait_deadline_uptime=wait_deadline,deadline_uptime=wait_deadline+43200,computation_wall_limit_s=43200,
         cpu_slots=16,memory_GiB=32,automatic_identical_retry=False))
    def status(state,**more):save(output/'status.json',dict(state=state,release_qualified=False,**more))
    try:
        while not (candidate/'assessment.json').exists():
            if identity(parent['pid'])!=parent['birth']:raise RuntimeError('candidate producer terminal without complete operator certificate')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=wait_deadline:raise TimeoutError('operator-certificate observation budget exhausted')
            status('waiting_for_exact_logical_C_derivative',producer_pid=parent['pid']);time.sleep(2)
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
        receipt=candidate/'assessment.json';a=json.loads(receipt.read_text());op_path=Path(a['logical_operator_manifest'])
        op=json.loads(op_path.read_text());control=controls/'assessment.json';c=json.loads(control.read_text());verify(c['input_sha256'])
        if (a.get('conservative_C_stored_coefficient_derivative_certified') is not True
                or a['results']['negative_new_conservative_diagonals']!=0
                or c.get('logical_C_exact_weighted_DD_controls_pass') is not True):
            raise ValueError('nonnegative exact diagonals, certified derivative, and controlled DD verifier required')
        matrix=Path(op['source_matrix']['path']);zero=Path(op['zero_rows']['path']);diagonal=Path(op['correction_certificate']['path'])
        binaries=[controls/name for name in ('search_logical_C_weighted_DD','certify_logical_C_weighted_DD')]
        expected={str(op_path):a['artifacts'][str(op_path)],str(matrix):op['source_matrix']['sha256'],
                  str(zero):op['zero_rows']['sha256'],str(diagonal):op['correction_certificate']['sha256']}
        expected.update({str(p):c['artifacts'][str(p)] for p in binaries})
        paths=list(dict.fromkeys([receipt,op_path,control,matrix,zero,diagonal,*binaries,*map(Path,c['input_sha256']),Path(__file__).resolve()]))
        os.environ.update(OMP_NUM_THREADS='16',OMP_THREAD_LIMIT='16',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        status('waiting_for_sixteen_CPU_32GiB_passivity_lease')
        with lease(16,32,deadline):
            status('hashing_full_logical_C_operator')
            with ThreadPoolExecutor(max_workers=16) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            if any(pins[path]!=h for path,h in expected.items()):raise ValueError('full logical C or controlled verifier changed')
            save(output/'input_manifest.json',dict(input_sha256=pins))
            base=dict(matrix=str(matrix),zero_rows=str(zero),diagonal_certificate=str(diagonal),node_count=op['node_count'],
                      ground_id=0,coefficient_quantum_exponent=op['correction_certificate']['binary_quantum_exponent'],deadline_uptime=deadline)
            vector=output/'weights.bin';search_cfg,search_report=output/'search.json',output/'search.report.json'
            save(search_cfg,dict(base,threads=16,iterations=256,maximum_adjacency_bytes=24*1024**3,vector=str(vector),report=str(search_report)))
            status('searching_full_spatial_C_positive_scaling',maximum_iterations=256)
            execute([binaries[0],search_cfg],output/'search.log',deadline,32)
            cfg,report=output/'verify.json',output/'verify.report.json';save(cfg,dict(base,vector=str(vector),report=str(report)))
            status('verifying_every_implicit_diagonal_and_weighted_margin_exactly')
            execute([binaries[1],cfg],output/'verify.log',deadline,12);result=json.loads(report.read_text())
            with ThreadPoolExecutor(max_workers=16) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):raise ValueError('logical C passivity inputs changed')
            artifacts={str(p):sha(p) for p in (vector,search_cfg,search_report,cfg,report)}
            save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=result,
                 search=json.loads(search_report.read_text()),scope='entire source-zero-row-corrected spatial C operator, explicit reference 0 retained',
                 full_spatial_C_passivity_certified=result['full_matrix_passivity_verified'],
                 full_matrix_passivity_verified=result['full_matrix_passivity_verified'],
                 failed_sufficient_certificate_is_not_indefiniteness=True,
                 physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
            status('full_logical_C_passivity_audit_complete',full_spatial_C_passivity_certified=result['full_matrix_passivity_verified'],
                   negative_weighted_margins=result['negative_margin_rows'])
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','controls','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();run(a.candidate.resolve(),a.controls.resolve(),a.output.resolve())
