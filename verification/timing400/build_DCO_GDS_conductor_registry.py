#!/usr/bin/env python3
"""Identify native conductor names by independent GDS device/pin seed probes.

Keep bulk/well impedance and private RC voltages separate from the ideal GDS
connectivity used only to establish conductor identity.
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
    proof = base/'DCO_private_R_primitives_001/assessment.json'
    assert verify(proof)['every_native_R_branch_multiplicity_and_value_recovered']
    boundary_proof = base/'DCO_private_R_public_boundary_audit_002/assessment.json'
    assert verify(boundary_proof)['actual_GDS_label_pin_rectangle_drawing_and_origin_layer_correspondence_passed']
    node_path = proof.parent/'nodes.json'
    device_path = proof.parent/'device_connections.json'
    boundary_path = boundary_proof.parent/'boundaries.json'
    nodes = {r['private_id']: r for r in json.loads(node_path.read_text())}
    devices = json.loads(device_path.read_text())
    boundaries = json.loads(boundary_path.read_text())
    conductors = {r['original_conductor'] for r in nodes.values()}
    topname = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    gds = ROOT/'openlane'/topname/'runs/c1fine_range_001/final/gds'/(topname+'.gds')
    layout = pya.Layout()
    layout.read(str(gds))
    assert layout.dbu == .001
    engine, regs = engine_at_stage(conductor_geometry(layout, layout.cell(topname)), 'm5')
    out = base/'DCO_GDS_conductor_registry_001'
    out.mkdir(exist_ok=False)
    save(out/'status.json', dict(state='probing_all_device_and_public_pin_seeds', runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(), deadline_uptime=deadline))
    seeds, missing, ambiguous = [], [], []
    clusters = defaultdict(set)
    def probe(name, layer, point, identity, expected=None):
        x, y = point
        hits = []
        for dx, dy in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
            net = engine.probe_net(regs[layer], pya.Point(x+dx, y+dy))
            if net is not None:
                hits.append(dict(point_nm=[x+dx, y+dy], cluster=net.cluster_id))
        found = sorted({r['cluster'] for r in hits})
        row = dict(original_conductor=name, layer=layer, point_nm=point, identity=identity,
            physical_hits=hits, clusters=found)
        if expected is not None:
            row['expected_from_independent_GDS_pin_label'] = expected
            assert found == [expected], row
        seeds.append(row)
        clusters[name].update(found)
        if not found:
            missing.append(row)
        elif len(found) != 1:
            ambiguous.append(row)
    for name, device in devices.items():
        codes = device['native_terminal_codes']
        for code, private in zip(codes, device['private_terminals']):
            if code == 4:
                continue  # Well identity/impedance is a distinct physical audit.
            layer = 'poly' if code == 1 or device['model'].endswith('__res_generic_po') else 'diff'
            node = nodes[private]
            probe(node['original_conductor'], layer, [v*5 for v in node['point_internal']],
                  dict(device=name, model=device['model'], terminal_code=code, private_node=private))
    for row in boundaries:
        probe(row['public_port'], row['layer'], row['GDS_label_nm'],
              dict(public_boundary=row['physical_boundary_id']), row['expected_GDS_cluster'])
    missing_names = sorted(conductors-clusters.keys())
    multiple = {name: sorted(values) for name, values in clusters.items() if len(values) > 1}
    empty = sorted(name for name, values in clusters.items() if not values)
    registry = {name: dict(GDS_clusters=sorted(values), seed_count=sum(r['original_conductor'] == name for r in seeds))
                for name, values in clusters.items()}
    save(out/'seeds.json', seeds)
    save(out/'conductor_registry.json', registry)
    save(out/'unresolved.json', dict(missing_probes=missing, ambiguous_probes=ambiguous,
        native_conductors_without_seeds=missing_names, native_conductors_without_cluster=empty,
        native_conductors_with_multiple_clusters=multiple))
    passed = not (missing or ambiguous or missing_names or empty or multiple)
    wrong_control = False
    unique = [(name, next(iter(values))) for name, values in clusters.items() if len(values) == 1]
    if unique:
        a = unique[0]
        b = next((r for r in unique if r[1] != a[1]), None)
        wrong_control = b is not None and clusters[a[0]] != clusters[b[0]]
    inputs = [Path(__file__).resolve(), owner, proof, boundary_proof, node_path, device_path, boundary_path, gds,
        Path(__file__).with_name('device_aware_conductor_geometry.py'),
        Path(__file__).with_name('check_forming_antenna_geometry_v2.py')]
    artifacts = [out/'seeds.json', out/'conductor_registry.json', out/'unresolved.json']
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(p): sha(p) for p in artifacts}, native_conductors=len(conductors),
        device_and_public_pin_seeds=len(seeds), missing_seed_probes=len(missing), ambiguous_seed_probes=len(ambiguous),
        native_conductors_without_seeds=missing_names, native_conductors_with_multiple_clusters=multiple,
        all_native_conductors_have_unique_independent_GDS_cluster=passed,
        deliberately_wrong_conductor_cluster_projection_rejected=wrong_control,
        bulk_impedance_or_private_voltage_equipotential_qualified=False,
        capacitor_placement_weights_or_RC_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    save(out/'status.json', dict(state='GDS_conductor_registry_terminal', runner_pid=os.getpid(),
        conductor_identity_passed=passed, release_qualified=False))
    print('Native/GDS conductor registry:', len(conductors), 'conductors;', len(seeds),
          'seeds; missing', len(missing), 'ambiguous', len(ambiguous), 'multiple conductors', len(multiple))


if __name__ == '__main__':
    main()
