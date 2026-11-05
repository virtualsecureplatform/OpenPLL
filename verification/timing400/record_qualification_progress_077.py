#!/usr/bin/env python3
"""Record completed ideal-wire diagnostics and a bounded numerical comparison."""
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
    reference = base / 'DCO_native_zero_wire_R_nom_tt27_c0_f247_80ns_001'
    ref_path = reference / 'assessment.json'
    ref = json.loads(ref_path.read_text())
    assert ref['native_exit'] == 0 and ref['completed_diagnostic_oscillation']
    audit_path = base / 'DCO_native_zero_wire_R_nom_tt27_c0_f247_80ns_checks_001/assessment.json'
    audit = json.loads(audit_path.read_text())
    assert audit['terminal_native_ideal_wire_diagnostic_verified']
    assert audit['duration_ns'] == 80 and audit['measured_periods'] == 98
    for filename, value in audit['input_sha256'].items():
        assert digest(Path(filename)) == value, filename
    old_status = json.loads((reference / 'status.json').read_text())
    assert old_status['state'] == 'completed' and not process(old_status['runner_pid'])['live']
    previous_path = base / 'qualification_progress_076.json'
    previous = json.loads(previous_path.read_text())
    cases, live = {}, []
    paths = [Path(__file__).resolve(), owner, previous_path, ref_path, audit_path]
    for name in ['DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_002',
                 'DCO_native_zero_wire_R_nom_tt27_c0_f247_25ns_numeric_001']:
        folder = base / name
        status = json.loads((folder / 'status.json').read_text())
        native = process(status['native_pid'])
        assert native['live'] and native['argv'][-1] == str((folder / 'point.cir').resolve())
        live.append(native)
        wave = folder / 'point.cir.prn'; rows = []
        if wave.exists():
            text = wave.read_text(); lines = text.splitlines()
            if text and not text.endswith('\n'): lines.pop()
            rows = [line.split() for line in lines[1:] if len(line.split()) == 4 and line.split()[0].isdigit()]
        cases[name] = dict(status=status, native=native, samples_observed=len(rows),
            last_observed_simulation_time_s=float(rows[-1][1]) if rows else None,
            waveform_observation_is_partial=True)
        paths.append(folder / 'input_manifest.json')
    work = previous['throughput_followup']
    work.update(active_native_transients=cases, completed_native_ideal_wire_reference=dict(
        native_exit=0, duration_ns=80, measured_frequency_mhz=audit['measured_frequency_mhz'],
        measured_periods=98, samples=audit['samples'], late_windows=audit['windows'],
        ten_ns_window_frequency_spread_ppm=audit['ten_ns_window_frequency_spread_ppm'],
        physical_finite_R_range_or_calibration_qualified=False,
        independent_timestep_tolerance_duration_checked=False,
        numerical_comparison_directory='DCO_native_zero_wire_R_nom_tt27_c0_f247_25ns_numeric_001',
        numerical_comparison_scope='Matched15..25ns interval, tighter tolerances and0.5ps maximum step; diagnosis only',
        original_deadline_uptime=deadline, budget_restarted=False, release_qualified=False, adopted=False))
    followup = previous['restored_self_C_operator_followup']
    followup.update(current_native_engines=live, native_points=cases, active_check_statuses=cases,
                    throughput_followup=work)
    previous.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='native_ideal_wire_80ns_reference_completes_frequency_still_drifts_tighter25ns_numerical_diagnostic_and_full_R_serial_case_live',
        throughput_followup=work, restored_self_C_operator_followup=followup,
        evidence_sha256={str(path.relative_to(root)): digest(path) for path in paths},
        native_analog_jobs=live, native_analog_count=len(live), current_native_CAD_and_analog_engines=live,
        release_qualified=False, adopted=False, physical_whole_pll_passes=0,
        next_actions=[
            'Finish the live full-R serial and bounded25ns numerical diagnostic within the original deadline; do not retry identical native cases or infer failure from an observation timeout',
            'Compare matched ideal-wire intervals to diagnose numerical error versus settling; no physical finite-R tuning/calibration qualification follows from ideal-wire data',
            'Retain the general mesh projection as rejected for worse passive symbolic work; do not launch it as a speed fix',
            'Complete the unchanged four-mode nominal1.8V/15PVT calibration, timing, reset/CDC, wholePLL, physical and reproducibility gates'])
    snapshot = base / 'qualification_progress_077.json'
    assert not snapshot.exists(); save(snapshot, previous)
    overview = root / 'build/timing450/implementation_assessment.json'
    state = json.loads(overview.read_text())
    state.update(latest_400mhz_qualification_progress=str(snapshot.relative_to(root)),
        active_400mhz_restored_self_C_operator_followup=followup, active_400mhz_throughput_followup=work,
        release_qualified=False, selected=False, timing_closure_complete=False)
    save(overview, state)
    print('Progress077:80ns native ideal-wire diagnostic completed; settling/numerical accuracy open; full-R serial and tighter numerical check live.')


if __name__ == '__main__': main()
