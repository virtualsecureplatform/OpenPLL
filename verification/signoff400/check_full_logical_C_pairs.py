"""Check necessary principal-pair conditions without claiming a full PSD certificate."""
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
         cpu_slots=4,memory_GiB=12,automatic_identical_retry=False))
    def status(state,**more):save(output/'status.json',dict(state=state,release_qualified=False,**more))
    try:
        while not (candidate/'assessment.json').exists():
            if identity(parent['pid'])!=parent['birth']:raise RuntimeError('candidate producer terminal without certificate')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=wait_deadline:raise TimeoutError('candidate observation budget exhausted')
            status('waiting_for_exact_logical_C_derivative',producer_pid=parent['pid']);time.sleep(2)
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
        receipt=candidate/'assessment.json';a=json.loads(receipt.read_text());op_path=Path(a['logical_operator_manifest'])
        control=controls/'assessment.json';c=json.loads(control.read_text());verify(c['input_sha256'])
        if (a.get('conservative_C_stored_coefficient_derivative_certified') is not True
                or a['results']['negative_new_conservative_diagonals']!=0
                or c.get('exact_principal_pair_controls_pass') is not True):
            raise ValueError('controlled principal-pair verifier and certified nonnegative diagonals required')
        op=json.loads(op_path.read_text());matrix=Path(op['source_matrix']['path']);zero=Path(op['zero_rows']['path'])
        diagonal=Path(op['correction_certificate']['path']);binary=controls/'check_logical_C_principal_pairs'
        expected={str(op_path):a['artifacts'][str(op_path)],str(matrix):op['source_matrix']['sha256'],
                  str(zero):op['zero_rows']['sha256'],str(diagonal):op['correction_certificate']['sha256'],
                  str(binary):c['artifacts'][str(binary)]}
        paths=list(dict.fromkeys([receipt,op_path,control,matrix,zero,diagonal,binary,*map(Path,c['input_sha256']),Path(__file__).resolve()]))
        status('waiting_for_four_CPU_12GiB_pair_check_lease')
        with lease(4,12,deadline):
            status('hashing_full_logical_C_pair_inputs')
            with ThreadPoolExecutor(max_workers=4) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            if any(pins[path]!=h for path,h in expected.items()):raise ValueError('logical C or controlled pair verifier changed')
            save(output/'input_manifest.json',dict(input_sha256=pins))
            cfg,report=output/'config.json',output/'report.json'
            save(cfg,dict(matrix=str(matrix),zero_rows=str(zero),diagonal_certificate=str(diagonal),node_count=op['node_count'],
                 ground_id=0,coefficient_quantum_exponent=op['correction_certificate']['binary_quantum_exponent'],
                 deadline_uptime=deadline,report=str(report)))
            status('checking_full_spatial_C_principal_pairs_exactly')
            execute([binary,cfg],output/'run.log',deadline,12);result=json.loads(report.read_text())
            with ThreadPoolExecutor(max_workers=4) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):raise ValueError('principal pair inputs changed')
            save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (cfg,report,binary)},
                 results=result,scope='necessary two-state principal minors of the complete logical C operator',
                 indefiniteness_proved=result['indefiniteness_proved'],full_matrix_passivity_verified=False,
                 passing_necessary_screen_is_not_PSD_certificate=True,physical_RC_qualified=False,
                 runtime_model_eligible=False,release_qualified=False))
            status('full_logical_C_pair_check_complete',indefiniteness_proved=result['indefiniteness_proved'],
                   negative_principal_pairs=result['negative_principal_pairs'])
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','controls','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();run(a.candidate.resolve(),a.controls.resolve(),a.output.resolve())
