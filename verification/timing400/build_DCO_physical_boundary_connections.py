#!/usr/bin/env python3
"""Encode verified physical point boundaries without merging supply layers.

Zero-volt connectors identify coincident mesh/interface points under an explicit
point-boundary representation. External driver/PDN feeds, ideal voltage across a
whole pin surface and the final macro adaptor remain separate qualifications.
"""
from collections import Counter
import json
import math
from pathlib import Path
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
    proof = base/'DCO_private_R_public_boundary_audit_002/assessment.json'
    audit = verify(proof)
    assert audit['actual_GDS_label_pin_rectangle_drawing_and_origin_layer_correspondence_passed']
    assert audit['supply_M4_M5_physical_boundaries_kept_separate']
    boundaries_path = proof.parent/'boundaries.json'
    boundaries = json.loads(boundaries_path.read_text())
    rows, expected, layers, public = [], Counter(), {}, {}
    for boundary in boundaries:
        name = boundary['physical_boundary_id']
        assert name not in layers and not name.startswith('_rmesh_')
        layers[name] = boundary['layer']
        public.setdefault(boundary['public_port'], []).append(name)
        points = {tuple(c['point_nm']) for c in boundary['candidates']}
        assert len(points) == 1 and boundary['same_layer_coincident_boundary_point']
        for candidate in boundary['candidates']:
            node = candidate['private_id']
            expected[name, node] += 1
            rows.append(dict(index=len(rows)+1, physical_boundary=name, private_node=node,
                public_port=boundary['public_port'], layer=boundary['layer'], point_nm=candidate['point_nm']))
    assert len(public) == 308 and len(layers) == 310 and len(rows) == 328
    assert len({r['private_node'] for r in rows}) == 328
    for name in ['VPWR', 'VGND']:
        assert sorted(public[name]) == [name+'__m4', name+'__m5']
    out = base/'DCO_physical_boundary_connections_001'
    out.mkdir(exist_ok=False)
    target = out/'point_connections_unqualified.spice'
    with target.open('x') as stream:
        stream.write('* Unqualified physical point-boundary connectors for private mesh assembly.\n')
        for row in rows:
            stream.write(f'Vboundary_{row["index"]} {row["physical_boundary"]} {row["private_node"]} 0\n')
    actual = Counter()
    for line in target.open():
        if line.startswith('*'):
            continue
        name, boundary, node, value = line.split()
        assert name.startswith('Vboundary_') and value == '0'
        actual[boundary, node] += 1
    assert actual == expected
    save(out/'connections.json', rows)
    save(out/'logical_to_physical_interfaces.json', public)
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in [Path(__file__).resolve(), owner, proof, boundaries_path]},
        artifacts={str(p): sha(p) for p in out.iterdir()},
        logical_public_ports=308, physical_layer_interfaces=310, zero_voltage_point_connectors=328,
        emitted_connector_graph_exactly_matches_GDS_checked_boundary_map=True,
        no_supply_M4_M5_interface_short_added=True,
        external_driver_or_PDN_feed_distribution_qualified=False,
        public_308_pin_macro_adaptor_qualified=False, whole_pin_surface_equipotential_qualified=False,
        C_and_local_junction_distribution_qualified=False, runtime_model_eligible=False,
        release_qualified=False, adopted=False))
    print('Encoded328 physical point connections for308 logical ports; M4/M5 supply interfaces preserved separately. Runtime adaptor remains unqualified.')


if __name__ == '__main__':
    main()
