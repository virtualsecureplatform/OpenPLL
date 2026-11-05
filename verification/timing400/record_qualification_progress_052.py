#!/usr/bin/env python3
"""Record GDS-checked private-mesh public interfaces and point connectors."""
from datetime import datetime, timezone
from pathlib import Path
import time
from check_compact_clock_tree import verify
from record_qualification_progress_031 import ROOT, BASE, read, digest, write
from record_qualification_progress_045 import process


def main():
    previous = BASE/'qualification_progress_051.json'
    owner = BASE/'distributed_RC_model_qualification_001/owner.json'
    deadline = read(owner)['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    geometry = BASE/'DCO_private_R_public_boundary_audit_002/assessment.json'
    connector = BASE/'DCO_physical_boundary_connections_001/assessment.json'
    g, c = verify(geometry), verify(connector)
    assert g['split_conductors_or_cross_conductor_R_links'] == 0
    assert g['resistor_components'] == g['original_conductors'] == 2686
    assert g['actual_GDS_label_pin_rectangle_drawing_and_origin_layer_correspondence_passed']
    assert c['emitted_connector_graph_exactly_matches_GDS_checked_boundary_map']
    assert c['no_supply_M4_M5_interface_short_added']
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
    evidence = dict(geometry_receipt=str(geometry.relative_to(ROOT)), connector_receipt=str(connector.relative_to(ROOT)),
        resistor_components=2686, original_conductors=2686, split_or_shorted_original_conductors=0,
        logical_public_ports=308, physical_port_layer_interfaces=310, matched_native_origin_vertices=328,
        all_public_interface_points_match_actual_GDS_label_drawing_rectangle_and_layer=True,
        signal_and_body_point_nodes_are_coincident_within_each_interface=True,
        isolated_VPB_VNB_declared_pins_without_MOS_attachment=2,
        connected_MOS_bodies_use_the_VPWR_VGND_mesh=True,
        M4_M5_supply_interfaces_preserved_separately=True,
        physical_point_zero_voltage_connectors=328, external_supply_or_driver_feeds_qualified=False,
        public_308_pin_macro_adaptor_qualified=False, whole_pin_surface_equipotential_qualified=False,
        native_CAD_or_analog_runs_added_this_phase=0,
        original_12h_deadline_uptime=deadline, total_budget_restarted=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False)
    progress = dict(read(previous))
    paths = [Path(__file__).resolve(), previous, owner, geometry, connector,
        BASE/'DCO_private_R_public_boundary_failure_001/assessment.json', requirements, plan]
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='private_R_public_point_interfaces_checked_external_feeds_and_C_junctions_unqualified',
        evidence_sha256={str(p.relative_to(ROOT)): digest(p) for p in paths},
        private_R_public_point_interfaces=evidence,
        native_analog_jobs=[], native_analog_count=0, current_native_CAD_and_analog_engines=[],
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    mapping = dict(progress['distributed_RC_geometry_mapping'])
    mapping.update(all_R_conductors_connected_without_cross_links=True,
        public_pin_point_and_layer_correspondence_verified=True,
        external_public_pin_driver_or_PDN_feed_distribution_qualified=False,
        runtime_model_eligible=False)
    progress['distributed_RC_geometry_mapping'] = mapping
    progress['next_actions'] = [
        'Preserve capacitor endpoint material/plane identity and extend geometry/weight mapping to all original conductors',
        'Resolve remaining297 surveyed signal C supports and4 multiple-node cases; qualify terminal-region and distributed-C integration error',
        'Distribute physical MOS junction and intrinsic-resistor charge while preserving original matrices and device geometry',
        'Qualify external supply/driver feeds, public macro adaptor and body impedance without collapsing interior voltage nodes',
        'After runtime eligibility complete frozen nominal1.8V/15PVT four-mode calibration, timing,60 wholePLL cases,mode changes and physical release gates']
    snapshot = BASE/'qualification_progress_052.json'
    assert not snapshot.exists()
    write(snapshot, progress)
    overview = ROOT/'build/timing450/implementation_assessment.json'
    current = read(overview)
    current['latest_400mhz_qualification_progress'] = str(snapshot.relative_to(ROOT))
    current['active_400mhz_private_R_public_point_interfaces'] = evidence
    current['active_400mhz_distributed_RC_geometry_mapping'] = mapping
    current['active_400mhz_distributed_RC_check'] = dict(owner=str(owner.relative_to(ROOT)),
        state='physical_public_point_mapping_and_connectors_terminal_external_feeds_and_C_junctions_open',
        deadline_uptime=deadline, native_analog_jobs=0, native_CAD_jobs=0, release_qualified=False)
    for key in ['release_qualified', 'selected', 'timing_closure_complete']:
        current[key] = False
    write(overview, current)
    print('Progress052: GDS-checked public point interfaces and connectors retained; external feeds/C/junction qualification remains open.')


if __name__ == '__main__':
    main()
