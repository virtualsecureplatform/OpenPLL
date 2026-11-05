"""Certify a logical conservative C derivative without modifying its stored source."""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time

from common import ROOT, save, sha, verify
from compiled_charge import execute
from resources import identity, lease


def run(output, controls):
    output.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    scratch = Path(tempfile.mkdtemp(prefix='openpll-conservative-C-', dir='/tmp'))
    (output/'native').symlink_to(scratch, target_is_directory=True)
    save(output/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid()),
         deadline_uptime=deadline, cpu_slots=8, memory_GiB=32, automatic_identical_retry=False,
         retained_local_scratch=str(scratch)))
    def status(state, **extra):
        save(output/'status.json', dict(state=state, release_qualified=False, **extra))
    try:
        control_receipt = controls/'assessment.json'
        control = json.loads(control_receipt.read_text())
        for key in ('independent_exact_C_auditor_controls_pass',
                    'conservative_C_coefficient_certificate_controls_pass', 'signed_C_edge_operator_controls_pass'):
            if control.get(key) is not True:
                raise ValueError('missing independent control: '+key)
        verify(control['input_sha256'])
        binaries = [controls/name for name in ('certify_conservative_C', 'evaluate_C_edge_operator')]
        for path in binaries:
            if sha(path) != control['artifacts'][str(path)]:
                raise ValueError('controlled binary changed')
        transform = ROOT/'build/signoff400/startup_timing_spatial_zero_R_followup_003/assessment.json'
        a = json.loads(transform.read_text())
        matrix = Path(a['constrained_matrix'])
        original = ROOT/'build/signoff400/startup_timing_exact_C_residual_certificate_001/assessment.json'
        before = json.loads(original.read_text())
        paths = [control_receipt, transform, original, matrix, *binaries, Path(__file__).resolve()]
        status('waiting_for_shared_resources')
        with lease(8, 32, deadline):
            pins = {str(p): sha(p) for p in paths}
            if pins[str(matrix)] != a['artifacts'][str(matrix)] or pins[str(matrix)] != before['input_sha256'][str(matrix)]:
                raise ValueError('matrix does not match retained exact certificate')
            save(output/'input_manifest.json', dict(input_sha256=pins))
            cfg, report, rows = output/'certificate.json', output/'certificate.report.json', scratch/'rows.jsonl'
            save(cfg, dict(matrix=str(matrix), node_count=a['transform_summary']['constrained_voltage_nodes'],
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
            save(evaluation, dict(matrix=str(matrix), node_count=found['node_count'],
                 maximum_adjacency_bytes=28*1024**3, threads=[1, 4, 8], vector_mode='vertex_pattern',
                 deadline_uptime=deadline, report=str(evaluated)))
            status('checking_full_signed_C_vector_at_one_four_eight_threads')
            execute([binaries[1], evaluation], output/'evaluation.log', deadline, 32)
            verify(pins)
            operator = output/'operator.json'
            save(operator, dict(schema_version=1, kind='signed_incidence_capacitance',
                 source_matrix=dict(path=str(matrix), sha256=pins[str(matrix)]),
                 voltage_namespace_receipt=dict(path=str(transform), sha256=pins[str(transform)]),
                 node_count=found['node_count'], raw_coefficient_to_farad='1e-18',
                 definition='(Cx)[i] = sum(j != i, -stored_C[i,j] * (x[i] - x[j]))',
                 diagonal_definition='exact negative sum of all stored offdiagonal coefficients in the row',
                 correction_certificate=dict(path=str(rows), sha256=sha(rows),
                      binary_quantum_exponent=found['common_binary_quantum_exponent']),
                 constant_nullspace_exact=True, offdiagonal_coefficients_unchanged=True,
                 all_diagonal_corrections_within_existing_coefficient_tolerance=True,
                 upstream_partition_of_unity_and_integration_certified=False,
                 full_matrix_passivity_verified=False, native_solver_integrated=False,
                 runtime_model_eligible=False, physical_RC_qualified=False, release_qualified=False))
            artifacts = {str(p): sha(p) for p in (cfg, report, rows, evaluation, evaluated, operator)}
            save(output/'assessment.json', dict(input_sha256=pins, artifacts=artifacts, results=found,
                 evaluation=json.loads(evaluated.read_text()), logical_operator_manifest=str(operator),
                 conservative_C_stored_coefficient_derivative_certified=True,
                 full_matrix_passivity_verified=False, upstream_integration_error_certified=False,
                 physical_RC_qualified=False, runtime_model_eligible=False, release_qualified=False))
            status('conservative_C_derivative_certified_physical_gates_open')
    except BaseException as error:
        status('stopped_without_promotion', reason=repr(error))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--controls', required=True, type=Path)
    args = parser.parse_args()
    run(args.output.resolve(), args.controls.resolve())
