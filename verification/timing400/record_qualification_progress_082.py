#!/usr/bin/env python3
"""Record passing active-wait controls and the guarded full-circuit handoff."""
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
    previous_path = base / 'qualification_progress_081.json'
    result = json.loads(previous_path.read_text())
    controls = base / 'stock_threaded_active_wait_controls_001/assessment.json'
    proof = json.loads(controls.read_text())
    assert proof['connected_mesh_threaded_controls_passed'] and proof['OpenMP_wait_policy'] == 'ACTIVE'
    prior = base / 'DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_002'
    receipt = prior / 'stopped_for_controlled_stock_threaded_solver_comparison.json'
    stopped = json.loads(receipt.read_text())
    assert stopped['original_deadline_uptime'] == deadline and not process(stopped['pid'])['live']
    threaded = base / 'DCO_domain_nom_tt27_c0_f247_80ns_stock_threaded_002'
    manifest = threaded / 'input_manifest.json'
    assert json.loads(manifest.read_text())['physical_R_and_device_cards_unchanged']
    work = result['throughput_followup']
    follow = work['threaded_solver_followup']
    follow.update(active_wait_connected_mesh_controls_passed=True,
        active_wait_controls_proof=str(controls.relative_to(root)), control_cases=proof['cases'],
        guarded_threaded_handoff_completed=True, full_finite_R_threaded_directory=threaded.name,
        prior_serial_stop_receipt=str(receipt.relative_to(root)),
        full_DCO_performance_improvement_demonstrated=False)
    for name, entry in follow['pipeline'].items():
        folder = base / name
        state = json.loads((folder / 'status.json').read_text())
        entry.update(status=state, runner=process(state['runner_pid']))
        if 'native_pid' in state: entry['native'] = process(state['native_pid'])
    cases, handles = {}, []
    for folder in [threaded, base / 'DCO_native_zero_wire_R_nom_tt27_c0_f247_25ns_numeric_002']:
        state = json.loads((folder / 'status.json').read_text())
        native = process(state['native_pid'])
        assert native['live'] and native['argv'][-1] == str((folder / 'point.cir').resolve())
        handles.append(native)
        wave = folder / 'point.cir.prn'; rows = []
        if wave.exists():
            content = wave.read_text(); lines = content.splitlines()
            if content and not content.endswith('\n'): lines.pop()
            rows = [line.split() for line in lines[1:] if len(line.split()) == 4 and line.split()[0].isdigit()]
        cases[folder.name] = dict(status=state, native=native, samples_observed=len(rows),
            last_observed_simulation_time_s=float(rows[-1][1]) if rows else None,
            waveform_observation_is_partial=True)
    work['active_native_transients'] = cases
    nested = result['restored_self_C_operator_followup']
    nested.update(current_native_engines=handles, native_points=cases, active_check_statuses=cases,
                  throughput_followup=work)
    paths = [Path(__file__), owner, previous_path, controls, receipt, manifest,
        threaded / 'prior_throughput_decision.json',
        Path(__file__).with_name('run_DCO_stock_threaded_point_v2.py')]
    result.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='active_wait_mesh_controls_passed_guarded_byte_identical_full_R_threaded_handoff_started',
        throughput_followup=work, restored_self_C_operator_followup=nested,
        evidence_sha256={str(path.resolve()): digest(path) for path in paths},
        native_analog_jobs=handles, native_analog_count=len(handles),
        current_native_CAD_and_analog_engines=handles,
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    snapshot = base / 'qualification_progress_082.json'; assert not snapshot.exists()
    save(snapshot, result)
    overview = root / 'build/timing450/implementation_assessment.json'
    state = json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=nested,
        active_400mhz_throughput_followup=work, release_qualified=False,
        selected=False, timing_closure_complete=False)
    save(overview, state)
    print('Progress082: control equivalence passed; full-R threaded point started; all release gates open.')


if __name__ == '__main__':
    main()
