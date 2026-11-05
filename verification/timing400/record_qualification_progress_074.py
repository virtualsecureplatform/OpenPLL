#!/usr/bin/env python3
"""Record completed stock serial build/controls and the actual guarded handoff."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    paths = [Path(__file__).resolve(), owner, base / 'qualification_progress_073.json']
    def proof(name):
        path = base / name / 'assessment.json'
        data = json.loads(path.read_text())
        for filename, value in data.get('artifacts', {}).items():
            assert digest(Path(filename)) == value, filename
        paths.append(path)
        return data
    built = proof('stock_serial_Xyce_001')
    controls = proof('stock_serial_factor_reuse_controls_001')
    assert built['stock_serial_build_completed'] and not built['source_code_modified']
    assert digest(Path(built['binary'])) == built['binary_sha256']
    assert controls['stock_serial_signed_C_finite_R_BSIM_controls_passed']
    assert controls['serial_KLU_repivot_option_modes_checked'] == [1, 0]
    assert all(case['control_equivalence_passed'] for case in controls['cases'])
    for filename, value in controls['input_sha256'].items():
        assert digest(Path(filename)) == value, filename
    current = base / 'DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_002'
    prior = base / 'DCO_domain_nom_tt27_c0_f247_80ns_canonical_ground_001'
    receipt_path = prior / 'stopped_for_controlled_stock_serial_corrected_C_comparison.json'
    receipt = json.loads(receipt_path.read_text())
    assert not process(receipt['pid'])['live']
    assert not receipt['physical_failure_inferred'] and not receipt['budget_restarted']
    decision_path = current / 'prior_throughput_decision.json'
    decision = json.loads(decision_path.read_text())
    assert decision['observation_span_s'] >= 120
    paths.extend([receipt_path, decision_path, current / 'prior_throughput_observations.json',
                  current / 'input_manifest.json', current / 'preparation_manifest.json'])
    previous = json.loads((base / 'qualification_progress_073.json').read_text())
    cases, live = {}, []
    for folder in [current, base / 'DCO_native_zero_wire_R_nom_tt27_c0_f247_80ns_001']:
        status = json.loads((folder / 'status.json').read_text())
        handle = process(status['native_pid'])
        assert handle['live'] and handle['argv'][-1] == str((folder / 'point.cir').resolve())
        live.append(handle)
        wave = folder / 'point.cir.prn'
        rows = []
        if wave.exists():
            text = wave.read_text(); lines = text.splitlines()
            if text and not text.endswith('\n'): lines.pop()
            rows = [line.split() for line in lines[1:] if len(line.split()) == 4 and line.split()[0].isdigit()]
        cases[folder.name] = dict(status=status, native=handle, samples_observed=len(rows),
            last_observed_simulation_time_s=float(rows[-1][1]) if rows else None,
            waveform_observation_is_partial=True)
    work = previous['throughput_followup']
    serial = work['stock_symbolic_fill_and_serial_build']
    serial.update(stock_serial_build_status=json.loads((base / 'stock_serial_Xyce_001/status.json').read_text()),
        stock_serial_build_completed=True, stock_serial_binary_sha256=built['binary_sha256'],
        successful_build_stages_observed=built['stages'],
        serial_factor_reuse_controls_passed=True, serial_control_cases=controls['cases'],
        general_simulator_equivalence_qualified=False,
        prior_full_R_throughput_decision=decision,
        prior_partial_waveform_and_stop_receipt_preserved=True,
        prior_full_R_stop_receipt=str(receipt_path.relative_to(root)),
        actual_serial_corrected_C_case=str(current.relative_to(root)),
        stock_solver_and_C_convention_both_changed=True,
        live_pipeline={current.name: cases[current.name]},
        serial_binary_adopted=False, full_DCO_performance_improvement_demonstrated=False)
    work.update(active_native_transients=cases, stock_symbolic_fill_and_serial_build=serial)
    followup = previous['restored_self_C_operator_followup']
    followup.update(current_native_engines=live, native_points=cases, active_check_statuses=cases,
                    throughput_followup=work)
    previous.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='stock_serial_build_and_native_equivalence_controls_pass_guarded_corrected_C_full_R_handoff_running_with_original_deadline',
        throughput_followup=work, restored_self_C_operator_followup=followup,
        evidence_sha256={str(path.relative_to(root)): digest(path) for path in paths},
        native_analog_jobs=live, native_analog_count=len(live),
        current_native_CAD_and_analog_engines=live,
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    snapshot = base / 'qualification_progress_074.json'
    assert not snapshot.exists(); save(snapshot, previous)
    overview = root / 'build/timing450/implementation_assessment.json'
    state = json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=followup,
        active_400mhz_throughput_followup=work,
        release_qualified=False, selected=False, timing_closure_complete=False)
    save(overview, state)
    print('Progress074: stock serial build and both native controls pass; corrected-C full-R handoff is live, performance/frequency unqualified.')


if __name__ == '__main__':
    main()
