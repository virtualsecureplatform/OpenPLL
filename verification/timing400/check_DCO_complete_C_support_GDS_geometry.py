#!/usr/bin/env python3
"""Check complete nominal C support boxes/edges against actual GDS geometry.

This strengthens sampled identity checks. It still does not define local charge
density, private voltage weights or the implicit substrate return distribution.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import signal
import time
import pya
from check_compact_clock_tree import verify
from device_aware_conductor_geometry import conductor_geometry
from check_forming_antenna_geometry_v2 import engine_at_stage
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    left = deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    proof = base/'DCO_layer_qualified_C_endpoint_inventory_001/assessment.json'
    inventory = verify(proof)
    source = proof.parent/'endpoints.jsonl'
    registry_proof = base/'DCO_GDS_conductor_registry_001/assessment.json'
    assert verify(registry_proof)['all_native_conductors_have_unique_independent_GDS_cluster']
    registry_path = registry_proof.parent/'conductor_registry.json'
    registry = json.loads(registry_path.read_text())
    topname = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    gds = ROOT/'openlane'/topname/'runs/c1fine_range_001/final/gds'/(topname+'.gds')
    tech = ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech'
    assert 'substrate *ppdiff,*mvppdiff,space/w,pwell well $SUB -dnwell,isosub' in tech.read_text()
    layout = pya.Layout()
    layout.read(str(gds))
    assert layout.dbu == .001
    top = layout.cell(topname)
    engine, regs = engine_at_stage(conductor_geometry(layout, top), 'm5')
    nets = {net.cluster_id: net for net in engine.netlist().top_circuit().each_net()}
    nw = pya.Region(top.begin_shapes_rec(layout.layer(64, 20))).merged()
    assert pya.Region(top.begin_shapes_rec(layout.layer(64, 18))).is_empty()
    pw = pya.Region(top.bbox())-nw
    cache = {}
    def expected_region(name, material, plane):
        key = name, material, plane
        if key not in cache:
            if plane == 'well':
                result = nw if material == 'nwell' else pw
                assert name == ('VPWR' if material == 'nwell' else 'VGND')
            else:
                if plane == 'active':
                    layer = ('poly' if material == 'poly' else 'gate' if material in ['scnmos', 'scpmoshvt']
                             else 'diff' if material in ['ndiff', 'pdiff'] else 'tap')
                else:
                    layer = 'li' if plane == 'locali' else plane.replace('metal', 'm')
                cluster, = registry[name]['GDS_clusters']
                result = engine.shapes_of_net(nets[cluster], regs[layer], True).merged()
                if material in ['ndiff', 'scnmos', 'psubdiff']:
                    result &= pw
                elif material in ['pdiff', 'scpmoshvt', 'nsubdiff']:
                    result &= nw
            cache[key] = result.sized(1).merged()
        return cache[key]
    out = base/'DCO_complete_C_support_GDS_geometry_001'
    out.mkdir(exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    def status(state, **data):
        save(out/'status.json', dict(state=state, runner_pid=os.getpid(), started_utc=started,
            deadline_uptime=deadline, **data))
    status('checking_complete_nominal_support_boxes_edges_and_points')
    counts, by_material, exceptions = Counter(), defaultdict(Counter), []
    for line in source.open():
        row = json.loads(line)
        l, b, r, t = [v*5 for v in row['box_internal']]
        zero_dimension = l == r or b == t
        # Test a1nm corridor around a closed edge/point against the1nm-expanded
        # conductor. This checks its entire length, including endpoints.
        support = pya.Region(pya.Box(l-1, b-1, r+1, t+1) if zero_dimension else pya.Box(l, b, r, t))
        expected = expected_region(row['original_conductor'], row['effective_material'], row['plane'])
        uncovered = support-expected
        category = 'complete_support_geometry_passed' if uncovered.is_empty() else 'support_geometry_unresolved'
        counts[category] += 1
        counts['supports_checked'] += 1
        by_material[row['effective_material']][category] += 1
        if not uncovered.is_empty() and len(exceptions) < 10000:
            exceptions.append(dict(**row, complete_support_measure_nm2=support.area(),
                uncovered_measure_nm2=uncovered.area(), uncovered_bbox_nm=uncovered.bbox().to_s(),
                edge_or_point_corridor_used=zero_dimension))
        if counts['supports_checked'] % 10000 == 0:
            assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
            status('checking_complete_nominal_support_boxes_edges_and_points', counts=dict(counts), cached_regions=len(cache))
    assert counts['supports_checked'] == inventory['unique_layer_material_endpoints']
    save(out/'exceptions_first10000.json', exceptions)
    save(out/'counts_by_material.json', {k: dict(v) for k, v in by_material.items()})
    inputs = [Path(__file__).resolve(), owner, proof, source, registry_proof, registry_path, gds, tech,
        Path(__file__).with_name('device_aware_conductor_geometry.py'),
        Path(__file__).with_name('check_forming_antenna_geometry_v2.py')]
    artifacts = [out/'exceptions_first10000.json', out/'counts_by_material.json']
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(p): sha(p) for p in artifacts}, counts=dict(counts), RC_corner='nom',
        all_complete_nominal_support_boxes_edges_and_points_covered=not counts['support_geometry_unresolved'],
        geometric_conductor_expansion_nm=1, edge_or_point_test_corridor_half_width_nm=1,
        local_charge_kernels_private_voltage_weights_and_RC_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    status('complete_nominal_C_support_geometry_terminal', counts=dict(counts), release_qualified=False)
    print('Complete nominal C support geometry:', dict(counts))


if __name__ == '__main__':
    main()
