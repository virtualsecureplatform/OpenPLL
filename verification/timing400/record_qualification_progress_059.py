#!/usr/bin/env python3
"""Record complete charge kernels, direct domains and one consistent mesh family."""
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
    names = ['DCO_C_kernel_trace_controls_001', 'DCO_complete_C_support_GDS_geometry_001',
        'magic_R_tile_domain_trace_patch_001', 'magic_R_tile_domain_trace_build_001',
        'DCO_R_tile_domain_trace_controls_001', 'DCO_complete_R_tile_domain_index_001',
        'DCO_complete_domain_model_primitives_001', 'DCO_direct_native_planes_and_boundaries_001',
        'DCO_voltage_domain_coverage_002', 'DCO_corner_extra_voltage_domain_coverage_001',
        'DCO_voltage_domain_coverage_assessor_supersession_001']
    receipts = [BASE/n/'assessment.json' for n in names]
    c, g, patch, build, control, domains, family, direct, coverage, extras, replacement = [verify(p) for p in receipts]
    assert c['full_DCO_trace_accounting_passed'] and c['local_charge_kernel_integrals_and_alignment_passed']
    assert len(c['results']) == 3 and all(r['installed_RC_context_and_C_only_context_exact_C_devices_identical'] for r in c['results'])
    assert g['all_complete_nominal_support_boxes_edges_and_points_covered']
    assert control['R_graph_values_and_MOS_terminals_preserved_under_bijective_renaming']
    assert domains['all_snapshot_generations_resolved_to_final_private_nodes']
    assert domains['domain_counts']['multiple_breakpoints_collapsed_to_one_voltage'] == 502
    assert family['complete_voltage_domains'] == 65162 and family['native_wire_R_primitives'] == 166286
    assert direct['all480_tap_contacts_have_three_distinct_voltage_nodes']
    assert direct['prior_unqualified_two_plane_tap_contact_inference_rejected']
    assert coverage['all_nominal_supports_covered_without_overlapping_native_domains']
    assert coverage['independent_KLayout_geometry_controls'] == 1370
    assert extras['all_corner_extra_C_supports_have_anchored_native_voltage_domains']
    # Recheck full native-private connectivity independently of printed aliases.
    family_dir = BASE/'DCO_complete_domain_model_primitives_001'
    nodes = read(family_dir/'nodes.json')
    parent = {r['private_id']: r['private_id'] for r in nodes}
    original = {r['private_id']: r['original_conductor'] for r in nodes}
    def find(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n
    import json
    for line in (family_dir/'branches.jsonl').open():
        r = json.loads(line)
        a, b = r['private_nodes']
        assert original[a] == original[b] == r['original_conductor']
        parent[find(a)] = find(b)
    groups = {}
    for n, name in original.items():
        groups.setdefault(name, set()).add(find(n))
    assert len(groups) == 2686 and all(len(v) == 1 for v in groups.values())
    engines = []
    for p in Path('/proc').glob('[0-9]*'):
        try:
            name = (p/'comm').read_text().strip()
            if name in ['Xyce', 'ngspice', 'magicdnull']:
                row = process(int(p.name))
                if row['live']:
                    engines.append(dict(kind=name, **row))
        except (FileNotFoundError, ProcessLookupError):
            continue
    assert not engines, engines
    previous = BASE/'qualification_progress_058.json'
    requirements = ROOT/'verification/release_requirements_400mhz.json'
    plan = ROOT/'verification/release_plan_400mhz.json'
    assert digest(requirements) == '02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52'
    assert digest(plan) == '2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'
    evidence = dict(receipts={n: str(p.relative_to(ROOT)) for n, p in zip(names, receipts)},
        all_three_RC_corners_local_C_kernel_integrals_native_matrices_devices_and_feedback_passed=True,
        complete_nominal_GDS_supports_checked=1355315, complete_nominal_anchored_voltage_domain_supports_checked=1355315,
        min_max_additional_voltage_domain_supports_checked=dict(min=5, max=10),
        complete_voltage_domains=65162, continuous_wire_domains=55663, constant_voltage_domains=9499,
        recovered_multi_breakpoint_constant_domains=502, native_wire_R_primitives=166286,
        exact_junction_private_device_primitives=8620, private_voltage_nodes=148346,
        original_conductor_connected_components=2686, split_or_cross_conductor_R_components=0,
        new_private_namespace='_rdomain_', obsolete_mesh_IDs_not_mixed=True,
        direct_three_plane_taps=dict(psubdiffcont=160, nsubdiffcont=320), all_tap_copies_have_distinct_voltage_nodes=True,
        previous_unqualified_two_plane_tap_inference_rejected=True,
        previous312_combined_locali_well_annotations_are_inference_artifacts=True,
        direct_native_plane_assignments_and328_source_BP_boundary_connectors_checked=True,
        M4_M5_supply_feed_point_interfaces_kept_separate=True,
        full_C_energy_matrix_assembled=False, signed_global_passivity_and_RC_error_qualified=False,
        min_max_R_values_external_feeds_and_308_pin_runtime_adaptor_qualified=False,
        original_12h_deadline_uptime=deadline, total_budget_restarted=False,
        native_analog_runs_added=0, new_complete_R_domain_native_runs=1,
        runtime_model_eligible=False, release_qualified=False, adopted=False)
    progress = dict(read(previous))
    paths = [Path(__file__).resolve(), previous, owner, requirements, plan, *receipts,
        BASE/'magic_R_tile_domain_build_prerequisite_failure_001/assessment.json']
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='all_three_RC_charge_kernels_complete_typed_voltage_domain_family_and_direct_tap_planes_checked_C_energy_assembly_open',
        evidence_sha256={str(p.relative_to(ROOT)): digest(p) for p in paths},
        complete_charge_kernel_and_voltage_domain_family=evidence,
        active_distributed_RC_followups=[], native_analog_jobs=[], native_analog_count=0,
        current_native_CAD_and_analog_engines=[], release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    progress['next_actions'] = [
        'Assemble local area/perimeter/overlap/fringe/sidewall energy matrices on the complete _rdomain_ family, retaining signed shields and explicit roundoff ledger',
        'Verify zero-R native C conservation and signed global passivity; qualify open-end/transverse/spatial and nonlinear/implicit-ground/intrinsic-resistor charge error',
        'Qualify min/max R values, external supply/driver feeds and final308-pin runtime adaptor',
        'After runtime eligibility complete frozen nominal1.8V/15PVT four-mode calibration, timing,60 wholePLL cases,mode changes and physical release gates']
    snapshot = BASE/'qualification_progress_059.json'
    assert not snapshot.exists()
    write(snapshot, progress)
    overview = ROOT/'build/timing450/implementation_assessment.json'
    current = read(overview)
    current['latest_400mhz_qualification_progress'] = str(snapshot.relative_to(ROOT))
    current['active_400mhz_complete_charge_kernel_and_voltage_domain_family'] = evidence
    current['active_400mhz_model_component_family'] = str(family_dir.relative_to(ROOT))
    current['superseded_400mhz_tap_plane_inference'] = dict(
        receipt='build/timing400/release_001/DCO_native_mesh_node_plane_inference_001/assessment.json',
        status='rejected_for_runtime_three_plane_taps_missing_from_assumptions',
        replacement='build/timing400/release_001/DCO_direct_native_planes_and_boundaries_001/assessment.json')
    current['active_400mhz_distributed_RC_followups'] = []
    current['active_400mhz_distributed_RC_check'] = dict(owner=str(owner.relative_to(ROOT)),
        state='charge_kernel_and_complete_voltage_domain_checks_terminal_full_C_energy_assembly_and_runtime_open',
        deadline_uptime=deadline, native_analog_jobs=0, native_CAD_jobs=0, release_qualified=False)
    for key in ['release_qualified', 'selected', 'timing_closure_complete']:
        current[key] = False
    write(overview, current)
    print('Progress059: all three C-kernel corners and full typed domain coverage passed; corrected three-plane taps; consistent new primitive family retained.')


if __name__ == '__main__':
    main()
