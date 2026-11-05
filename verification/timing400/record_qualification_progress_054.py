#!/usr/bin/env python3
"""Record local decap junction candidate and exact native inventory balance."""
from datetime import datetime, timezone
from pathlib import Path
import json
import time
from check_compact_clock_tree import verify
from record_qualification_progress_031 import ROOT, BASE, read, digest, write
from record_qualification_progress_045 import process


def main():
    owner = BASE/'distributed_RC_model_qualification_001/owner.json'
    deadline = read(owner)['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    receipt = BASE/'DCO_local_decap_junction_candidate_001/assessment.json'
    c = verify(receipt)
    assert c['source_junction_candidates_corrected'] == 152
    assert c['physical_diffusion_regions_match_private_source_and_drain_boundary_points']
    assert c['corrected_rail_junction_area_perimeter_exactly_matches_native_inventory']
    assert c['original_global_fallback_double_count_and_post_R_missing_side_controls_rejected']
    old = read(BASE/'DCO_private_R_primitives_001/device_connections.json')
    new = read(receipt.parent/'device_connections_candidate.json')
    assert old.keys() == new.keys()
    changed = 0
    for name, before in old.items():
        after = new[name]
        assert all(after[k] == v for k, v in before.items())
        if 'junction_corrected_candidate_card' in after:
            changed += 1
            a, b = before['original_card'], after['junction_corrected_candidate_card']
            assert len(a) == len(b) and a[:5] == b[:5]
            assert all(x == y or x.startswith(('as=', 'ps=')) and x.split('=')[0] == y.split('=')[0]
                       for x, y in zip(a[5:], b[5:]))
    assert changed == 152
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'comm').read_text().strip() in ['Xyce', 'ngspice', 'magicdnull']:
                assert not process(int(p.name))['live']
        except (FileNotFoundError, ProcessLookupError):
            continue
    previous = BASE/'qualification_progress_053.json'
    progress = dict(read(previous))
    evidence = dict(receipt=str(receipt.relative_to(ROOT)), decap_source_junction_candidates=152,
        actual_GDS_diffusion_polygon_area_and_perimeter_verified=True,
        both_private_source_drain_boundary_point_correspondences_verified=True,
        native_rail_area_perimeter_exact_integer_balance_verified=True,
        original_global_fallback_plus_explicit_double_count_rejected=True,
        post_R_dropping_missing_local_sources_rejected=True,
        original_metadata_and_all_other_device_parameters_preserved=True,
        nonlinear_junction_charge_and_distributed_integration_qualified=False,
        native_CAD_or_analog_runs_added=0, runtime_model_eligible=False,
        release_qualified=False, adopted=False)
    inputs = [Path(__file__).resolve(), owner, previous, receipt]
    progress.update(observed_utc=datetime.now(timezone.utc).isoformat(),
        classification='local_decap_junction_geometry_candidate_balanced_charge_and_runtime_open',
        evidence_sha256={str(p.relative_to(ROOT)): digest(p) for p in inputs},
        local_decap_junction_candidate=evidence,
        native_analog_jobs=[], native_analog_count=0, current_native_CAD_and_analog_engines=[],
        release_qualified=False, adopted=False, physical_whole_pll_passes=0)
    progress['next_actions'] = [
        'Qualify nonlinear junction charge and spatial distribution using local GDS-backed decap source areas; never restore duplicated global fallback values',
        'Map and weight all plane/material capacitor endpoints on private R vertices, including remaining signal-support cases',
        'Qualify intrinsic resistor/body charge, external supply/driver feeds and308-pin macro adaptor',
        'After runtime eligibility complete unchanged nominal1.8V/15PVT four-mode calibration, timing,60 wholePLL cases,mode changes and physical release gates']
    snapshot = BASE/'qualification_progress_054.json'
    assert not snapshot.exists()
    write(snapshot, progress)
    overview = ROOT/'build/timing450/implementation_assessment.json'
    current = read(overview)
    current['latest_400mhz_qualification_progress'] = str(snapshot.relative_to(ROOT))
    current['active_400mhz_local_decap_junction_candidate'] = evidence
    current['active_400mhz_distributed_RC_check'] = dict(owner=str(owner.relative_to(ROOT)),
        state='local_decap_junction_geometry_candidate_balanced_charge_spatial_weights_and_runtime_open',
        deadline_uptime=deadline, native_analog_jobs=0, native_CAD_jobs=0, release_qualified=False)
    for key in ['release_qualified', 'selected', 'timing_closure_complete']:
        current[key] = False
    write(overview, current)
    print('Progress054: local decap junction geometry balances both native rail inventories; no runtime model adoption.')


if __name__ == '__main__':
    main()
