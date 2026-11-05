"""Search a full C voltage witness, then independently verify its energy with exact integers."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import time
from common import save,sha,verify
from compiled_charge import execute
from resources import identity,lease


def run(candidate,search_controls,energy_controls,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,
         cpu_slots=16,memory_GiB=32,computation_wall_limit_s=43200,automatic_identical_retry=False,
         phases=[dict(name='Lanczos_search',cpu_slots=16,memory_GiB=32),dict(name='exact_energy',cpu_slots=1,memory_GiB=12)]))
    def status(state,**more):save(output/'status.json',dict(state=state,release_qualified=False,**more))
    try:
        receipt=candidate/'assessment.json';a=json.loads(receipt.read_text());op_path=Path(a['logical_operator_manifest']);op=json.loads(op_path.read_text())
        if a.get('conservative_C_stored_coefficient_derivative_certified') is not True or a['results']['negative_new_conservative_diagonals']!=0:
            raise ValueError('certified nonnegative-diagonal full C derivative required')
        sc,ec=[p/'assessment.json' for p in (search_controls,energy_controls)]
        s,e=[json.loads(p.read_text()) for p in (sc,ec)]
        if s.get('C_negative_energy_search_controls_pass') is not True or e.get('exact_signed_C_vector_energy_controls_pass') is not True:
            raise ValueError('controlled search and independent exact-energy verifier required')
        verify(s['input_sha256']);verify(e['input_sha256'])
        search=search_controls/'search_C_negative_energy';energy=energy_controls/'certify_C_vector_energy'
        matrix=Path(op['source_matrix']['path']);zero=Path(op['zero_rows']['path']);diagonal=Path(op['correction_certificate']['path'])
        expected={str(op_path):a['artifacts'][str(op_path)],str(matrix):op['source_matrix']['sha256'],str(zero):op['zero_rows']['sha256'],
            str(diagonal):op['correction_certificate']['sha256'],str(search):s['artifacts'][str(search)],str(energy):e['artifacts'][str(energy)]}
        if s['input_sha256'].get(str(energy))!=expected[str(energy)]:raise ValueError('search controls used another exact-energy checker')
        paths=list(dict.fromkeys([receipt,op_path,sc,ec,matrix,zero,diagonal,search,energy,*map(Path,s['input_sha256']),
                                 *map(Path,e['input_sha256']),Path(__file__).resolve()]))
        os.environ.update(OMP_NUM_THREADS='16',OMP_THREAD_LIMIT='16',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        status('waiting_for_sixteen_CPU_32GiB_energy_search_lease')
        with lease(16,32,deadline):
            status('hashing_full_C_energy_search_inputs')
            with ThreadPoolExecutor(max_workers=16) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            if any(pins[p]!=h for p,h in expected.items()):raise ValueError('energy search inputs changed')
            save(output/'input_manifest.json',dict(input_sha256=pins))
            base=dict(matrix=str(matrix),zero_rows=str(zero),node_count=op['node_count'],
                 coefficient_quantum_exponent=op['correction_certificate']['binary_quantum_exponent'],deadline_uptime=deadline)
            vector=output/'vector.bin';cfg,report=output/'search.json',output/'search.report.json'
            save(cfg,dict(base,diagonal_certificate=str(diagonal),threads=16,iterations=256,maximum_adjacency_bytes=28*1024**3,
                 vector=str(vector),progress=str(output/'progress.json'),report=str(report)))
            status('searching_full_C_negative_energy_by_two_pass_Lanczos')
            execute([search,cfg],output/'search.log',deadline,32);vector_sha=sha(vector)
        status('waiting_for_one_CPU_12GiB_exact_energy_lease')
        with lease(1,12,deadline):
            if sha(vector)!=vector_sha:raise ValueError('candidate vector changed between phases')
            ecfg,ereport=output/'energy.json',output/'energy.report.json';save(ecfg,dict(base,vector=str(vector),report=str(ereport)))
            status('independently_verifying_full_vector_energy_exactly')
            execute([energy,ecfg],output/'energy.log',deadline,12);result=json.loads(ereport.read_text())
            verify(pins)
            if sha(vector)!=vector_sha:raise ValueError('candidate voltage changed during exact verification')
            save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (vector,cfg,report,ecfg,ereport)},
                 search=json.loads(report.read_text()),results=result,exact_full_operator_vector_energy_verified=True,
                 indefiniteness_proved=result['indefiniteness_proved'],nonnegative_energy_does_not_prove_PSD=True,
                 full_matrix_passivity_verified=False,physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
            status('full_C_candidate_energy_audit_complete',indefiniteness_proved=result['indefiniteness_proved'])
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','search-controls','energy-controls','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();run(a.candidate.resolve(),a.search_controls.resolve(),a.energy_controls.resolve(),a.output.resolve())
