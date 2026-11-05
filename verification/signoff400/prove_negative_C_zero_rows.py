"""Prove source-level zero rows by exact cancellation of rational/atan/log1p terms."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import identity,lease


def run(output,controls):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,
         cpu_slots=16,memory_GiB=32,automatic_identical_retry=False))
    def status(state,**more):save(output/'status.json',dict(state=state,release_qualified=False,**more))
    try:
        control=controls/'assessment.json';c=json.loads(control.read_text());verify(c['input_sha256'])
        binary=controls/'prove_selected_C_zero_rows'
        if not c['exact_symbolic_C_zero_row_controls_pass'] or sha(binary)!=c['artifacts'][str(binary)]:
            raise ValueError('controlled exact symbolic row evaluator required')
        base=ROOT/'build/signoff400';previous=base/'startup_timing_analytic_negative_C_diagonals_001/assessment.json'
        a=json.loads(previous.read_text())
        if not a['complete_selected_analytic_diagonal_enclosures']:raise ValueError('complete selected-source integration required')
        prepared=base/'startup_timing_analytic_negative_C_diagonals_001/128.json'
        if sha(prepared)!=a['artifacts'][str(prepared)]:raise ValueError('prepared selected case changed')
        config=json.loads(prepared.read_text());targets_receipt=base/'startup_timing_negative_C_fields_002/assessment.json'
        t=json.loads(targets_receipt.read_text());compact=base/'startup_timing_zero_R_voltage_map_002/voltage_map.bin'
        expected=dict(a['input_sha256']);expected[str(compact)]=t['input_sha256'][str(compact)]
        paths=list(dict.fromkeys([control,binary,previous,prepared,targets_receipt,compact,
                                 *map(Path,expected),Path(__file__).resolve()]))
        os.environ.update(OMP_NUM_THREADS='16',OMP_THREAD_LIMIT='16',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        status('waiting_for_sixteen_CPU_32GiB_symbolic_proof_lease')
        with lease(16,32,deadline):
            status('hashing_exact_symbolic_support_and_source_lineage')
            with ThreadPoolExecutor(max_workers=16) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            if any(pins[path]!=digest for path,digest in expected.items()):raise ValueError('symbolic row proof source changed')
            save(output/'input_manifest.json',dict(input_sha256=pins))
            cfg,report=output/'config.json',output/'report.json'
            config.update(deadline_uptime=deadline,report=str(report),voltage_map=str(compact),threads=16)
            config['geometry']['deadline_uptime']=deadline;save(cfg,config)
            status('proving_complete_target_rows_with_exact_transcendental_atom_cancellation')
            execute([binary,cfg],output/'proof.log',deadline,32);result=json.loads(report.read_text())
            with ThreadPoolExecutor(max_workers=16) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):raise ValueError('symbolic proof inputs changed')
            save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(path):sha(path) for path in (cfg,report)},
                 results=result,complete_target_C_symbolic_row_expressions_assembled=True,
                 all_target_C_rows_exactly_zero=result['all_target_rows_exactly_zero'],
                 source_level_zero_row_certificate_complete=result['all_target_rows_exactly_zero'],
                 numerical_coefficient_threshold_used=False,matrix_modified=False,
                 full_matrix_passivity_verified=False,physical_RC_qualified=False,release_qualified=False))
            status('exact_symbolic_target_row_proof_complete',all_target_rows_exactly_zero=result['all_target_rows_exactly_zero'],
                   nonzero_symbolic_coefficients=result['nonzero_symbolic_coefficients'])
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--controls',required=True,type=Path);a=p.parse_args();run(a.output.resolve(),a.controls.resolve())
