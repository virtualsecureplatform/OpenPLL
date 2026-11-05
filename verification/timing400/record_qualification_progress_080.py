#!/usr/bin/env python3
"""Retain a live reset-crossing prefix and record guarded solver preparation."""
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
    refined = base / 'DCO_native_zero_wire_R_nom_tt27_c0_f247_25ns_numeric_002'
    source_status = json.loads((refined / 'status.json').read_text())
    handle = process(source_status['native_pid'])
    assert handle['live'] and handle['argv'][-1] == str((refined / 'point.cir').resolve())
    text = (refined / 'point.cir.prn').read_text()
    if not text.endswith('\n'): text = text[:text.rfind('\n') + 1]
    lines = text.splitlines()
    assert lines[0].split() == ['Index', 'TIME', 'V(PLLOUT)', 'I(VVPWR)']
    rows = [line.split() for line in lines[1:]]
    assert all(len(row) == 4 and int(row[0]) == index for index, row in enumerate(rows))
    times = [float(row[1]) for row in rows]
    assert all(a < b for a, b in zip(times, times[1:])) and times[-1] > 5.05e-9
    minimum = min(b - a for a, b in zip(times, times[1:]) if 4.9e-9 <= b <= 5.05e-9)
    out = base / 'DCO_numeric_reset_grid_recovery_001'; out.mkdir(exist_ok=False)
    prefix = out / 'retained_live_prefix.prn'; prefix.write_text(text)
    source_manifest = refined / 'input_manifest.json'
    inputs = [Path(__file__).resolve(), owner, source_manifest, refined / 'point.cir',
        base / 'breakpoint_grid_controls_001/assessment.json']
    save(out / 'assessment.json', dict(accepted_native_steps_past_reset_edge_observed=True,
        observed_utc=datetime.now(timezone.utc).isoformat(), native_identity=handle,
        prefix_samples=len(rows), prefix_last_time_s=times[-1],
        minimum_step_around_reset_s=minimum,
        roundoff_sized_steps_below1attosecond_absent=minimum > 1e-18,
        maximum_step_ps=.47, reset_release_s=5e-9, reset_rise_end_s=5.05e-9,
        live_prefix_only=True, full_native_completion_verified=False,
        physical_frequency_or_numerical_convergence_qualified=False,
        release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256={str(path.resolve()): digest(path) for path in inputs},
        artifacts={str(prefix.resolve()): digest(prefix)}))
    previous_path = base / 'qualification_progress_079.json'
    previous = json.loads(previous_path.read_text())
    work = previous['throughput_followup']
    work['breakpoint_grid_failure_followup'].update(DCO_reset_breakpoint_recovery_demonstrated=True,
        retained_prefix_proof=str((out / 'assessment.json').relative_to(root)),
        observed_accepted_time_s=times[-1], minimum_step_around_reset_s=minimum,
        full_completion_or_frequency_convergence_qualified=False)
    work['completed_native_ideal_wire_reference']['numerical_comparison_directory'] = refined.name
    pipeline = {}
    for name in ['stock_threaded_Xyce_002', 'stock_threaded_solver_controls_002',
                 'DCO_domain_nom_tt27_c0_f247_80ns_stock_threaded_001',
                 'DCO_ideal_wire_numeric_window_comparison_001']:
        folder = base / name
        status = json.loads((folder / 'status.json').read_text())
        runner = process(status['runner_pid']); assert runner['live']
        pipeline[name] = dict(status=status, runner=runner)
        inputs.append(folder / 'owner.json')
    work['threaded_solver_followup']['pipeline'] = pipeline
    work['threaded_solver_followup'].update(guarded_threaded_handoff_queued=True,
        physical_deck_byte_identity_required_except_solver_options=True)
    cases, live = {}, []
    for folder in [base / 'DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_002', refined]:
        status = json.loads((folder / 'status.json').read_text())
        native = process(status['native_pid']); assert native['live']
        live.append(native)
        content = (folder / 'point.cir.prn').read_text(); complete = content.splitlines()
        if content and not content.endswith('\n'): complete.pop()
        records = [line.split() for line in complete[1:] if len(line.split()) == 4 and line.split()[0].isdigit()]
        cases[folder.name] = dict(status=status, native=native, samples_observed=len(records),
            last_observed_simulation_time_s=float(records[-1][1]), waveform_observation_is_partial=True)
    work['active_native_transients'] = cases
    followup = previous['restored_self_C_operator_followup']
    followup.update(current_native_engines=live, native_points=cases, active_check_statuses=cases,
                    throughput_followup=work)
    inputs.extend([previous_path, out / 'assessment.json',
        Path(__file__).with_name('run_DCO_stock_threaded_point.py'),
        Path(__file__).with_name('compare_DCO_ideal_wire_numeric_windows.py')])
    previous.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='revised_numeric_grid_passes_prior_reset_failure_immutable_live_prefix_retained_threaded_handoff_and_matched_window_comparison_queued',
        throughput_followup=work, restored_self_C_operator_followup=followup,
        evidence_sha256={str(path): digest(path) for path in inputs},
        native_analog_jobs=live, native_analog_count=len(live), current_native_CAD_and_analog_engines=live,
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    snapshot = base / 'qualification_progress_080.json'
    assert not snapshot.exists(); save(snapshot, previous)
    overview = root / 'build/timing450/implementation_assessment.json'
    state = json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=followup, active_400mhz_throughput_followup=work,
        release_qualified=False, selected=False, timing_closure_complete=False)
    save(overview, state)
    print('Progress080: revised native grid crosses reset; immutable prefix retained; solver handoff/comparison queued, no release qualification.')


if __name__ == '__main__': main()
