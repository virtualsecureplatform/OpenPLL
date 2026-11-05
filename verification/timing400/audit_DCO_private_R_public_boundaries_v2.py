#!/usr/bin/env python3
"""Audit private R components and physical public-port interface candidates.

Check actual GDS pin labels/drawing, native port rectangles and incident layer.
Keep M4/M5 supply interfaces separate in the inventory. A boundary-point
correspondence is not qualification of an external pad/PDN feed, ideal drive
distribution across a pin, body impedance, capacitance or runtime timing.
"""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import shlex
import signal
import sys
import time
import pya
from audit_active_dco_rc_capacitance import parse
from check_compact_clock_tree import verify
from check_forming_antenna_geometry_v2 import engine_at_stage
from device_aware_conductor_geometry import conductor_geometry
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    left = json.loads(owner.read_text())['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    proof = base/'DCO_private_R_primitives_001/assessment.json'
    assert verify(proof)['every_native_R_branch_multiplicity_and_value_recovered']
    source = base/'DCO_R_binding_trace_controls_001/trace'
    topname = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    ext = source/(topname+'.ext')
    original = base/'DCO_original_device_geometry_ids_003/original.spice'
    model_ports = parse(original)['ports']
    node_path = proof.parent/'nodes.json'
    branch_path = proof.parent/'branches.jsonl'
    nodes = json.loads(node_path.read_text())
    by_id = {r['private_id']: r for r in nodes}
    printed = defaultdict(list)
    for row in nodes:
        printed[row['printed_name']].append(row)
    parent = {name: name for name in by_id}
    incident = defaultdict(Counter)
    def find(node):
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node
    branches = 0
    with branch_path.open() as stream:
        for line in stream:
            row = json.loads(line)
            a, b = row['private_nodes']
            assert row['original_conductor'] == by_id[a]['original_conductor'] == by_id[b]['original_conductor']
            parent[find(a)] = find(b)
            for node in [a, b]:
                incident[node][row['material_type_id']] += 1
            branches += 1
    components = defaultdict(set)
    component_nodes = Counter()
    for row in nodes:
        components[row['original_conductor']].add(find(row['private_id']))
        component_nodes[find(row['private_id'])] += 1
    assert len(components) == len(component_nodes) == 2686
    assert all(len(v) == 1 for v in components.values())
    # Read only required public origin/material metadata from the private stream.
    wanted = {(r['private_id'].split('_')[2], r['native_pointer']): r['private_id']
              for name in model_ports for r in printed[name]}
    types, origins = {}, {}
    with (source/'R_provenance.log').open() as stream:
        for line in stream:
            if line.startswith('TYPE '):
                f = shlex.split(line)
                types[f[1]] = f[2]
            elif line.startswith('NODE '):
                f = shlex.split(line)
                key = (f[1], f[2])
                if key in wanted:
                    origins[wanted[key]] = dict(why=int(f[6]), status=int(f[7]))
    assert len(origins) == len(wanted)
    native_ports = [shlex.split(line) for line in ext.open() if line.startswith('port ')]
    assert len(native_ports) == 310 and {r[1] for r in native_ports} == set(model_ports)
    assert len(model_ports) == len(set(model_ports)) == 308
    gds = ROOT/f'openlane/{topname}/runs/c1fine_range_001/final/gds/{topname}.gds'
    assert sha(gds) == '0f227ae41fa996eaa23410aecbe7a3b38090185285c768ba24435026f337a2dd'
    layout = pya.Layout()
    layout.read(str(gds))
    assert layout.dbu == .001
    top = layout.cell(topname)
    geom = conductor_geometry(layout, top)
    engine, regs = engine_at_stage(geom, 'm5')
    labels = defaultdict(list)
    for kind, number in [('m3', 70), ('m4', 71), ('m5', 72)]:
        for shape in top.shapes(layout.layer(number, 5)).each():
            if shape.is_text():
                text = shape.text
                labels[text.string, kind].append(text.trans.disp)
    material = {'m3': 'metal3', 'm4': 'metal4', 'm5': 'metal5'}
    device_path = proof.parent/'device_connections.json'
    connected_device_nodes = {n for device in json.loads(device_path.read_text()).values() for n in device['private_terminals']}
    resolved, used = [], set()
    isolated_declared_pin_nodes = set()
    for f in native_ports:
        assert len(f) == 8 and f[7] in material
        name, kind = f[1], f[7]
        rectangle = list(map(int, f[3:7]))
        l, b, r, t = [v*5 for v in rectangle]
        box = pya.Box(l, b, r, t)
        assert (pya.Region(box)-geom[kind]).is_empty(), (name, kind, 'port not covered by drawing')
        actual_labels = labels[name, kind]
        assert len(actual_labels) == 1 and box.contains(actual_labels[0]), (name, kind)
        expected = engine.probe_net(regs[kind], actual_labels[0])
        assert expected is not None
        candidates = []
        for row in printed[name]:
            mats = {types[v] for v in incident[row['private_id']]}
            isolated = not mats
            if isolated:
                assert name in ['VPB', 'VNB'] and kind == 'm3'
                assert len(printed[name]) == 1 and component_nodes[find(row['private_id'])] == 1
                assert row['private_id'] not in connected_device_nodes
                isolated_declared_pin_nodes.add(row['private_id'])
            elif mats != {material[kind]}:
                continue
            assert origins[row['private_id']]['why'] & 8
            x, y = row['point_internal']
            assert rectangle[0] <= x <= rectangle[2] and rectangle[1] <= y <= rectangle[3]
            found = set()
            for dx, dy in [(0, 0), (1, 1), (-1, 1), (1, -1), (-1, -1)]:
                net = engine.probe_net(regs[kind], pya.Point(x*5+dx, y*5+dy))
                if net is not None:
                    found.add(net.cluster_id)
            assert found == {expected.cluster_id}, (name, kind, row, found)
            candidates.append(dict(private_id=row['private_id'], point_internal=row['point_internal'],
                point_nm=[x*5, y*5], native_origin=origins[row['private_id']], incident_materials=sorted(mats),
                layer_evidence='native declared port and independent GDS label/drawing for an isolated vertex' if isolated else 'incident R material plus declared port and independent GDS'))
            used.add(row['private_id'])
        assert candidates, (name, kind)
        assert len({tuple(row['point_internal']) for row in candidates}) == 1
        boundary_id = name if kind == 'm3' else name+'__'+kind
        resolved.append(dict(public_port=name, physical_boundary_id=boundary_id, layer=kind,
            native_port_index=int(f[2]), rectangle_internal=rectangle, rectangle_nm=[l, b, r, t],
            GDS_label_nm=[actual_labels[0].x, actual_labels[0].y], expected_GDS_cluster=expected.cluster_id,
            candidates=candidates, same_layer_coincident_boundary_point=True,
            external_PDN_or_driver_distribution_qualified=False))
    assert len(isolated_declared_pin_nodes) == 2
    assert len(used) == len(wanted) == 328
    assert len({row['physical_boundary_id'] for row in resolved}) == 310
    # Wrong public-net correspondence must differ in the independent GDS graph.
    first = resolved[0]
    other = next(row for row in resolved if row['public_port'] != first['public_port'])
    assert first['expected_GDS_cluster'] != other['expected_GDS_cluster']
    assert all(len([r for r in resolved if r['public_port'] == name]) == 2 for name in ['VGND', 'VPWR'])
    out = base/'DCO_private_R_public_boundary_audit_002'
    out.mkdir(exist_ok=False)
    save(out/'boundaries.json', resolved)
    save(out/'resistive_components.json', {name: dict(root=next(iter(roots)),
        nodes=component_nodes[next(iter(roots))]) for name, roots in components.items()})
    paths = [Path(__file__).resolve(), Path(sys.executable), owner, proof, node_path, branch_path,
        ext, original, device_path, source/'R_provenance.log', gds,
        base/'DCO_private_R_public_boundary_failure_001/assessment.json',
        Path(__file__).with_name('device_aware_conductor_geometry.py'),
        Path(__file__).with_name('check_forming_antenna_geometry_v2.py')]
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in paths},
        artifacts={str(p): sha(p) for p in out.iterdir()}, wire_branches_checked=branches,
        native_voltage_nodes=len(nodes), original_conductors=len(components),
        resistor_components=len(component_nodes), split_conductors_or_cross_conductor_R_links=0,
        public_ports=308, physical_port_layer_records=310, matched_native_public_origin_vertices=len(used),
        isolated_declared_VPB_VNB_vertices_without_device_attachments=2,
        incident_R_layer_public_vertices=len(used)-2,
        coincident_same_layer_signal_and_body_boundary_points_verified=True,
        supply_M4_M5_physical_boundaries_kept_separate=True,
        actual_GDS_label_pin_rectangle_drawing_and_origin_layer_correspondence_passed=True,
        wrong_public_conductor_projection_control_rejected=True,
        external_driver_or_PDN_feed_distribution_qualified=False,
        ideal_pin_surface_potential_or_lumped_bulk_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    print('Private R boundaries:2686 connected conductors;308 ports/310 layer interfaces;328 native origins match actual GDS. External feed qualification remains open.')


if __name__ == '__main__':
    main()
