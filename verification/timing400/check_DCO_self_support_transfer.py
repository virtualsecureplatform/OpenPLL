#!/usr/bin/env python3
"""Transfer complete GDS coverage to new self-coupling supports by exact unions.

Each reference box/corridor already passed the complete typed GDS check. A new
support contained in their union therefore inherits that check. Uncovered
supports are retained for direct GDS checking, never treated as passed.
"""
from collections import Counter, defaultdict
import json
import math
import os
from pathlib import Path
import time
import pya

from check_compact_clock_tree import verify
from compile_local_C_operators_v2 import digest, save, project


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    old_proof = base/'DCO_complete_C_support_GDS_geometry_001/assessment.json'
    assert verify(old_proof)['all_complete_nominal_support_boxes_edges_and_points_covered']
    reference = base/'DCO_layer_qualified_C_endpoint_inventory_001/endpoints.jsonl'
    assert json.loads(old_proof.read_text())['input_sha256'][str(reference)] == digest(reference)
    operators = base/'DCO_local_C_operators_nom_self_002'
    fields = json.loads((operators/'fields.json').read_text())
    identity = base/'DCO_self_C_increment_identity_001'
    assert json.loads((identity/'assessment.json').read_text())['all_original_energy_operators_identical_under_exact_field_key_renaming']
    source = identity/'self_operators.jsonl'
    out = base/'DCO_self_C_support_transfer_001'
    out.mkdir(exist_ok=False)
    counts = Counter()
    def status(state):
        save(out/'status.json', dict(state=state, runner_pid=os.getpid(), deadline_uptime=deadline, counts=dict(counts)))
    grid = 4000
    def box_nm(box):
        l, b, r, t = [5*v for v in box]
        if l == r or b == t:
            return [l-1, b-1, r+1, t+1]
        return [l, b, r, t]
    def cells(box):
        return ((x, y) for x in range(box[0]//grid, (box[2]-1)//grid+1)
                for y in range(box[1]//grid, (box[3]-1)//grid+1))
    def clip(box, cell):
        x, y = cell
        return pya.Box(max(box[0], x*grid), max(box[1], y*grid),
            min(box[2], (x+1)*grid), min(box[3], (y+1)*grid))
    cover = defaultdict(pya.Region)
    status('indexing_previously_GDS_verified_supports')
    for text in reference.open():
        r = json.loads(text)
        key = r['original_conductor'], r['plane'], r['effective_material']
        box = box_nm(r['box_internal'])
        for cell in cells(box):
            cover[key, cell].insert(clip(box, cell))
        counts['reference_supports'] += 1
        if counts['reference_supports'] % 50000 == 0:
            assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
            status('indexing_previously_GDS_verified_supports')
    assert counts['reference_supports'] == 1355315
    for i, region in enumerate(cover.values()):
        region.merge()
        if i % 1000 == 0:
            assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    seen = set()
    status('checking_added_self_supports')
    with (out/'uncovered_endpoints.jsonl').open('x') as uncovered:
        for text in source.open():
            kind, a, b, serial, *data = json.loads(text)
            assert serial < 0 and fields[a][0] == fields[b][0]
            if kind == 'A':
                supports = [(a, data[0]), (b, data[0])]
            elif kind == 'L':
                supports = [(a, data[0]), (b, data[1])]
            else:
                assert kind == 'F'
                supports = [(a, project(data[0], data[1])), (b, data[1])]
            for field, rectangle in supports:
                key = tuple(fields[field])
                unique = key, tuple(rectangle)
                if unique in seen:
                    continue
                seen.add(unique)
                box = box_nm(rectangle)
                passed = True
                for cell in cells(box):
                    portion = pya.Region(clip(box, cell))
                    if not (portion-cover.get((key, cell), pya.Region())).is_empty():
                        passed = False
                        break
                counts['added_unique_supports'] += 1
                counts['covered_by_prior_GDS_verified_union' if passed else 'requires_direct_GDS_check'] += 1
                if not passed:
                    uncovered.write(json.dumps(dict(original_conductor=key[0], plane=key[1], effective_material=key[2],
                        box_internal=rectangle))+'\n')
                if counts['added_unique_supports'] % 20000 == 0:
                    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
                    status('checking_added_self_supports')
            counts['self_operators_checked'] += 1
    assert counts['self_operators_checked'] == 2642914
    inputs = [Path(__file__).resolve(), owner, old_proof, reference, operators/'assessment.json',
        operators/'fields.json', identity/'assessment.json', source]
    result = dict(counts=dict(counts), all_added_supports_in_previously_GDS_verified_unions=not counts['requires_direct_GDS_check'],
        unique_layer_material_endpoints=counts['requires_direct_GDS_check'],
        direct_GDS_check_required_for_uncovered_only=True,
        geometric_GDS_expansion_nm=1, edge_or_point_corridor_half_width_nm=1,
        voltage_ownership_and_physical_transient_accuracy_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256={str(p.resolve()): digest(p) for p in inputs},
        artifacts={str((out/'uncovered_endpoints.jsonl').resolve()): digest(out/'uncovered_endpoints.jsonl')})
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(out/'assessment.json', result)
    status('completed')
    print(json.dumps({k:v for k,v in result.items() if k not in ['input_sha256','artifacts']}, indent=2))


if __name__ == '__main__':
    main()
