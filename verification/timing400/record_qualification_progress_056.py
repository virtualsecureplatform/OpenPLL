#!/usr/bin/env python3
"""Record all-conductor C samples, all junction shares and exact device primitives."""
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
    names = ['DCO_GDS_conductor_registry_001', 'DCO_all_C_endpoint_GDS_identity_001',
        'DCO_all_junction_region_audit_001', 'DCO_exact_junction_device_primitives_001',
        'DCO_RC_corner_endpoint_support_comparison_001', 'DCO_corner_extra_C_support_geometry_001']
    paths = [BASE/n/'assessment.json' for n in names]
    registry, capacitance, junction, primitives, corners, extra = [verify(p) for p in paths]
    assert registry['all_native_conductors_have_unique_independent_GDS_cluster']
    r = read(paths[0].parent/'conductor_registry.json')
    assert len({tuple(v['GDS_clusters']) for v in r.values()}) == len(r) == 2686
    assert capacitance['all_nominal_endpoint_samples_on_expected_GDS_layer_conductor_or_well']
    assert capacitance['counts']['endpoints_checked'] == 1355315
    assert junction['all_local_junction_region_shares_match_GDS']
    assert junction['junction_terminal_records'] == 17236 and junction['physical_diffusion_regions'] == 10386
    assert primitives['exact_AP_private_connections_and_all_other_parameters_checked_in_emitted_deck']
    assert primitives['emitted_private_device_primitives'] == 8620
    assert extra['full_min_max_endpoint_sets_covered_by_nominal_sampled_geometry_plus_extra_box_checks']
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'comm').read_text().strip() in ['Xyce', 'ngspice', 'magicdnull']:
                assert not process(int(p.name))['live']
        except (FileNotFoundError, ProcessLookupError):
            continue
    previous = BASE/'qualification_progress_055.json'
    requirements = ROOT/'verification/release_requirements_400mhz.json'
    plan = ROOT/'verification/release_plan_400mhz.json'
    assert digest(requirements) == '02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52'
    assert digest(plan) == '2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'
    evidence = dict(receipts={n: str(p.relative_to(ROOT)) for n, p in zip(names, paths)},
        native_to_GDS_conductor_bijection=2686, independent_device_and_public_pin_seeds=26168,
        nominal_endpoint_layer_conductor_or_well_samples_checked=1355315,
        min_max_endpoint_set_comparison=corners['results'],
        corner_extra_diffusion_boxes_checked=dict(min=5, max=10),
        min_max_geometry_sample_coverage_complete=True,
        physical_diffusion_regions_with_exact_local_junction_shares=10386,
        source_drain_terminal_records_with_exact_GDS_shares=17236,
        private_device_primitives_emitted=8620, exact_local_junction_parameter_values=34472,
        previous_rounded_parameter_values_replaced=1138,
        maximum_removed_relative_junction_print_rounding=primitives['maximum_removed_relative_print_rounding'],
        capacitor_whole_support_voltage_weights_or_RC_error_qualified=False,
        implicit_ground_and_nonlinear_charge_qualified=False,
        external_PDN_driver_feeds_and_runtime_adaptor_qualified=False,
        original_12h_deadline_uptime=deadline, total_budget_restarted=False,
        native_CAD_or_analog_runs_added=0, runtime_model_eligible=False, release_qualified=False, adopted=False)
    progress = dict(read(previous))
    inputs = [Path(__file__).resolve(), previous, owner, requirements, plan, *paths]
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='all_conductor_C_sample_identity_three_RC_corners_and_all_local_junction_geometry_checked_exact_device_primitives_unqualified',
        evidence_sha256={str(p.relative_to(ROOT)): digest(p) for p in inputs},
        all_conductor_capacitor_and_exact_junction_geometry=evidence,
        native_analog_jobs=[], native_analog_count=0, current_native_CAD_and_analog_engines=[],
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    progress['next_actions'] = [
        'Construct geometry-backed distributed capacitor voltage weights over separate private R vertices; verify full native matrix conservation and passivity',
        'Bound whole-support geometry, metal-island potential, spatial integration and nonlinear junction/body/intrinsic-resistor charge error',
        'Qualify min/max distributed R values and external supply/driver feeds with final308-pin runtime adaptor',
        'After runtime eligibility complete frozen nominal1.8V/15PVT four-mode calibration, timing,60 wholePLL cases,mode changes and physical release gates']
    snapshot = BASE/'qualification_progress_056.json'
    assert not snapshot.exists()
    write(snapshot, progress)
    overview = ROOT/'build/timing450/implementation_assessment.json'
    current = read(overview)
    current['latest_400mhz_qualification_progress'] = str(snapshot.relative_to(ROOT))
    current['active_400mhz_all_conductor_C_and_exact_junction_geometry'] = evidence
    current['active_400mhz_distributed_RC_check'] = dict(owner=str(owner.relative_to(ROOT)),
        state='all_conductor_C_sample_and_local_junction_geometry_terminal_distributed_weights_charge_and_runtime_open',
        deadline_uptime=deadline, native_analog_jobs=0, native_CAD_jobs=0, release_qualified=False)
    for key in ['release_qualified', 'selected', 'timing_closure_complete']:
        current[key] = False
    write(overview, current)
    print('Progress056: full three-corner C sampled geometry and all local junction shares checked; exact private device primitives retained.')


if __name__ == '__main__':
    main()
