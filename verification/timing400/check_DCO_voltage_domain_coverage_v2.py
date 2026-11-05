#!/usr/bin/env python3
"""Exact grid-domain coverage with spatial bins and independent KLayout controls.

All coordinates lie on the native5nm grid. Complete rectangle/interval coverage
is equivalent to the earlier1nm expanded-region/corridor check on this grid.
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
from run_dco_qualification import ROOT, sha, save


def area_intersection(a, b):
    return max(0, min(a[2], b[2])-max(a[0], b[0]))*max(0, min(a[3], b[3])-max(a[1], b[1]))


def covered(box, rectangles):
    l, b, r, t = box
    if l < r and b < t:
        total = sum(area_intersection(box, q) for q in rectangles)
        assert total <= (r-l)*(t-b)
        return total == (r-l)*(t-b)
    if l == r and b == t:
        return any(q[0] <= l <= q[2] and q[1] <= b <= q[3] for q in rectangles)
    along = 1 if l == r else 0
    fixed = 1-along
    spans = sorted((max(box[along], q[along]), min(box[along+2], q[along+2]))
                   for q in rectangles if q[fixed] <= box[fixed] <= q[fixed+2])
    end = box[along]
    for lo, hi in spans:
        if hi < lo:
            continue
        if lo > end:
            return False
        end = max(end, hi)
    return end >= box[along+2]


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    left = deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    family_proof = base/'DCO_complete_domain_model_primitives_001/assessment.json'
    family = verify(family_proof)
    domain_path = family_proof.parent/'voltage_domains.jsonl'
    inventory_proof = base/'DCO_layer_qualified_C_endpoint_inventory_001/assessment.json'
    inventory = verify(inventory_proof)
    support_path = inventory_proof.parent/'endpoints.jsonl'
    boxes, bins = defaultdict(list), defaultdict(lambda: defaultdict(list))
    grid, overlap = 800, []
    def cells(box):
        return ((x, y) for x in range(box[0]//grid, box[2]//grid+1)
                for y in range(box[1]//grid, box[3]//grid+1))
    for line in domain_path.open():
        row = json.loads(line)
        key = row['original_conductor'], row['plane'], row['effective_material']
        box = row['box_internal']
        assert all(isinstance(v, int) for v in box)
        existing = set()
        for cell in cells(box):
            existing.update(bins[key].get(cell, []))
        for i in existing:
            if area_intersection(box, boxes[key][i]):
                overlap.append(dict(key=key, first=boxes[key][i], second=box))
        index = len(boxes[key])
        boxes[key].append(box)
        for cell in cells(box):
            bins[key][cell].append(index)
    assert not overlap, overlap[:2]
    out = base/'DCO_voltage_domain_coverage_002'
    out.mkdir(exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    def status(state, **data):
        save(out/'status.json', dict(state=state, runner_pid=os.getpid(), started_utc=started,
            deadline_uptime=deadline, **data))
    status('checking_exact_grid_native_voltage_domain_coverage')
    counts, materials, missing = Counter(), defaultdict(Counter), []
    sampled_materials = set()
    controls = 0
    for number, line in enumerate(support_path.open()):
        row = json.loads(line)
        key = row['original_conductor'], row['plane'], row['effective_material']
        box = row['box_internal']
        candidates = set()
        for cell in cells(box):
            candidates.update(bins[key].get(cell, []))
        rectangles = [boxes[key][i] for i in candidates]
        passed = covered(box, rectangles)
        if number % 1000 == 0 or row['effective_material'] not in sampled_materials:
            actual = pya.Region()
            for q in rectangles:
                actual.insert(pya.Box(*[v*5 for v in q]))
            actual = actual.merged().sized(1).merged()
            l, b, r, t = [v*5 for v in box]
            support = pya.Region(pya.Box(l-1, b-1, r+1, t+1) if l == r or b == t else pya.Box(l, b, r, t))
            assert passed == (support-actual).is_empty(), row
            sampled_materials.add(row['effective_material'])
            controls += 1
        category = 'complete_support_covered_by_anchored_native_domains' if passed else 'voltage_domain_coverage_unresolved'
        counts[category] += 1
        counts['supports_checked'] += 1
        materials[row['effective_material']][category] += 1
        if not passed and len(missing) < 20000:
            missing.append(dict(**row, candidate_domain_count=len(rectangles)))
        if counts['supports_checked'] % 100000 == 0:
            assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
            status('checking_exact_grid_native_voltage_domain_coverage', counts=dict(counts), KLayout_controls=controls)
    assert counts['supports_checked'] == inventory['unique_layer_material_endpoints']
    assert controls >= 1355 and len(sampled_materials) == 15
    # Moved geometry must fail actual full-support membership.
    assert not covered([1000000, 1000000, 1000010, 1000010], [[0, 0, 10, 10]])
    save(out/'uncovered_first20000.json', missing)
    save(out/'counts_by_material.json', {k: dict(v) for k, v in materials.items()})
    inputs = [Path(__file__).resolve(), owner, family_proof, domain_path, inventory_proof, support_path]
    artifacts = [out/'uncovered_first20000.json', out/'counts_by_material.json']
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(p): sha(p) for p in artifacts}, counts=dict(counts),
        native_voltage_domains=family['complete_voltage_domains'], typed_domain_groups=len(boxes),
        all_typed_native_domain_rectangles_have_disjoint_interiors=True,
        independent_KLayout_geometry_controls=controls, sampled_materials=sorted(sampled_materials),
        all_nominal_supports_covered_without_overlapping_native_domains=not counts['voltage_domain_coverage_unresolved'],
        native_geometry_grid_nm=5, KLayout_control_conductor_expansion_and_corridor_nm=1,
        displaced_support_control_rejected=True,
        local_kernel_voltage_weights_global_passivity_and_RC_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    status('exact_grid_native_voltage_domain_coverage_terminal', counts=dict(counts), release_qualified=False)
    print('Exact native voltage-domain coverage:', dict(counts), '; independent KLayout cases', controls)


if __name__ == '__main__':
    main()
