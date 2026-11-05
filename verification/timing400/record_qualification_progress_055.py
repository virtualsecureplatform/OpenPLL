#!/usr/bin/env python3
"""Record resolved signal support geometry and full nominal layer inventory."""
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
    geometry = BASE/'DCO_unresolved_C_layer_geometry_001/assessment.json'
    inventory = BASE/'DCO_layer_qualified_C_endpoint_inventory_001/assessment.json'
    g, i = verify(geometry), verify(inventory)
    assert g['actual_GDS_expected_net_on_recorded_metal_layer_all_probes_passed']
    assert g['geometry_classifications'] == dict(one_same_metal_island_mesh_vertex=297, one_correct_layer_single_tile=4)
    assert i['native_contributions'] == 8297230 and i['RC_corner'] == 'nom'
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
    previous = BASE/'qualification_progress_054.json'
    requirements = ROOT/'verification/release_requirements_400mhz.json'
    plan = ROOT/'verification/release_plan_400mhz.json'
    assert digest(requirements) == '02911569a2538d8b4d6c3139decdf7ec4d7c33bf2cbad85eed442947c0022b52'
    assert digest(plan) == '2d6d5ed4404df842d64d42d68ebe593e4f627e65b4f90aaa48bef5f991e94b02'
    evidence = dict(geometry_receipt=str(geometry.relative_to(ROOT)), inventory_receipt=str(inventory.relative_to(ROOT)),
        signal_supports_checked_on_actual_GDS_net_and_exact_metal_layer=301,
        single_tile_ambiguities_resolved_by_native_plane=4,
        metal1_supports_on_islands_with_unique_layer_identified_native_mesh_vertex=297,
        contact_native_incidence='viali and via1 identify metal1 at each of the297 previously uncovered supports',
        nominal_unique_layer_material_endpoints=i['unique_layer_material_endpoints'],
        nominal_counts_by_plane=i['counts_by_plane'],
        nominal_endpoint_conductors_outside_private_R_inventory=i['conductors_outside_private_R_inventory'],
        full_nominal_layer_inventory_complete=True, all_conductor_physical_mapping_complete=False,
        capacitor_weights_or_uniform_island_potential_error_qualified=False,
        min_max_endpoint_geometry_coverage_qualified=False,
        original_12h_deadline_uptime=deadline, total_budget_restarted=False,
        native_CAD_or_analog_runs_added=0, runtime_model_eligible=False, release_qualified=False, adopted=False)
    progress = dict(read(previous))
    paths = [Path(__file__).resolve(), previous, owner, geometry, inventory, requirements, plan]
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='remaining301_signal_C_support_locations_resolved_full_nominal_layer_inventory_complete_weights_and_runtime_open',
        evidence_sha256={str(p.relative_to(ROOT)): digest(p) for p in paths},
        layer_qualified_capacitor_supports=evidence,
        native_analog_jobs=[], native_analog_count=0, current_native_CAD_and_analog_engines=[],
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    progress['next_actions'] = [
        'Extend plane/material geometry correspondence and capacitor weights to the complete endpoint inventory, including wells/supplies and finite-resistor body charge',
        'Bound uniform metal-island potential and spatial integration error; location correspondence alone is insufficient',
        'Check min/max endpoint geometry coverage and nonlinear junction/body/intrinsic-resistor charge',
        'Qualify external supply/driver feeds and308-pin macro adaptor, then complete frozen nominal1.8V/15PVT four-mode calibration, timing,60 wholePLL cases,mode changes and physical release gates']
    snapshot = BASE/'qualification_progress_055.json'
    assert not snapshot.exists()
    write(snapshot, progress)
    overview = ROOT/'build/timing450/implementation_assessment.json'
    current = read(overview)
    current['latest_400mhz_qualification_progress'] = str(snapshot.relative_to(ROOT))
    current['active_400mhz_layer_qualified_capacitor_supports'] = evidence
    current['active_400mhz_distributed_RC_check'] = dict(owner=str(owner.relative_to(ROOT)),
        state='remaining301_signal_C_locations_resolved_full_nominal_inventory_complete_weights_charge_and_runtime_open',
        deadline_uptime=deadline, native_analog_jobs=0, native_CAD_jobs=0, release_qualified=False)
    for key in ['release_qualified', 'selected', 'timing_closure_complete']:
        current[key] = False
    write(overview, current)
    print('Progress055: remaining301 signal support locations resolved; full nominal plane/material endpoint inventory retained.')


if __name__ == '__main__':
    main()
