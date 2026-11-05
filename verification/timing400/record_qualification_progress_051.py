#!/usr/bin/env python3
"""Record lossless native R primitives and recovered physical device bindings."""
from datetime import datetime, timezone
from pathlib import Path
import time
from check_compact_clock_tree import verify
from record_qualification_progress_031 import ROOT, BASE, read, digest, write
from record_qualification_progress_045 import process


def main():
    previous = BASE/'qualification_progress_050.json'
    owner = BASE/'distributed_RC_model_qualification_001/owner.json'
    deadline = read(owner)['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    receipts = dict(
        node_bindings='DCO_native_pointer_binding_index_001/assessment.json',
        original_device_geometry='DCO_original_device_geometry_ids_003/assessment.json',
        retained_device_geometry='DCO_retained_device_geometry_ids_002/assessment.json',
        single_tile_C_support='DCO_C_single_tile_support_001/assessment.json',
        private_R_primitives='DCO_private_R_primitives_001/assessment.json')
    checked = {k: verify(BASE/p) for k, p in receipts.items()}
    primitive = checked['private_R_primitives']
    assert primitive['every_native_R_branch_multiplicity_and_value_recovered']
    assert primitive['wire_resistors'] == 166286 and primitive['devices_bound_by_unique_physical_geometry'] == 8620
    assert primitive['deliberately_wrong_gate_drain_binding_rejected']
    assert checked['node_bindings']['ambiguous_terminal_bindings'] == 0
    engines = []
    for p in Path('/proc').glob('[0-9]*'):
        try:
            name = (p/'comm').read_text().strip()
            if name not in ['Xyce', 'ngspice', 'magicdnull']:
                continue
            row = process(int(p.name))
            if row['live']:
                engines.append(dict(kind=name, **row))
        except (FileNotFoundError, ProcessLookupError):
            continue
    assert not engines, engines
    history_paths = [BASE/p for p in [
        'magic_R_binding_trace_prepare_failure_001/assessment.json',
        'DCO_R_binding_trace_controls_001/status.json',
        'DCO_R_binding_trace_controls_001/network_comparison.json',
        'DCO_original_device_geometry_ids_001/status.json',
        'DCO_original_device_geometry_ids_002/status.json',
        'DCO_retained_device_geometry_ids_001/status.json',
        'magic_R_binding_trace_build_001/status.json',
        'magic_R_binding_trace_build_002/status.json',
        'magic_R_binding_trace_build_003/status.json']]
    historical = {str(p.relative_to(ROOT)): read(p) for p in history_paths if p.name == 'status.json'}
    requirements = ROOT/'verification/release_requirements_400mhz.json'
    plan = ROOT/'verification/release_plan_400mhz.json'
    assert digest(requirements) == '02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52'
    assert digest(plan) == '2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'
    evidence = dict(receipts={k: str((BASE/p).relative_to(ROOT)) for k, p in receipts.items()},
        native_voltage_vertices=primitive['private_native_voltage_nodes'], native_wire_resistors=primitive['wire_resistors'],
        physical_devices_bound=primitive['devices_bound_by_unique_physical_geometry'],
        all_native_R_values_and_multiplicities_preserved=True, printed_name_and_original_alias_collapses_removed=True,
        legacy_reader_bias_applied=False, original_device_cards_preserved_as_metadata=True,
        wrong_gate_drain_binding_negative_control_rejected=True,
        full_R_native_extractions_added_this_phase=1, direct_saved_file_exports_added=5,
        full_R_extraction_not_repeated_for_missing_device_ID_log=True,
        node_lifetimes_resolved_by_generation=True,
        one_breakpoint_tiles_recovered=checked['node_bindings']['single_breakpoint_conductor_tiles'],
        outstanding_surveyed_signal_C_supports=checked['single_tile_C_support']['classification_counts'],
        C_support_survey_is_not_full_layout_or_C_assignment=True,
        original_12h_deadline_uptime=deadline, total_budget_restarted=False,
        public_boundaries_local_junctions_and_distributed_C_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False)
    progress = dict(read(previous))
    paths = [Path(__file__).resolve(), previous, owner, requirements, plan,
        *[BASE/p for p in receipts.values()], *history_paths]
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='lossless_private_R_primitives_and_physical_device_bindings_not_runtime_or_release_qualification',
        evidence_sha256={str(p.relative_to(ROOT)): digest(p) for p in paths},
        private_R_model_primitives=evidence, historical_device_ID_diagnostic_and_build_states=historical,
        native_analog_jobs=[], native_analog_count=0, current_native_CAD_and_analog_engines=[],
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    mapping = dict(progress['distributed_RC_geometry_mapping'])
    mapping.update(private_native_voltage_id_export_completed=True,
        native_resistance_reader_bias_removed_in_new_primitives=True,
        physical_device_geometry_and_terminal_bindings_completed=True,
        runtime_model_eligible=False)
    progress['distributed_RC_geometry_mapping'] = mapping
    progress['next_actions'] = [
        'Bind actual public signal and supply boundaries to physical private mesh nodes; audit resistive components and body assumptions',
        'Extend capacitor support mapping to all original conductors, preserve layer identity and derive distributed charge weights with convergence/error checks',
        'Resolve remaining297 surveyed signal C boxes and4 multiple-node cases; qualify one-breakpoint terminal regions',
        'Distribute original MOS junction and intrinsic-resistor charge physically; preserve original C matrices without double counting',
        'After runtime eligibility, complete frozen nominal1.8V/15PVT four-mode calibration, timing,60 wholePLL cases,mode changes and physical release gates']
    snapshot = BASE/'qualification_progress_051.json'
    assert not snapshot.exists()
    write(snapshot, progress)
    overview = ROOT/'build/timing450/implementation_assessment.json'
    current = read(overview)
    current['latest_400mhz_qualification_progress'] = str(snapshot.relative_to(ROOT))
    current['active_400mhz_private_R_model_primitives'] = evidence
    current['active_400mhz_distributed_RC_geometry_mapping'] = mapping
    current['active_400mhz_distributed_RC_check'] = dict(owner=str(owner.relative_to(ROOT)),
        state='private_R_primitives_and_device_bindings_terminal_runtime_qualification_open',
        deadline_uptime=deadline, native_analog_jobs=0, native_CAD_jobs=0, release_qualified=False)
    for key in ['release_qualified', 'selected', 'timing_closure_complete']:
        current[key] = False
    write(overview, current)
    print('Progress051: every native resistor and vertex preserved with physical device bindings; boundary/C/junction qualification remains open.')


if __name__ == '__main__':
    main()
