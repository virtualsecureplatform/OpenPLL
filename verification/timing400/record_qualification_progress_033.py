#!/usr/bin/env python3
"""Record completed capacitance mapping, range nonpass and isolated candidate."""
from datetime import datetime, timezone
from pathlib import Path
import time
from record_qualification_progress_031 import ROOT, BASE, read, digest, write


def main():
    names = [
        'qualification_progress_032.json',
        'parent_filled_metal_capacitance_network_audit_001/assessment.json',
        'parent_filled_metal_capacitance_positive_001/assessment.json',
        'parent_filled_extraction_device_audit_002/assessment.json',
        'fill_material_overlap_001/assessment.json',
        'lower_fill_capacitance_controls_001/assessment.json',
        'tie_resistor_geometry_controls_001/assessment.json',
        'current_digital_cap_geometry_correlation_002/assessment.json',
        'current_digital_native_capacitance_nodes_001/assessment.json',
        'current_digital_wire_capacitance_inventory_001/assessment.json',
        'tt100_endpoint_collection_001/assessment.json',
        'tt100_range_priority_handoff_001/assessment.json',
        'return_fine_range_candidate_001/plan.json',
        'return_fine_range_connectivity_001/assessment.json',
    ]
    paths = [BASE / n for n in names] + [Path(__file__).resolve(),
        ROOT / 'verification/release_requirements_400mhz.json',
        ROOT / 'verification/release_plan_400mhz.json']
    assert digest(paths[-2]) == '02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52'
    assert digest(paths[-1]) == '2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'
    prior = read(BASE / names[0])
    analog = []
    now_boot = time.clock_gettime(time.CLOCK_BOOTTIME)
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            if (proc / 'comm').read_text().strip() != 'Xyce':
                continue
            if (proc / 'stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z':
                continue
            argv = [s.decode() for s in (proc / 'cmdline').read_bytes().split(b'\0') if s]
            deck = Path(argv[-1])
            owner = read(deck.parent / 'owner.json')
            deadline = owner.get('absolute_deadline_uptime', owner.get('deadline_uptime'))
            assert deadline is not None and deadline > now_boot
            analog.append(dict(pid=int(proc.name), argv=argv, original_owner=owner,
                remaining_budget_s=deadline-now_boot))
        except (FileNotFoundError, ProcessLookupError):
            continue
    assert len(analog) <= 4
    assert read(BASE / names[-1])['elaboration_and_connectivity_passed']
    assert not read(BASE / 'tt100_endpoint_collection_001/assessment.json')['intrinsic_tt100_ordered_range_brackets_target']
    now = datetime.now(timezone.utc).isoformat()
    progress = dict(observed_utc=now, classification='electrical_mapping_and_range_progress_not_release',
        evidence_sha256={str(p.relative_to(ROOT)): digest(p) for p in paths},
        latest_candidate=prior['latest_candidate'],
        capacitance=dict(corrected_metal_fill_network_extraction_completed=True,
            positive_capacitors=21007169, exactly_zero_capacitors_removed=21579265,
            floating_branches_retained=True, parent_nodes=359, digital_targets_mapped=7468,
            digital_mapping_failures=0, original_mos_gate_area_conserved=True,
            native_warning_count=2288, warning_count_matches_known_decaps=True,
            full_flattened_feedback_captured=False, lower_fill_material_controls_completed=True,
            full_material_coverage_qualified=False, resistance_qualified=False,
            driver_types_exceeding_old_fixture_wire_diagonal_max=5,
            sums_are_effective_loads=False, nonlinear_device_capacitance_included=False,
            timing_load_enclosure_qualified=False, model_adopted=False),
        tt100_range=dict(coarse13_f8_mhz=102.31836454427376, coarse13_f247_mhz=104.12498091336614,
            coarse13_brackets_target=False, coarse14_f8_and_f247_in_progress=True,
            global_target_unreachability_proven=False, loaded_range_qualified=False),
        scheduling=dict(two_step5_checks_explicitly_superseded_for_range_gate=True,
            partial_outputs_retained=True, superseded_cases_identical_retry_authorized=False,
            corrected_duration_checks_continued=True, original_absolute_deadlines_retained=True,
            native_concurrency_limit=4),
        isolated_candidate=dict(top='IntegerPLL_DCO_EINVP_C1FINE160_RETURNFINE80',
            original_cells_preserved=691, added_return_loads=80, elaborated_connectivity_passed=True,
            negative_control_rejected=True, public_ports_and_encoding_preserved=True,
            physical_layout_started=False, native_analog_started=False, adopted=False),
        native_analog_jobs=sorted(analog, key=lambda r:r['pid']), native_analog_count=len(analog),
        required_nominal_15pvt_scope_unchanged=True, calibration_and_dynamic_models_qualified=False,
        qualified_timing_15pvt_complete=False, physical_whole_pll_cases_passed=0,
        physical_ordered_mode_change_cases_passed=0, release_qualified=False, adopted=False,
        next_actions=['Collect neighboring coarse14 TT100 range and both corrected duration probes within original deadlines',
            'Use range evidence to decide whether the isolated return fine-range candidate merits physical implementation',
            'Resolve remaining fill-material, resistance, nonlinear load and RC enclosure before timing-model adoption',
            'Complete nominal15PVT timing/calibration/interfaces,60 wholePLL cases and ordered mode changes',
            'Complete supply/noise, physical power/jitter/area and documented integration release gates'])
    snapshot = BASE / 'qualification_progress_033.json'
    assert not snapshot.exists()
    write(snapshot, progress)
    overview = ROOT / 'build/timing450/implementation_assessment.json'
    data = read(overview)
    data['latest_400mhz_qualification_progress'] = str(snapshot.relative_to(ROOT))
    data['active_400mhz_fill_capacitance_extraction'] = progress['capacitance']
    data['active_400mhz_tt100_range'] = progress['tt100_range']
    data['active_400mhz_return_fine_candidate'] = progress['isolated_candidate']
    for key in ['release_qualified', 'selected', 'timing_closure_complete']:
        data[key] = False
    write(overview, data)
    print('Progress033 recorded: mapped capacitance network, coarse13 TT100 nonpass, bounded neighboring checks and unadopted connectivity-audited candidate.')


if __name__ == '__main__':
    main()
