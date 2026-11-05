#!/usr/bin/env python3
"""Record completed stock build, retained failed controls, and changed scheduling."""
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
    build = base / 'stock_threaded_Xyce_002/assessment.json'
    proof = json.loads(build.read_text())
    assert proof['stock_threaded_build_completed'] and not proof['source_code_modified']
    failure = base / 'stock_threaded_solver_controls_002/failure_assessment.json'
    assert json.loads(failure.read_text())['native_eight_thread_nonzero_exit_observed_in_runner_assertion']
    old_path = base / 'qualification_progress_080.json'
    result = json.loads(old_path.read_text())
    work = result['throughput_followup']
    threaded = work['threaded_solver_followup']
    threaded.update(stock_threaded_build_completed=True, completed_build_proof=str(build.relative_to(root)),
        tiny_eight_thread_control_failed=True, retained_failure_proof=str(failure.relative_to(root)),
        larger_passive_wait_mesh_control_timed_out=True, tiny_failure_cause_proven=False,
        active_wait_control_directory='stock_threaded_active_wait_controls_001',
        full_DCO_performance_improvement_demonstrated=False)
    observations, handles, inputs = {}, [], [Path(__file__), owner, old_path, build, failure]
    for name in ['stock_threaded_Xyce_002', 'stock_threaded_solver_controls_002',
                 'stock_threaded_mesh_controls_001', 'stock_threaded_active_wait_controls_001',
                 'DCO_domain_nom_tt27_c0_f247_80ns_stock_threaded_001',
                 'DCO_domain_nom_tt27_c0_f247_80ns_stock_threaded_002',
                 'DCO_ideal_wire_startup_prefix_comparison_001',
                 'DCO_ideal_wire_numeric_window_comparison_001']:
        folder = base / name
        status = json.loads((folder / 'status.json').read_text())
        observations[name] = dict(status=status, runner=process(status['runner_pid']))
        inputs.append(folder / 'owner.json')
        if 'native_pid' in status:
            native = process(status['native_pid'])
            observations[name]['native'] = native
            if native['live']: handles.append(native)
    threaded['pipeline'] = observations
    cases = {}
    for name in ['DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_002',
                 'DCO_native_zero_wire_R_nom_tt27_c0_f247_25ns_numeric_002']:
        folder = base / name
        status = json.loads((folder / 'status.json').read_text())
        native = process(status['native_pid'])
        if native['live']: handles.append(native)
        text = (folder / 'point.cir.prn').read_text()
        lines = text.splitlines()
        if text and not text.endswith('\n'): lines.pop()
        rows = [line.split() for line in lines[1:] if len(line.split()) == 4 and line.split()[0].isdigit()]
        cases[name] = dict(status=status, native=native, samples_observed=len(rows),
            last_observed_simulation_time_s=float(rows[-1][1]), waveform_observation_is_partial=True)
    work['active_native_transients'] = cases
    followup = result['restored_self_C_operator_followup']
    followup.update(current_native_engines=handles, native_points=cases, active_check_statuses=cases,
                    throughput_followup=work)
    inputs.extend([Path(__file__).with_name(name) for name in
        ['audit_DCO_startup_comparison.py', 'check_stock_threaded_mesh_control.py',
         'check_stock_threaded_active_wait_control.py', 'run_DCO_stock_threaded_point_v2.py']])
    result.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='stock_OpenMP_ShyLU_build_completed_tiny_control_failed_mesh_passive_wait_timeout_active_wait_control_queued_guarded_handoff',
        throughput_followup=work, restored_self_C_operator_followup=followup,
        evidence_sha256={str(path.resolve()): digest(path) for path in inputs},
        native_analog_jobs=handles, native_analog_count=len(handles),
        current_native_CAD_and_analog_engines=handles,
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    snapshot = base / 'qualification_progress_081.json'; assert not snapshot.exists()
    save(snapshot, result)
    overview = root / 'build/timing450/implementation_assessment.json'
    state = json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=followup,
        active_400mhz_throughput_followup=work, release_qualified=False,
        selected=False, timing_closure_complete=False)
    save(overview, state)
    print('Progress081: stock threaded build complete; control failures retained; no release gate closed.')


if __name__ == '__main__':
    main()
