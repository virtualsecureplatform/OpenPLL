"""Review completed full RC evidence without rerunning or altering native cases."""
import json, re, time
from pathlib import Path
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease


def run():
    base = ROOT / 'build/signoff400'
    names = ['selected_reference_alias_full_RC_audit_1766',
             'selected_reference_alias_native_RC_model_1768',
             'selected_zero_C_backend_model_1810',
             'selected_zero_C_backend_CSC_assessment_1814',
             'selected_nodeset_release_control_1824',
             'selected_seeded_full_RC_DC_1825']
    pins, records = {}, []
    with lease(1, 2, time.clock_gettime(time.CLOCK_BOOTTIME) + 1200):
        for name in names:
            receipt = base / name / 'assessment.json'
            record = json.loads(receipt.read_text())
            verify(record['input_sha256']); verify(record['artifacts'])
            pins[str(receipt)] = sha(receipt); records.append(record)
        audit, literal, adapter, matrix, nodeset, dc = records
        if len(audit['checks']) != 13 or not all(audit['checks'].values()):
            raise ValueError('all thirteen full physical export gates required')
        if not literal['all_RC_endpoints_and_literal_values_preserved']:
            raise ValueError('literal full RC fidelity required')
        for key in ['exact_source_reconstruction_verified', 'all_other_bytes_unchanged',
                    'signed_nonzero_C_unchanged', 'zero_R_preserved']:
            if not adapter[key]: raise ValueError(key)
        report_path = base / names[3] / 'report.json'
        report = json.loads(report_path.read_text())
        if report['rows'] != 923123 or report['nonzero_rows']['zero'] or report['nonzero_columns']['zero']:
            raise ValueError('full native matrix must have no empty equations')
        if not nodeset['nodeset_released_before_final_DC'] or not nodeset['hierarchical_nodeset_accepted']:
            raise ValueError('released hierarchical initial guess required')
        folder = base / names[-1]
        process = json.loads((folder / 'native.process.json').read_text())
        if identity(process['pid']) == process['birth'] or not dc['normal_native_exit']:
            raise ValueError('normally completed absent worker required')
        log = (folder / 'native.log').read_text()
        def count(label):
            match = re.findall(re.escape(label) + r':\s*(\d+)', log)
            if len(match) != 1: raise ValueError(label)
            return int(match[0])
        summary = {label: count(label) for label in [
            'Number Successful Steps Taken', 'Number Failed Steps Attempted',
            'Number Linear Solves', 'Number Failed Linear Solves',
            'Number Nonlinear Convergence Failures']}
        if summary['Number Successful Steps Taken'] != 1 or summary['Number Failed Steps Attempted'] or summary['Number Nonlinear Convergence Failures']:
            raise ValueError('completed converged native DC step required')
        adapter_summary = re.findall(r'OpenPLL UMFPACK adapter: calls=(\d+) numeric=(\d+) symbolic=(\d+) failures=(\d+)', log)
        if len(adapter_summary) != 1: raise ValueError('one adapter summary required')
        calls, numeric, symbolic, failures = map(int, adapter_summary[0])
        if calls != summary['Number Linear Solves'] or failures != summary['Number Failed Linear Solves']:
            raise ValueError('native and adapter failure accounting differs')
        if '***** End of Xyce(TM) Simulation' not in log:
            raise ValueError('normal simulation footer required')
        pins[str(Path(__file__).resolve())] = sha(Path(__file__).resolve())
        verify(pins)
        out = base / 'selected_completed_RC_review_1826'; out.mkdir(exist_ok=False)
        save(out / 'assessment.json', dict(input_sha256=pins, artifacts={},
            physical_export_checks=audit['checks'],
            full_physical_RC_export_verified=True,
            reversible_zero_C_backend_adapter_verified=True,
            full_native_matrix_empty_equations=0,
            completed_full_RC_reset_DC_verified=True,
            native_summary=summary, recovered_linear_failures=failures,
            native_initial_guess_release_control_verified=True,
            monitored_ports=10, all_internal_solution_values_independently_checked=False,
            transient_correlation_qualified=False, frequency_qualified=False,
            release_ready=False,
            qualification_scope='physical RC export fidelity and completed reset DC only',
            remaining_review='Determine required transient backend correlation before final goal completion'))
        print(out / 'assessment.json')


if __name__ == '__main__': run()
