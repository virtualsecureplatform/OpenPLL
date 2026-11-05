#!/usr/bin/env python3
"""Record corrected OpenMP configuration and verified breakpoint grid change."""
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
    previous_path = base / 'qualification_progress_078.json'
    previous = json.loads(previous_path.read_text())
    failed = base / 'DCO_native_zero_wire_R_nom_tt27_c0_f247_25ns_numeric_001'
    fixed = base / 'DCO_native_zero_wire_R_nom_tt27_c0_f247_25ns_numeric_002'
    old = json.loads((failed / 'assessment.json').read_text())
    assert old['native_exit'] == 1 and old['metrics'] is None
    for filename, value in old['artifacts'].items(): assert digest(Path(filename)) == value, filename
    history = (failed / 'native.log').read_text()
    assert '1.464e-22' in history and '2.928e-22' in history and 'Time step too small' in history
    original = (failed / 'point.cir').read_text()
    assert original.replace('.tran 20p 25n 0 0.5p', '.tran 20p 25n 0 0.47p') == (fixed / 'point.cir').read_text()
    control_path = base / 'breakpoint_grid_controls_001/assessment.json'
    control = json.loads(control_path.read_text())
    assert control['noncommensurate_grid_matches_analytic_RC']
    for filename, value in {**control['input_sha256'], **control['artifacts']}.items():
        assert digest(Path(filename)) == value, filename
    paths = [Path(__file__).resolve(), owner, previous_path, failed / 'assessment.json',
        failed / 'native.log', failed / 'point.cir', fixed / 'point.cir', control_path]
    pipeline = {}
    for name in ['stock_threaded_Xyce_002', 'stock_threaded_solver_controls_002']:
        folder = base / name
        status = json.loads((folder / 'status.json').read_text())
        runner = process(status['runner_pid'])
        assert runner['live']
        pipeline[name] = dict(status=status, runner=runner)
        paths.append(folder / 'owner.json')
    new_build = base / 'stock_threaded_Xyce_002/input_manifest.json'
    build_params = json.loads(new_build.read_text())
    assert 'Trilinos_ENABLE_OpenMP=ON' in build_params['corrected_flags']
    assert build_params['resumed_after_configuration_failure']
    paths.append(new_build)
    work = previous['throughput_followup']
    work['threaded_solver_followup'].update(pipeline=pipeline,
        initial_build_configuration_failed=True, required_global_OpenMP_flag_corrected=True,
        successful_dependency_builds_reused=True, original_deadline_uptime=deadline,
        native_controls_passed=False, budget_restarted=False)
    work['breakpoint_grid_failure_followup'] = dict(original_native_exit=1,
        original_failure_time_s=5e-9, observed_roundoff_step_s=1.464e-22,
        next_failed_step_s=2.928e-22, hardware_frequency_result_produced=False,
        analytic_RC_controls=control['cases'],
        corrected_maximum_step_ps=.47, preceding_maximum_step_ps=.5,
        same_reset_timing_and_tight_tolerances=True, sole_deck_change_is_maximum_step=True,
        diagnostic_directory=str(fixed.relative_to(root)),
        DCO_reset_breakpoint_recovery_demonstrated=False, release_qualified=False, adopted=False)
    cases, live = {}, []
    for folder in [base / 'DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_002', fixed]:
        status = json.loads((folder / 'status.json').read_text())
        native = process(status['native_pid'])
        assert native['live'] and native['argv'][-1] == str((folder / 'point.cir').resolve())
        live.append(native)
        text = (folder / 'point.cir.prn').read_text(); lines = text.splitlines()
        if text and not text.endswith('\n'): lines.pop()
        rows = [line.split() for line in lines[1:] if len(line.split()) == 4 and line.split()[0].isdigit()]
        cases[folder.name] = dict(status=status, native=native, samples_observed=len(rows),
            last_observed_simulation_time_s=float(rows[-1][1]) if rows else None,
            waveform_observation_is_partial=True)
    work['active_native_transients'] = cases
    followup = previous['restored_self_C_operator_followup']
    followup.update(current_native_engines=live, native_points=cases, active_check_statuses=cases,
                    throughput_followup=work)
    previous.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='global_OpenMP_build_configuration_corrected_breakpoint_roundoff_reproduced_analytic_control_validates_0p47ps_grid_live_DCO_diagnostic_pending',
        throughput_followup=work, restored_self_C_operator_followup=followup,
        evidence_sha256={str(path): digest(path) for path in paths},
        native_analog_jobs=live, native_analog_count=len(live), current_native_CAD_and_analog_engines=live,
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    snapshot = base / 'qualification_progress_079.json'
    assert not snapshot.exists(); save(snapshot, previous)
    overview = root / 'build/timing450/implementation_assessment.json'
    state = json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=followup, active_400mhz_throughput_followup=work,
        release_qualified=False, selected=False, timing_closure_complete=False)
    save(overview, state)
    print('Progress079: OpenMP build configuration corrected; breakpoint grid change validated analytically; both native DCO cases live, release open.')


if __name__ == '__main__': main()
