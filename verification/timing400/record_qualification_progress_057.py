#!/usr/bin/env python3
"""Record lifetime-safe wire bases and the verified local-charge metadata gap."""
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
    orientation = BASE/'DCO_private_wire_creation_geometry_002/assessment.json'
    basis = BASE/'DCO_native_tile_voltage_basis_001/assessment.json'
    kernel = BASE/'DCO_C_charge_kernel_metadata_audit_001/assessment.json'
    o, b, k = verify(orientation), verify(basis), verify(kernel)
    assert o['all_wire_creation_endpoint_orientations_unique'] and o['wire_branches_checked'] == 130708
    assert b['native_tile_chains_continuous_with_no_axis_gaps_or_overlaps']
    assert b['counts']['tiles'] == 55663 and b['counts']['wire_branches'] == 130708
    assert b['exact_nonnegative_partition_of_unity_for_all_uniform_axis_integrals']
    assert b['analytic_controls']['reversed_endpoint_orientation_control_rejected']
    assert k['uniform_target_box_C_weights_rejected_by_actual_native_counterexample']
    assert not k['local_charge_kernel_metadata_complete']
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'comm').read_text().strip() in ['Xyce', 'ngspice', 'magicdnull']:
                assert not process(int(p.name))['live']
        except (FileNotFoundError, ProcessLookupError):
            continue
    previous = BASE/'qualification_progress_056.json'
    requirements = ROOT/'verification/release_requirements_400mhz.json'
    plan = ROOT/'verification/release_plan_400mhz.json'
    assert digest(requirements) == '02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52'
    assert digest(plan) == '2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'
    evidence = dict(orientation_receipt=str(orientation.relative_to(ROOT)), basis_receipt=str(basis.relative_to(ROOT)),
        kernel_metadata_receipt=str(kernel.relative_to(ROOT)), oriented_native_wire_branches=130708,
        wire_endpoints_requiring_merge_history=8617, addresses_with_multiple_allocation_lifetimes=14913,
        continuous_native_tile_voltage_bases=55663, exact_rational_axis_integral_controls_passed=True,
        open_end_tile_extensions_requiring_error_bounds=21200,
        wire_branch_breakpoints_outside_creation_tile_axis_interval=140,
        node_coordinate_nearest_matching_and_printed_alias_merging_used=False,
        uniform_target_tile_charge_weights_rejected=True,
        perimeter_local_edge_and_fringe_clipped_shield_kernel_metadata_complete=False,
        C_contribution_weights_emitted=False, capacitor_passivity_or_RC_error_qualified=False,
        CPU_checker_implementation_interruption_receipt='build/timing400/release_001/DCO_private_wire_geometry_checker_interruption_001/assessment.json',
        native_CAD_or_analog_runs_added=0, original_12h_deadline_uptime=deadline,
        total_budget_restarted=False, runtime_model_eligible=False, release_qualified=False, adopted=False)
    progress = dict(read(previous))
    paths = [Path(__file__).resolve(), previous, owner, orientation, basis, kernel, requirements, plan,
        BASE/'DCO_private_wire_geometry_checker_interruption_001/assessment.json']
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='lifetime_safe_wire_tile_voltage_basis_complete_local_charge_kernel_trace_required_before_C_weights',
        evidence_sha256={str(p.relative_to(ROOT)): digest(p) for p in paths},
        native_wire_voltage_basis_and_charge_kernel_gap=evidence,
        native_analog_jobs=[], native_analog_count=0, current_native_CAD_and_analog_engines=[],
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    progress['next_actions'] = [
        'Create a new isolated Magic source/prefix so new instrumentation cannot change pinned previous sources or receipts',
        'Trace local perimeter edge intervals and exact overlap/fringe/sidewall/shield integration kernels aligned with existing contribution and surface serials; preserve native numerical outputs',
        'Integrate local charge kernels on lifetime-safe private voltage bases; verify full native matrix conservation and passivity before runtime use',
        'Bound open-end/transverse/spatial error and nonlinear/implicit-ground/intrinsic-resistor charge; qualify min/max R values, external feeds and308-pin adaptor',
        'After runtime eligibility complete frozen nominal1.8V/15PVT four-mode calibration, timing,60 wholePLL cases,mode changes and physical release gates']
    snapshot = BASE/'qualification_progress_057.json'
    assert not snapshot.exists()
    write(snapshot, progress)
    overview = ROOT/'build/timing450/implementation_assessment.json'
    current = read(overview)
    current['latest_400mhz_qualification_progress'] = str(snapshot.relative_to(ROOT))
    current['active_400mhz_wire_voltage_basis_and_C_kernel_gap'] = evidence
    current['active_400mhz_distributed_RC_check'] = dict(owner=str(owner.relative_to(ROOT)),
        state='native_wire_voltage_bases_terminal_local_charge_kernel_metadata_required_weights_and_runtime_open',
        deadline_uptime=deadline, native_analog_jobs=0, native_CAD_jobs=0, release_qualified=False)
    for key in ['release_qualified', 'selected', 'timing_closure_complete']:
        current[key] = False
    write(overview, current)
    print('Progress057: lifetime-safe native voltage bases retained; uniform C support-box placement rejected; local kernels required.')


if __name__ == '__main__':
    main()
