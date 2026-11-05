#!/usr/bin/env python3
"""Probe every nominal C support on its exact GDS layer/conductor or well.

Endpoint/midpoint probes establish sampled support identity, not continuous
support coverage, voltage weights, implicit-ground distribution or RC error.
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
    registry_proof = base/'DCO_GDS_conductor_registry_001/assessment.json'
    assert verify(registry_proof)['all_native_conductors_have_unique_independent_GDS_cluster']
    registry_path = registry_proof.parent/'conductor_registry.json'
    registry = json.loads(registry_path.read_text())
    expected = {name: r['GDS_clusters'][0] for name, r in registry.items()}
    assert len(set(expected.values())) == len(expected) == 2686
    inventory_proof = base/'DCO_layer_qualified_C_endpoint_inventory_001/assessment.json'
    inventory = verify(inventory_proof)
    source = inventory_proof.parent/'endpoints.jsonl'
    topname = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    gds = ROOT/'openlane'/topname/'runs/c1fine_range_001/final/gds'/(topname+'.gds')
    tech = ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech'
    assert 'substrate *ppdiff,*mvppdiff,space/w,pwell well $SUB -dnwell,isosub' in tech.read_text()
    layout = pya.Layout()
    layout.read(str(gds))
    assert layout.dbu == .001
    top = layout.cell(topname)
    engine, regs = engine_at_stage(conductor_geometry(layout, top), 'm5')
    nw = pya.Region(top.begin_shapes_rec(layout.layer(64, 20))).merged()
    assert pya.Region(top.begin_shapes_rec(layout.layer(64, 18))).is_empty()
    wells = dict(nwell=nw, pwell=pya.Region(top.bbox())-nw)
    # Recheck all labelled public boundaries against registry cluster IDs before
    # using them for unlabelled internal endpoint identity.
    boundary_path = base/'DCO_private_R_public_boundary_audit_002/boundaries.json'
    for row in json.loads(boundary_path.read_text()):
        net = engine.probe_net(regs[row['layer']], pya.Point(*row['GDS_label_nm']))
        assert net is not None and net.cluster_id == expected[row['public_port']]
    out = base/'DCO_all_C_endpoint_GDS_identity_001'
    out.mkdir(exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    def status(state, **data):
        save(out/'status.json', dict(state=state, runner_pid=os.getpid(), started_utc=started,
            deadline_uptime=deadline, **data))
    status('checking_all_nominal_endpoint_layer_and_conductor_probes')
    counts, materials = Counter(), defaultdict(Counter)
    exceptions = []
    offsets = [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]
    with source.open() as stream:
        for line in stream:
            row = json.loads(line)
            material = row['effective_material']
            name = row['original_conductor']
            assert name in expected
            l, b, r, t = [v*5 for v in row['box_internal']]
            points = sorted({(l, b), (r, t), ((l+r)//2, (b+t)//2)})
            failures = []
            if row['plane'] == 'well':
                assert material in wells
                assert name == ('VPWR' if material == 'nwell' else 'VGND')
                for x, y in points:
                    probe = pya.Region(pya.Box(x-1, y-1, x+1, y+1))
                    if (wells[material] & probe).is_empty():
                        failures.append(dict(point_nm=[x, y], expected_well=material))
                category = 'well_mask_sampled_support_passed'
            else:
                if row['plane'] == 'active':
                    layer = ('poly' if material == 'poly' else 'gate' if material in ['scnmos', 'scpmoshvt']
                             else 'diff' if material in ['ndiff', 'pdiff'] else 'tap')
                    assert material in ['poly', 'scnmos', 'scpmoshvt', 'ndiff', 'pdiff', 'psubdiff', 'nsubdiff']
                else:
                    layer = 'li' if row['plane'] == 'locali' else row['plane'].replace('metal', 'm')
                for x, y in points:
                    found = set()
                    for dx, dy in offsets:
                        net = engine.probe_net(regs[layer], pya.Point(x+dx, y+dy))
                        if net is not None:
                            found.add(net.cluster_id)
                        if expected[name] in found:
                            break
                    if expected[name] not in found:
                        failures.append(dict(point_nm=[x, y], expected_cluster=expected[name],
                            found_clusters=sorted(found), layer=layer))
                category = 'exact_layer_conductor_sampled_support_passed'
            if failures:
                category = 'sampled_support_unresolved'
                if len(exceptions) < 10000:
                    exceptions.append(dict(**row, failed_probes=failures))
            counts[category] += 1
            counts['endpoints_checked'] += 1
            materials[material][category] += 1
            if counts['endpoints_checked'] % 50000 == 0:
                status('checking_all_nominal_endpoint_layer_and_conductor_probes', counts=dict(counts))
    assert counts['endpoints_checked'] == inventory['unique_layer_material_endpoints']
    save(out/'exceptions_first10000.json', exceptions)
    save(out/'counts_by_material.json', {k: dict(v) for k, v in materials.items()})
    inputs = [Path(__file__).resolve(), owner, registry_proof, registry_path, inventory_proof, source,
        gds, tech, boundary_path, Path(__file__).with_name('device_aware_conductor_geometry.py'),
        Path(__file__).with_name('check_forming_antenna_geometry_v2.py')]
    artifacts = [out/'exceptions_first10000.json', out/'counts_by_material.json']
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(p): sha(p) for p in artifacts}, RC_corner='nom', counts=dict(counts),
        all_nominal_endpoint_samples_on_expected_GDS_layer_conductor_or_well=not counts['sampled_support_unresolved'],
        sample_rule='native box endpoints and midpoint;1nm cardinal neighbourhood on physical boundaries',
        whole_support_geometry_and_voltage_weights_qualified=False,
        implicit_ground_feed_junction_charge_and_RC_error_qualified=False,
        min_max_geometry_coverage_qualified=False, runtime_model_eligible=False,
        release_qualified=False, adopted=False))
    status('all_nominal_endpoint_GDS_identity_terminal', counts=dict(counts), release_qualified=False)
    print('All nominal C endpoint sampled GDS identity:', dict(counts))


if __name__ == '__main__':
    main()
