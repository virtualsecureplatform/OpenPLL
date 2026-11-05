"""Certify a logical conservative C derivative without modifying its stored source."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import struct
from pathlib import Path
import tempfile
import time

from common import ROOT, save, sha, verify
from compiled_charge import execute
from resources import identity, lease


def run(output, controls, zero_proof):
    output.mkdir(parents=True, exist_ok=False)
    receipt_path=zero_proof/'assessment.json'
    producer=None
    if not receipt_path.exists():
        producer=json.loads((zero_proof/'owner.json').read_text())
        wait_deadline=producer['deadline_uptime']+60
    else:wait_deadline=time.clock_gettime(time.CLOCK_BOOTTIME)
    deadline = wait_deadline+43200
    scratch = Path(tempfile.mkdtemp(prefix='openpll-conservative-C-', dir='/tmp'))
    (output/'native').symlink_to(scratch, target_is_directory=True)
    save(output/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid()),
         deadline_uptime=deadline, cpu_slots=8, memory_GiB=32, automatic_identical_retry=False,
         retained_local_scratch=str(scratch)))
    def status(state, **extra):
        save(output/'status.json', dict(state=state, release_qualified=False, **extra))
    try:
        while not receipt_path.exists():
            if identity(producer['pid'])!=producer['birth'] or time.clock_gettime(time.CLOCK_BOOTTIME)>=wait_deadline:
                raise RuntimeError('exact source zero-row proof producer terminal without complete certificate')
            status('waiting_for_exact_source_zero_row_proof',producer_pid=producer['pid']);time.sleep(2)
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
        control_receipt = controls/'assessment.json' 
        control = json.loads(control_receipt.read_text())
        for key in ('source_zero_row_C_operator_controls_pass',):
            if control.get(key) is not True:
                raise ValueError('missing independent control: '+key)
        verify(control['input_sha256'])
        binaries = [controls/name for name in ('certify_conservative_C_v2', 'evaluate_C_edge_operator_v2')]
        for path in binaries:
            if sha(path) != control['artifacts'][str(path)]:
                raise ValueError('controlled binary changed')
        transform = ROOT/'build/signoff400/startup_timing_spatial_zero_R_followup_003/assessment.json'
        a = json.loads(transform.read_text())
        matrix = Path(a['constrained_matrix'])
        original = ROOT/'build/signoff400/startup_timing_exact_C_residual_certificate_001/assessment.json'
        before = json.loads(original.read_text())
        zero_proof = receipt_path
        zp = json.loads(zero_proof.read_text())
        if zp.get('source_level_zero_row_certificate_complete') is not True:
            raise ValueError('exact complete source-level zero-row proof required')
        zero_config = zero_proof.parent/'config.json'
        zero_report = zero_proof.parent/'report.json'
        for path in (zero_config, zero_report):
            if sha(path) != zp['artifacts'][str(path)]: raise ValueError('zero-row proof artifact changed')
        zcfg=json.loads(zero_config.read_text());zr=json.loads(zero_report.read_text())
        compact=Path(zcfg['voltage_map'])
        if zp['input_sha256'][str(compact)] != a['input_sha256'][str(compact)]:
            raise ValueError('zero-row proof uses another zero-R namespace')
        projected=ROOT/'build/signoff400/startup_timing_full_spatial_projection_002/assessment.json'
        if zp['input_sha256'][str(projected)] != a['input_sha256'][str(projected)]:
            raise ValueError('zero-row proof uses another projection')
        proof_targets=Path(zcfg['targets']);zt=json.loads(proof_targets.read_text())
        wanted={row['row'] for row in zt['negative_nodes']}
        rows_to_zero=[row['row'] for row in zr['rows']]
        if (not zr['all_target_rows_exactly_zero'] or len(set(rows_to_zero))!=len(rows_to_zero)
                or set(rows_to_zero)!=wanted or not all(row['entire_row_exactly_zero'] is True for row in zr['rows'])):
            raise ValueError('incomplete exact zero-row coverage')
        mask=output/'zero_rows.bin';n=a['transform_summary']['constrained_voltage_nodes'];bits=bytearray(n)
        for row in rows_to_zero:
            if type(row) is not int or not 0<row<n:raise ValueError('zero row outside preserved reference namespace')
            bits[row]=1
        mask.write_bytes(b'CZEROR01'+struct.pack('<Q',n)+bits)
        paths = list(dict.fromkeys([control_receipt, transform, original, matrix, *binaries,
             zero_proof,zero_config,zero_report,proof_targets,compact,mask,*map(Path,zp['input_sha256']),Path(__file__).resolve()]))
        status('waiting_for_shared_resources')
        with lease(8, 32, deadline):
            with ThreadPoolExecutor(max_workers=8) as pool:
                pins = dict(zip(map(str,paths),pool.map(sha,paths)))
            if any(pins[path]!=digest for path,digest in zp['input_sha256'].items()):raise ValueError('symbolic row proof inputs changed')
            if pins[str(matrix)] != a['artifacts'][str(matrix)] or pins[str(matrix)] != before['input_sha256'][str(matrix)]:
                raise ValueError('matrix does not match retained exact certificate')
            save(output/'input_manifest.json', dict(input_sha256=pins))
            cfg, report, rows = output/'certificate.json', output/'certificate.report.json', scratch/'rows.jsonl'
            save(cfg, dict(matrix=str(matrix), zero_rows=str(mask), node_count=a['transform_summary']['constrained_voltage_nodes'],
                           deadline_uptime=deadline, row_certificate=str(rows), report=str(report)))
            status('certifying_every_conservative_diagonal_exactly')
            execute([binaries[0], cfg], output/'certificate.log', deadline, 8)
            found = json.loads(report.read_text())
            previous = before['results']
            if found['original_rows_outside_1e12_gauge_screen'] != previous['rows_outside_existing_1e12_gauge_screen_exact']:
                raise ValueError('independent original gauge count differs')
            if found['common_binary_quantum_exponent'] != previous['common_binary_quantum_exponent']:
                raise ValueError('independent original binary quantum differs')
            if not found['all_corrections_within_existing_coefficient_tolerance']:
                raise ValueError('logical diagonal correction exceeds unchanged coefficient tolerances')
            evaluation = output/'evaluation.json'
            evaluated = output/'evaluation.report.json'
            save(evaluation, dict(matrix=str(matrix), zero_rows=str(mask), node_count=found['node_count'],
                 maximum_adjacency_bytes=28*1024**3, threads=[1, 4, 8], vector_mode='vertex_pattern',
                 deadline_uptime=deadline, report=str(evaluated)))
            status('checking_full_signed_C_vector_at_one_four_eight_threads')
            execute([binaries[1], evaluation], output/'evaluation.log', deadline, 32)
            verify(pins)
            operator = output/'operator.json'
            save(operator, dict(schema_version=1, kind='signed_incidence_capacitance_with_source_proven_zero_rows',
                 source_matrix=dict(path=str(matrix), sha256=pins[str(matrix)]),
                 voltage_namespace_receipt=dict(path=str(transform), sha256=pins[str(transform)]),
                 node_count=found['node_count'], raw_coefficient_to_farad='1e-18',
                 definition='(Cx)[i] = sum(j != i and neither endpoint is a source-proven zero row, -stored_C[i,j] * (x[i] - x[j]))',
                 zero_rows=dict(path=str(mask),sha256=sha(mask),count=len(rows_to_zero)),
                 source_zero_row_proof=dict(path=str(zero_proof),sha256=sha(zero_proof)),
                 all_voltage_states_retained=True,conductance_operator_unchanged=True,
                 diagonal_definition='exact negative sum of retained offdiagonals; source-proven zero rows have no incident capacitive edges',
                 correction_certificate=dict(path=str(rows), sha256=sha(rows),
                      binary_quantum_exponent=found['common_binary_quantum_exponent']),
                 constant_nullspace_exact=True, offdiagonals_unchanged_except_source_proven_zero_rows=True,
                 all_diagonal_corrections_within_existing_coefficient_tolerance=True,
                 upstream_partition_of_unity_and_integration_certified=False,
                 full_matrix_passivity_verified=False, native_solver_integrated=False,
                 runtime_model_eligible=False, physical_RC_qualified=False, release_qualified=False))
            artifacts = {str(p): sha(p) for p in (cfg, report, rows, evaluation, evaluated, operator, mask)}
            save(output/'assessment.json', dict(input_sha256=pins, artifacts=artifacts, results=found,
                 evaluation=json.loads(evaluated.read_text()), logical_operator_manifest=str(operator),
                 conservative_C_stored_coefficient_derivative_certified=True,source_proven_zero_C_rows_applied=len(rows_to_zero),
                 full_matrix_passivity_verified=False, upstream_integration_error_certified=False,
                 physical_RC_qualified=False, runtime_model_eligible=False, release_qualified=False))
            status('source_zero_row_C_derivative_certified_physical_gates_open',negative_diagonal_rows=found['negative_new_conservative_diagonals'])
    except BaseException as error:
        status('stopped_without_promotion', reason=repr(error))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--controls', required=True, type=Path)
    parser.add_argument('--zero-proof',required=True,type=Path)
    args = parser.parse_args()
    run(args.output.resolve(), args.controls.resolve(), args.zero_proof.resolve())
