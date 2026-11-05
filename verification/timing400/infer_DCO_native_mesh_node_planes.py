#!/usr/bin/env python3
"""Infer native contact endpoint planes from wire incidence and PDK contacts.

Nodes may legitimately belong to multiple planes at native zero-R interfaces.
Keep all private voltages separate; do not use a single-plane intersection for
nodes joining a tap and well. This is topology, not a GDS impedance proof.
"""
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
    proof = base/'DCO_private_R_primitives_001/assessment.json'
    assert verify(proof)['every_native_R_branch_multiplicity_and_value_recovered']
    node_path, branch_path = proof.parent/'nodes.json', proof.parent/'branches.jsonl'
    nodes = json.loads(node_path.read_text())
    known = {r['private_id']: set() for r in nodes}
    provenance = base/'DCO_R_binding_trace_controls_001/trace/R_provenance.log'
    types = {}
    for line in provenance.open():
        if line.startswith('TYPE '):
            f = shlex.split(line)
            types[f[1]] = f[2]
        elif line.startswith('BEGIN '):
            break
    wire_planes = {k: 'active' for k in ['poly', 'scnmos', 'scpmoshvt', 'ndiff', 'pdiff', 'psubdiff', 'nsubdiff']}
    wire_planes.update(locali='locali', pwell='well', nwell='well')
    wire_planes.update({f'metal{i}': f'metal{i}' for i in range(1, 6)})
    contact_planes = {k: {'active', 'locali'} for k in ['ndiffc', 'pdiffc', 'polycont', 'psubdiffcont', 'nsubdiffcont']}
    contact_planes['viali'] = {'locali', 'metal1'}
    contact_planes.update({f'via{i}': {f'metal{i}', f'metal{i+1}'} for i in range(1, 5)})
    tech = ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech'
    text = tech.read_text()
    for rule in ['ndc      ndiff      locali', 'pdc      pdiff      locali',
                 'nsc      nsd        locali', 'psc      psd        locali',
                 'mcon locali metal1', 'via1   metal1 metal2', 'via2   metal2 metal3',
                 'via3   metal3 metal4', 'via4   metal4 metal5']:
        assert rule in text
    assert 'polycont' in text
    contacts = []
    for line in branch_path.open():
        row = json.loads(line)
        material = types[row['material_type_id']]
        a, b = row['private_nodes']
        if row['status'] & 0x600:
            plane = wire_planes[material]
            known[a].add(plane)
            known[b].add(plane)
        else:
            assert material in contact_planes
            contacts.append(dict(**row, material=material))
    passes = 0
    while True:
        changed = 0
        passes += 1
        for row in contacts:
            a, b = row['private_nodes']
            allowed = contact_planes[row['material']]
            for origin, target in [(a, b), (b, a)]:
                choices = known[origin] & allowed
                if len(choices) == 1:
                    opposite = allowed-choices
                    before = len(known[target])
                    known[target].update(opposite)
                    changed += len(known[target])-before
        if not changed:
            break
        assert passes < 32
    unresolved = []
    oriented = []
    for row in contacts:
        a, b = row['private_nodes']
        allowed = contact_planes[row['material']]
        pairs = [(x, y) for x in sorted(known[a] & allowed) for y in sorted(known[b] & allowed) if x != y]
        result = dict(**row, endpoint_plane_pair_candidates=pairs)
        (oriented if len(pairs) == 1 else unresolved).append(result)
    single_path = base/'DCO_native_pointer_binding_index_001/single_breakpoint_tiles.json'
    singles, unresolved_singles = [], []
    for row in json.loads(single_path.read_text()):
        material = types[row['type_id']]
        allowed = {wire_planes[material]} if material in wire_planes else contact_planes[material]
        choices = sorted(known[row['private_id']] & allowed)
        result = dict(**row, raw_material=material, native_plane_candidates=choices)
        if len(choices) == 1:
            singles.append(result)
        else:
            unresolved_singles.append(result)
    # Declared isolated ports supply their own pinned physical plane evidence.
    boundary_path = base/'DCO_private_R_public_boundary_audit_002/boundaries.json'
    for row in json.loads(boundary_path.read_text()):
        for candidate in row['candidates']:
            layer = row['layer'].replace('m', 'metal')
            assert layer.startswith('metal')
            known[candidate['private_id']].add(layer)
    empty = [n for n, planes in known.items() if not planes]
    counts = Counter(tuple(sorted(v)) for v in known.values())
    out = base/'DCO_native_mesh_node_plane_inference_001'
    out.mkdir(exist_ok=False)
    save(out/'node_planes.json', {n: sorted(v) for n, v in known.items()})
    with (out/'contact_endpoint_planes.jsonl').open('x') as stream:
        for row in oriented:
            stream.write(json.dumps(row)+'\n')
    save(out/'single_tile_planes.json', singles)
    save(out/'unresolved.json', dict(contacts=unresolved, single_tiles=unresolved_singles, nodes_without_plane=empty))
    inputs = [Path(__file__).resolve(), owner, proof, node_path, branch_path, provenance, tech, single_path, boundary_path]
    artifacts = [out/'node_planes.json', out/'contact_endpoint_planes.jsonl', out/'single_tile_planes.json', out/'unresolved.json']
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(p): sha(p) for p in artifacts}, private_nodes=len(nodes), contact_branches=len(contacts),
        propagation_passes=passes, unresolved_contact_planes=len(unresolved),
        resolved_single_breakpoint_tile_planes=len(singles), unresolved_single_tile_planes=len(unresolved_singles),
        nodes_without_native_plane=len(empty), node_plane_set_counts={','.join(k): v for k, v in counts.items()},
        all_contact_and_single_tile_planes_uniquely_inferred=not (unresolved or unresolved_singles or empty),
        multiple_plane_native_zero_R_interfaces_preserved=True,
        contact_sheet_voltage_weights_or_GDS_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    print('Native plane inference:', len(oriented), 'oriented contacts;', len(unresolved), 'unresolved contacts;',
          len(singles), 'single tiles;', len(unresolved_singles), 'unresolved single tiles;', len(empty), 'untyped nodes')


if __name__ == '__main__':
    main()
