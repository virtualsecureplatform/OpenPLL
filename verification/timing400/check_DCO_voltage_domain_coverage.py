#!/usr/bin/env python3
"""Check complete C support coverage by typed, anchored native voltage domains."""
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


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    left = deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    family_proof = base/'DCO_complete_domain_model_primitives_001/assessment.json'
    family = verify(family_proof)
    assert family['all_wire_endpoints_bound_by_exact_tile_breakpoint_lifetimes']
    domain_path = family_proof.parent/'voltage_domains.jsonl'
    inventory_proof = base/'DCO_layer_qualified_C_endpoint_inventory_001/assessment.json'
    inventory = verify(inventory_proof)
    support_path = inventory_proof.parent/'endpoints.jsonl'
    regions, raw_area = {}, Counter()
    for line in domain_path.open():
        row = json.loads(line)
        key = row['original_conductor'], row['plane'], row['effective_material']
        if key not in regions:
            regions[key] = pya.Region()
        box = pya.Box(*[v*5 for v in row['box_internal']])
        regions[key].insert(box)
        raw_area[key] += box.area()
    overlap = []
    for key, region in list(regions.items()):
        merged = region.merged()
        if merged.area() != raw_area[key]:
            overlap.append(dict(original_conductor=key[0], plane=key[1], effective_material=key[2],
                sum_domain_area_nm2=raw_area[key], union_area_nm2=merged.area()))
        regions[key] = merged.sized(1).merged()
    out = base/'DCO_voltage_domain_coverage_001'
    out.mkdir(exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    def status(state, **data):
        save(out/'status.json', dict(state=state, runner_pid=os.getpid(), started_utc=started,
            deadline_uptime=deadline, **data))
    status('checking_all_nominal_C_support_voltage_domain_coverage')
    counts, material_counts, missing = Counter(), defaultdict(Counter), []
    empty = pya.Region()
    for line in support_path.open():
        row = json.loads(line)
        key = row['original_conductor'], row['plane'], row['effective_material']
        l, b, r, t = [v*5 for v in row['box_internal']]
        zero_dimension = l == r or b == t
        support = pya.Region(pya.Box(l-1, b-1, r+1, t+1) if zero_dimension else pya.Box(l, b, r, t))
        uncovered = support-regions.get(key, empty)
        classification = 'complete_support_covered_by_anchored_native_domains' if uncovered.is_empty() else 'voltage_domain_coverage_unresolved'
        counts[classification] += 1
        counts['supports_checked'] += 1
        material_counts[row['effective_material']][classification] += 1
        if not uncovered.is_empty() and len(missing) < 20000:
            missing.append(dict(**row, uncovered_measure_nm2=uncovered.area(),
                uncovered_bbox_nm=uncovered.bbox().to_s(), matching_domain_region_exists=key in regions))
        if counts['supports_checked'] % 20000 == 0:
            assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
            status('checking_all_nominal_C_support_voltage_domain_coverage', counts=dict(counts))
    assert counts['supports_checked'] == inventory['unique_layer_material_endpoints']
    save(out/'uncovered_first20000.json', missing)
    save(out/'overlapping_domain_groups.json', overlap)
    save(out/'counts_by_material.json', {k: dict(v) for k, v in material_counts.items()})
    inputs = [Path(__file__).resolve(), owner, family_proof, domain_path, inventory_proof, support_path]
    artifacts = [out/n for n in ['uncovered_first20000.json', 'overlapping_domain_groups.json', 'counts_by_material.json']]
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(p): sha(p) for p in artifacts}, counts=dict(counts),
        anchored_native_voltage_domains=family['complete_voltage_domains'], typed_conductor_domain_groups=len(regions),
        overlapping_typed_domain_groups=len(overlap),
        all_nominal_supports_covered_without_overlapping_native_domains=not (counts['voltage_domain_coverage_unresolved'] or overlap),
        native_domain_expansion_nm=1, closed_edge_point_corridor_half_width_nm=1,
        local_kernel_voltage_weights_global_passivity_and_RC_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    status('native_voltage_domain_coverage_terminal', counts=dict(counts), overlapping_groups=len(overlap), release_qualified=False)
    print('Native voltage-domain C support coverage:', dict(counts), '; overlapping typed groups', len(overlap))


if __name__ == '__main__':
    main()
