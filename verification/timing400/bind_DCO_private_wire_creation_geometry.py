#!/usr/bin/env python3
"""Resolve wire creation endpoints through all native allocation generations.

Native path traversal can reverse resistor endpoint slots. Preserve all possible
lifetimes for a reused address and accept only a unique pairing with final nodes.
No closest-coordinate matching or printed-name merging is used.
"""
from collections import Counter, defaultdict
from decimal import Decimal
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
    nodes_path, branches_path = proof.parent/'nodes.json', proof.parent/'branches.jsonl'
    nodes = json.loads(nodes_path.read_text())
    final_nodes = defaultdict(dict)
    for row in nodes:
        _, _, group, generation = row['private_id'].split('_')
        final_nodes[group][int(generation)] = row
    branches = defaultdict(list)
    for line in branches_path.open():
        row = json.loads(line)
        branches[row['native_group']].append(row)
    source = base/'DCO_R_binding_trace_controls_001/trace'
    creation, latest = {}, {}
    for line in (source/'R_segments.log').open():
        f = line.split()
        if f[0] == 'SEG':
            latest[f[1]] = f
        elif f[1] in branches:
            for row in branches[f[1]]:
                if row['status'] & 0x600:
                    segment = latest[row['native_branch']]
                    assert Decimal(segment[12]) == Decimal(row['native_milliohm'])
                    assert segment[13] == row['material_type_id']
                    assert int(segment[14]) & 0xe00 == row['status'] & 0xe00
                    creation[f[1], row['native_branch']] = segment
    assert len(creation) == 130708
    active, parent, history = {}, {}, defaultdict(list)
    serial = 0
    results, ambiguous = [], []
    counts = Counter()
    def resolve(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n
    for line in (source/'R_bindings.log').open():
        f = line.split()
        if f[0] == 'ALLOC':
            serial += 1
            assert f[1] not in active
            active[f[1]] = serial
            parent[serial] = serial
            history[f[1]].append(serial)
        elif f[0] == 'MERGE':
            assert f[1] in active and f[2] in active
            parent[resolve(active[f[2]])] = resolve(active[f[1]])
            del active[f[2]]
        elif f[0] == 'GROUP':
            group = f[1]
            if group in final_nodes:
                endpoints = final_nodes[group]
                for generation, row in endpoints.items():
                    assert resolve(active[row['native_pointer']]) == generation
                roots = {ptr: {endpoints[resolve(gen)]['private_id'] for gen in generations
                               if resolve(gen) in endpoints} for ptr, generations in history.items()}
                counts['addresses_with_multiple_lifetimes'] += sum(len(v) > 1 for v in history.values())
                for row in branches[group]:
                    if not row['status'] & 0x600:
                        continue
                    segment = creation[group, row['native_branch']]
                    a, b = row['private_nodes']
                    aroots, broots = roots.get(segment[2], set()), roots.get(segment[3], set())
                    pairings = [p for p in [(a, b), (b, a)] if p[0] in aroots and p[1] in broots]
                    direct = {endpoints[g]['native_pointer'] for g in endpoints
                              if endpoints[g]['private_id'] in {a, b}} == set(segment[2:4])
                    counts['creation_addresses_still_both_final' if direct else 'creation_addresses_need_merge_history'] += 1
                    item = dict(**row, creation_breakpoints_internal=[list(map(int, segment[4:6])), list(map(int, segment[6:8]))],
                        creation_tile_internal=list(map(int, segment[8:12])),
                        creation_address_candidates=[sorted(aroots & {a, b}), sorted(broots & {a, b})],
                        centerline=int(segment[15]), width=int(segment[16]))
                    if len(pairings) == 1:
                        item['oriented_private_nodes'] = list(pairings[0])
                        counts['unique_endpoint_orientation'] += 1
                    else:
                        counts['ambiguous_or_absent_endpoint_orientation'] += 1
                        ambiguous.append(item)
                    results.append(item)
            active, parent, history = {}, {}, defaultdict(list)
    assert len(results) == 130708
    # Source pinning documents both allowed endpoint mutations: zero-length
    # merges keep each slot; path traversal may reverse the two slots.
    src = ROOT/'build/timing400/magic_location_source_001/resis'
    simplify = (src/'ResSimple.c').read_text()
    merge = (src/'ResMerge.c').read_text()
    assert 'res->rr_node[0] = node1;' in simplify and 'res->rr_node[1] = node0;' in simplify
    assert 'workingRes->re_thisEl->rr_connection1 = node1;' in merge
    assert 'workingRes->re_thisEl->rr_connection2 = node1;' in merge
    out = base/'DCO_private_wire_creation_geometry_001'
    out.mkdir(exist_ok=False)
    with (out/'wire_geometry.jsonl').open('x') as stream:
        for row in results:
            stream.write(json.dumps(row)+'\n')
    save(out/'unresolved_orientations.json', ambiguous)
    inputs = [Path(__file__).resolve(), owner, proof, nodes_path, branches_path,
        source/'R_segments.log', source/'R_bindings.log', source/'extract.tcl',
        src/'ResMakeRes.c', src/'ResMerge.c', src/'ResSimple.c', src/'ResRex.c', src/'ResPrint.c']
    artifacts = [out/'wire_geometry.jsonl', out/'unresolved_orientations.json']
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(p): sha(p) for p in artifacts}, wire_branches_checked=len(results), counts=dict(counts),
        all_wire_creation_endpoint_orientations_unique=not ambiguous,
        native_R_values_types_and_branch_ids_preserved=True,
        closest_coordinate_matching_or_printed_name_merging_used=False,
        capacitor_voltage_weights_and_RC_error_qualified=False, runtime_model_eligible=False,
        release_qualified=False, adopted=False))
    print('Wire creation endpoint orientation:', dict(counts))


if __name__ == '__main__':
    main()
