#!/usr/bin/env python3
"""Record conductor/segment mapping progress without claiming runtime eligibility."""
from datetime import datetime, timezone
from pathlib import Path
import time
import shlex
from check_compact_clock_tree import verify
from record_qualification_progress_031 import ROOT, BASE, read, digest, write
from record_qualification_progress_045 import process


def main():
    previous = BASE/'qualification_progress_048.json'
    progress = dict(read(previous))
    owner = BASE/'distributed_RC_model_qualification_001/owner.json'
    budget = read(owner)
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < budget['deadline_uptime']
    receipts = {
        'conductor_identity': 'DCO_R_conductor_alias_audit_001/assessment.json',
        'remote_C_GDS_support': 'DCO_remote_C_support_geometry_001/assessment.json',
        'native_segment_trace_controls': 'DCO_R_segment_trace_controls_001/assessment.json',
        'retained_mesh_default_controls': 'DCO_retained_R_mesh_default_controls_001/assessment.json',
        'retained_mesh_extraction': 'DCO_retained_R_mesh_001/assessment.json',
        'retained_mesh_conductors': 'DCO_retained_R_mesh_conductor_audit_001/assessment.json',
        'native_segment_geometry': 'DCO_retained_R_mesh_geometry_001/assessment.json',
        'C_to_segment_support': 'DCO_C_R_segment_support_inventory_001/assessment.json',
        'C_terminal_tile_support': 'DCO_C_R_terminal_tile_support_001/assessment.json',
    }
    checked = {k: verify(BASE/p) for k, p in receipts.items()}
    assert checked['conductor_identity']['ambiguous_or_missing_conductor_bindings'] == 0
    assert checked['remote_C_GDS_support']['expected_GDS_conductor_found'] == 100
    assert checked['native_segment_trace_controls']['R_graph_values_and_MOS_terminals_preserved_under_bijective_renaming']
    assert checked['retained_mesh_default_controls']['R_graph_values_and_MOS_terminals_preserved_under_bijective_renaming']
    assert checked['native_segment_geometry']['wire_branch_type_and_value_preserved_at_creation_and_export']
    counts = checked['native_segment_geometry']['final_branch_counts']
    assert checked['retained_mesh_conductors']['all_original_MOS_resistor_and_public_terminal_conductor_identities_preserved']
    native_res = BASE/'DCO_retained_R_mesh_001/trace/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160.res.ext'
    native_R_count = same_name_R_count = 0
    for line in native_res.open():
        if line.startswith('resist '):
            f = shlex.split(line)
            native_R_count += 1
            same_name_R_count += f[1] == f[2]
    assert native_R_count == counts['wire_segments'] + counts['contacts']
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
    requirements = ROOT/'verification/release_requirements_400mhz.json'
    plan = ROOT/'verification/release_plan_400mhz.json'
    assert digest(requirements) == '02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52'
    assert digest(plan) == '2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'
    mapping = dict(owner=str(owner.relative_to(ROOT)), deadline_uptime=budget['deadline_uptime'],
        original_budget_includes_preparation_and_assessment=True,
        normal_simplify_off_still_reduces_series_parallel_and_triangles=True,
        retained_mesh_switch='OPENPLL_R_RETAIN_MESH',
        retained_mesh_electrical_equivalence_qualified=False, automatic_identical_native_retry=False,
        receipts={k: str((BASE/p).relative_to(ROOT)) for k, p in receipts.items()},
        all_78613_retained_nodes_bound_to_original_conductors=True,
        printed_provenance_group_name_differences=checked['conductor_identity']['provenance_group_name_difference_records'],
        worst_100_signal_supports_on_expected_GDS_conductor=True,
        segment_branch_counts=checked['native_segment_geometry']['final_branch_counts'],
        retained_mesh_voltage_nodes=checked['retained_mesh_conductors']['retained_R_MOS_and_port_nodes'],
        retained_mesh_SPICE_R_branches=checked['retained_mesh_extraction']['retained_wire_R_branches'],
        native_geometry_R_branches=native_R_count,
        native_R_branches_with_same_printed_endpoint_name=same_name_R_count,
        native_geometry_to_SPICE_alias_or_omitted_branch_reconciliation_qualified=False,
        largest_gap_C_support_intersecting_segments=checked['native_segment_geometry']['remote_C_support_intersecting_wire_segments'],
        C_to_segment_counts=checked['C_to_segment_support']['counts'],
        terminal_tile_support_counts=checked['C_terminal_tile_support']['counts'],
        old_largest_gap_example_terminal_tile_extension_nm=checked['C_terminal_tile_support']['new_mesh_max_gap_example_tile_extension_padding_nm'],
        capacitor_attachment_and_integration_weights_qualified=False,
        local_junction_and_bulk_distribution_qualified=False, runtime_model_eligible=False)
    paths = [Path(__file__).resolve(), previous, owner, requirements, plan, native_res,
        BASE/'DCO_R_segment_geometry_inspection_failure_001/assessment.json', *[BASE/p for p in receipts.values()]]
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='native_R_segment_support_mapping_progress_not_runtime_or_release_qualification',
        evidence_sha256={str(p.relative_to(ROOT)): digest(p) for p in paths},
        distributed_RC_geometry_mapping=mapping, native_analog_jobs=[], native_analog_count=0,
        current_native_CAD_and_analog_engines=[], physical_whole_pll_passes=0,
        release_qualified=False, adopted=False)
    progress['next_actions'] = [
        'Reconcile native node-pointer identities and repeated terminal names with SPICE alias/omission handling and qualify retained mesh electrical equivalence before runtime adoption',
        'Resolve uncovered C supports and layer identity; derive physical C integration/attachment weights on retained wire segments',
        'Distribute junction charge and intrinsic-resistor capacitance; qualify supply/body connections and bulk impedance',
        'Require original-conductor C conservation, device charge conservation and spatial/time-step convergence before runtime adoption',
        'Use eligible runtime models for nominal1.8V/15PVT100/250/300/400MHz range/calibration/reset reachability',
        'Complete frozen timing/interfaces,60 physical wholePLL cases,ordered mode changes and physical release gates']
    snapshot = BASE/'qualification_progress_049.json'
    assert not snapshot.exists()
    write(snapshot, progress)
    overview = ROOT/'build/timing450/implementation_assessment.json'
    current = read(overview)
    current['latest_400mhz_qualification_progress'] = str(snapshot.relative_to(ROOT))
    current['active_400mhz_distributed_RC_geometry_mapping'] = mapping
    current['active_400mhz_distributed_RC_check'] = dict(owner=str(owner.relative_to(ROOT)),
        state='retained_mesh_geometry_assessments_terminal_runtime_qualification_open',
        deadline_uptime=budget['deadline_uptime'], native_analog_jobs=0, native_CAD_jobs=0,
        release_qualified=False)
    for key in ['release_qualified', 'selected', 'timing_closure_complete']:
        current[key] = False
    write(overview, current)
    print('Progress049: native segment mapping retained; runtime eligibility and physical wholePLL release gates remain open.')


if __name__ == '__main__':
    main()
