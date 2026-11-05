#!/usr/bin/env python3
"""Compare original C support boxes with native resistor creation rectangles.

An inclusive rectangle intersection identifies possible support, not a voltage
attachment or an integration weight. Restrict this survey to independently
identified routed signal conductors; well and supply distribution remain open.
"""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import signal
import time
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def overlaps(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    left = json.loads(owner.read_text())['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    proof = base/'DCO_retained_R_mesh_geometry_001/assessment.json'
    assert verify(proof)['wire_branch_type_and_value_preserved_at_creation_and_export']
    path = proof.parent/'branches.json'
    terminals = base/'DCO_intercell_wire_rc_geometry_001/terminals.json'
    labels = {r['logical_net'] for r in json.loads(terminals.read_text()) if r['logical_net'] is not None}
    rects = defaultdict(list)
    bins = defaultdict(lambda: defaultdict(list))
    grid = 800  # 4um bins on the native 5nm grid; no geometry rounding.
    for row in json.loads(path.read_text()):
        net = row['original_conductor']
        if net not in labels or 'segment_support_internal' not in row:
            continue
        box = row['segment_support_internal']
        index = len(rects[net])
        rects[net].append(box)
        l, b, r, t = box
        for x in range(l//grid, r//grid+1):
            for y in range(b//grid, t//grid+1):
                bins[net][x, y].append(index)
    counts, per_net = Counter(), defaultdict(Counter)
    uncovered = []
    supports = base/'DCO_C_R_support_inventory_001/support_boxes.jsonl'
    for line in supports.open():
        row = json.loads(line)
        net = row['original_conductor']
        if net not in labels:
            counts['outside_routed_signal_scope'] += 1
            continue
        box = row['box_internal']
        l, b, r, t = box
        candidates = set()
        for x in range(l//grid, r//grid+1):
            for y in range(b//grid, t//grid+1):
                candidates.update(bins[net].get((x, y), []))
        found = sum(overlaps(box, rects[net][i]) for i in candidates)
        state = 'intersects_creation_segment' if found else 'no_creation_segment_intersection'
        counts[state] += 1
        per_net[net][state] += 1
        if found and row['nearest_representative_padding_nm'] > 0:
            counts['segment_found_despite_no_representative_point_in_box'] += 1
        if not found:
            uncovered.append(row)
    assert counts['intersects_creation_segment'] > 0
    out = base/'DCO_C_R_segment_support_inventory_001'
    out.mkdir(exist_ok=False)
    save(out/'per_conductor.json', {k: dict(v) for k, v in per_net.items()})
    save(out/'uncovered_supports.json', uncovered)
    paths = [Path(__file__).resolve(), owner, proof, path, terminals, supports]
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in paths},
        artifacts={str(p): sha(p) for p in out.iterdir()},
        scope='Routed signal conductor C support / rectangular native R segment intersections only',
        counts=dict(counts), signal_conductors_checked=len(per_net),
        voltage_attachment_or_C_integration_weights_qualified=False,
        well_supply_and_junction_distribution_qualified=False,
        physical_RC_or_transient_error_qualified=False, release_qualified=False, adopted=False))
    print('C to native R segment support survey:', dict(counts), flush=True)


if __name__ == '__main__':
    main()
