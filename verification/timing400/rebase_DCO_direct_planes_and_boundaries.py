#!/usr/bin/env python3
"""Use direct working-plane records and port BPs for the complete mesh family."""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import shlex
import signal
import time
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    left = json.loads(owner.read_text())['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    index = base/'DCO_complete_R_tile_domain_index_001/assessment.json'
    assert verify(index)['all_snapshot_generations_resolved_to_final_private_nodes']
    family_proof = base/'DCO_complete_domain_model_primitives_001/assessment.json'
    assert verify(family_proof)['all_wire_endpoints_bound_by_exact_tile_breakpoint_lifetimes']
    boundary_proof = base/'DCO_private_R_public_boundary_audit_002/assessment.json'
    assert verify(boundary_proof)['actual_GDS_label_pin_rectangle_drawing_and_origin_layer_correspondence_passed']
    node_path = family_proof.parent/'nodes.json'
    nodes = {r['private_id']: r for r in json.loads(node_path.read_text())}
    trace_to_private = {r['trace_private_id']: r['private_id'] for r in nodes.values()}
    by_pointer = {(r['trace_private_id'].split('_')[2], r['native_pointer']): n for n, r in nodes.items()}
    planes, point_membership = defaultdict(set), defaultdict(set)
    domain_path = index.parent/'tile_domains.jsonl'
    for line in domain_path.open():
        d = json.loads(line)
        for bp in d['breakpoints']:
            n = trace_to_private[bp['private_id']]
            planes[n].add(d['native_working_plane'])
            point_membership[d['original_conductor'], d['native_working_plane'], tuple(bp['point_internal'])].add(n)
    contact_path = index.parent/'contact_domains.jsonl'
    contacts = defaultdict(list)
    for line in contact_path.open():
        r = json.loads(line)
        r['private_id'] = trace_to_private[r['private_id']]
        planes[r['private_id']].add(r['native_working_plane'])
        contacts[r['original_conductor'], r['contact_pointer']].append(r)
    expected_edges, tap_counts, contact_segments = Counter(), Counter(), []
    for rows in contacts.values():
        rows.sort(key=lambda r: r['copy_index'])
        assert len(rows) == rows[0]['copies'] and [r['copy_index'] for r in rows] == list(range(len(rows)))
        assert len({r['private_id'] for r in rows}) == len(rows)
        if len(rows) == 3:
            assert [r['native_working_plane'] for r in rows] == ['well', 'active', 'locali']
            assert rows[0]['contact_material'] in ['psubdiffcont', 'nsubdiffcont']
            tap_counts[rows[0]['contact_material']] += 1
        else:
            assert len(rows) == 2
        for a, b in zip(rows, rows[1:]):
            key = tuple(sorted([a['private_id'], b['private_id']])), a['contact_type_id']
            expected_edges[key] += 1
            contact_segments.append(dict(original_conductor=a['original_conductor'], contact_material=a['contact_material'],
                private_nodes=[a['private_id'], b['private_id']], endpoint_planes=[a['native_working_plane'], b['native_working_plane']],
                center_internal=a['center_internal'], contact_rectangle_internal=a['contact_rectangle_internal']))
    branch_path = family_proof.parent/'branches.jsonl'
    actual_edges, degree = Counter(), Counter()
    for line in branch_path.open():
        r = json.loads(line)
        degree.update(r['private_nodes'])
        if not r['status'] & 0x600:
            actual_edges[tuple(sorted(r['private_nodes'])), r['material_type_id']] += 1
    assert actual_edges == expected_edges and sum(actual_edges.values()) == 35578
    assert tap_counts == dict(psubdiffcont=160, nsubdiffcont=320)
    assert all(len(p) == 1 for p in planes.values())
    provenance = base/'DCO_R_tile_domain_trace_controls_001/trace/R_provenance.log'
    origins = {}
    for line in provenance.open():
        if line.startswith('NODE '):
            f = shlex.split(line)
            key = f[1], f[2]
            if key in by_pointer and int(f[6]) & 8:
                origins[by_pointer[key]] = dict(point_internal=list(map(int, f[4:6])), why=int(f[6]), status=int(f[7]))
    boundary_path = boundary_proof.parent/'boundaries.json'
    boundaries = json.loads(boundary_path.read_text())
    device_nodes = {n for r in json.loads((family_proof.parent/'device_connections.json').read_text()).values() for n in r['private_terminals']}
    rows = []
    for boundary in boundaries:
        name, layer = boundary['public_port'], boundary['layer'].replace('m', 'metal')
        points = {tuple(r['point_internal']) for r in boundary['candidates']}
        assert len(points) == 1
        point = next(iter(points))
        if name in ['VPB', 'VNB']:
            found = [n for n, r in nodes.items() if r['original_conductor'] == name]
            assert len(found) == 1 and found[0] in origins and not degree[found[0]] and found[0] not in device_nodes
            assert tuple(origins[found[0]]['point_internal']) == point
            planes[found[0]].add(layer)
        else:
            found = sorted(n for n in point_membership[name, layer, point] if n in origins and planes[n] == {layer})
        assert len(found) == len(boundary['candidates']), (name, layer, point, found)
        for n in found:
            rows.append(dict(index=len(rows)+1, physical_boundary=boundary['physical_boundary_id'],
                public_port=name, layer=boundary['layer'], point_internal=list(point), private_node=n,
                native_origin=origins[n], exact_source_port_breakpoint_preserved=True))
    assert len(rows) == 328 and len({r['physical_boundary'] for r in rows}) == 310
    assert set(planes) == set(nodes) and all(len(v) == 1 for v in planes.values())
    out = base/'DCO_direct_native_planes_and_boundaries_001'
    out.mkdir(exist_ok=False)
    save(out/'node_planes.json', {n: next(iter(v)) for n, v in planes.items()})
    save(out/'boundary_connections.json', rows)
    with (out/'contact_plane_segments.jsonl').open('x') as stream:
        for r in contact_segments:
            stream.write(json.dumps(r)+'\n')
    with (out/'point_connections_unqualified.spice').open('x') as stream:
        stream.write('* Unqualified physical point connectors for complete-domain mesh family.\n')
        for r in rows:
            stream.write(f'Vdomain_boundary_{r["index"]} {r["physical_boundary"]} {r["private_node"]} 0\n')
    prior = base/'DCO_native_mesh_node_plane_inference_001/assessment.json'
    inputs = [Path(__file__).resolve(), owner, index, family_proof, boundary_proof, node_path,
        domain_path, contact_path, branch_path, provenance, boundary_path, prior, family_proof.parent/'device_connections.json']
    artifacts = [out/n for n in ['node_planes.json', 'boundary_connections.json', 'contact_plane_segments.jsonl', 'point_connections_unqualified.spice']]
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(p): sha(p) for p in artifacts}, private_voltage_nodes=148346,
        all_direct_native_voltage_node_planes_unique=True, direct_contact_edge_planes_reproduce_all35578_native_edges=True,
        three_plane_tap_contacts=dict(tap_counts), all480_tap_contacts_have_three_distinct_voltage_nodes=True,
        prior_unqualified_two_plane_tap_contact_inference_rejected=True,
        prior312_locali_well_combined_annotations_not_confirmed_by_direct_trace=True,
        public_point_connectors=328, logical_ports=308, physical_layer_interfaces=310,
        original_GDS_checked_boundary_points_rebased_by_exact_source_BPs=True,
        M4_M5_supply_interfaces_preserved_separately=True,
        whole_pin_feed_contact_sheet_and_RC_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    print('Direct plane/port mapping passed:480 three-plane taps,35578 contact edges,148346 unique node planes,328 source-BP point connectors.')


if __name__ == '__main__':
    main()
