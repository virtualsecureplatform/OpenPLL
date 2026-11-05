#!/usr/bin/env python3
"""Record three-corner capacitor surface accounting and junction diagnostics."""
from datetime import datetime, timezone
from pathlib import Path
import time
from check_compact_clock_tree import verify
from record_qualification_progress_031 import ROOT, BASE, read, digest, write
from record_qualification_progress_045 import process


def main():
    owner = BASE/'distributed_RC_model_qualification_001/owner.json'
    deadline = read(owner)['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    capacitance = BASE/'DCO_C_surface_trace_controls_001/assessment.json'
    junction = BASE/'DCO_zero_length_junction_source_audit_001/assessment.json'
    c, j = verify(capacitance), verify(junction)
    assert c['full_DCO_trace_accounting_passed'] and c['complete_ordered_plane_material_metadata']
    assert c['installed_RC_and_opt_in_C_only_exact_C_and_devices_identical']
    assert set(c['RC_corners']) == {'min', 'nom', 'max'}
    assert all(r['native_matrix_reconstructed'] and r['matrix_difference_pairs'] == 0 for r in c['results'])
    assert j['zero_length_sources_all_in_actual_decap_3_GDS_instances']
    assert j['zero_length_source_terminals'] == 152 and j['unique_decap_instances'] == 76
    engines = []
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'comm').read_text().strip() in ['Xyce', 'ngspice', 'magicdnull']:
                row = process(int(p.name))
                if row['live']:
                    engines.append(row)
        except (FileNotFoundError, ProcessLookupError):
            continue
    assert not engines, engines
    previous = BASE/'qualification_progress_052.json'
    requirements = ROOT/'verification/release_requirements_400mhz.json'
    plan = ROOT/'verification/release_plan_400mhz.json'
    assert digest(requirements) == '02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52'
    assert digest(plan) == '2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'
    evidence = dict(capacitance_receipt=str(capacitance.relative_to(ROOT)),
        junction_diagnostic_receipt=str(junction.relative_to(ROOT)),
        ordered_plane_material_metadata_all_three_RC_corners=True,
        unchanged_native_C_and_device_cards=True,
        trace_event_counts={r['corner']: r['trace_events'] for r in c['results']},
        missing_contribution_and_displaced_surface_serial_negative_controls_rejected=True,
        zero_length_sources_in_76_decap_instances=152,
        nonzero_global_fallback_source_junction_records=2,
        global_fallback_junction_physical_charge_qualified=False,
        all_conductor_spatial_C_weights_and_transient_error_qualified=False,
        original_12h_deadline_uptime=deadline, total_budget_restarted=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False)
    progress = dict(read(previous))
    inputs = [Path(__file__).resolve(), owner, previous, capacitance, junction, requirements, plan]
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='three_RC_corner_C_surface_accounting_complete_spatial_charge_and_runtime_open',
        evidence_sha256={str(p.relative_to(ROOT)): digest(p) for p in inputs},
        capacitor_surface_and_junction_diagnostics=evidence,
        native_analog_jobs=[], native_analog_count=0, current_native_CAD_and_analog_engines=[],
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    progress['next_actions'] = [
        'Use complete plane/material C metadata to map and weight all original conductors without merging private voltage vertices',
        'Validate local diffusion geometry and charge before allocating global-node fallback junction area; do not blindly restore the two pre-R fallback records',
        'Qualify distributed C, intrinsic resistor and body charge, external public driver/PDN feeds and final308-pin macro adaptor',
        'After runtime eligibility complete the unchanged nominal1.8V/15PVT four-mode calibration, timing,60 wholePLL cases,mode changes and physical release gates']
    snapshot = BASE/'qualification_progress_053.json'
    assert not snapshot.exists()
    write(snapshot, progress)
    overview = ROOT/'build/timing450/implementation_assessment.json'
    current = read(overview)
    current['latest_400mhz_qualification_progress'] = str(snapshot.relative_to(ROOT))
    current['active_400mhz_capacitor_surface_and_junction_diagnostics'] = evidence
    current['active_400mhz_distributed_RC_check'] = dict(owner=str(owner.relative_to(ROOT)),
        state='three_RC_corner_C_surface_accounting_terminal_spatial_weights_and_junction_charge_open',
        deadline_uptime=deadline, native_analog_jobs=0, native_CAD_jobs=0, release_qualified=False)
    for key in ['release_qualified', 'selected', 'timing_closure_complete']:
        current[key] = False
    write(overview, current)
    print('Progress053: all three C surface-accounting corners passed; local junction and distributed-model qualification remain open.')


if __name__ == '__main__':
    main()
