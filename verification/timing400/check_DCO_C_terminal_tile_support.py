#!/usr/bin/env python3
"""Classify C supports outside resistor breakpoint-to-breakpoint rectangles.

Retain the full native creation tile as distinct from the resistor's longitudinal
span. An intersection with a tile extension is geometry evidence only: it does
not assign C to an endpoint or bound the resistance of an open conductor end.
"""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import signal
import time
from check_compact_clock_tree import verify
from inventory_DCO_C_to_R_segments import overlaps
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    left = json.loads(owner.read_text())['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    survey = base/'DCO_C_R_segment_support_inventory_001/assessment.json'
    geometry = base/'DCO_retained_R_mesh_geometry_001/assessment.json'
    assert verify(survey)['counts']['no_creation_segment_intersection'] > 0
    assert verify(geometry)['wire_branch_type_and_value_preserved_at_creation_and_export']
    branches = geometry.parent/'branches.json'
    uncovered = survey.parent/'uncovered_supports.json'
    tiles = defaultdict(list)
    for row in json.loads(branches.read_text()):
        if 'segment_support_internal' in row:
            tiles[row['original_conductor']].append(row)
    counts, results = Counter(), []
    for row in json.loads(uncovered.read_text()):
        box = row['box_internal']
        matches = [r for r in tiles[row['original_conductor']] if overlaps(box, r['creation_geometry']['tile_internal'])]
        distances = []
        for match in matches:
            l, b, r, t = match['segment_support_internal']
            distances.append(max(l-box[2], box[0]-r, b-box[3], box[1]-t, 0)*5)
        state = 'inside_creation_tile_extension' if matches else 'outside_all_recorded_creation_tiles'
        counts[state] += 1
        results.append(dict(**row, classification=state,
            creation_tile_matches=len(matches),
            nearest_segment_padding_within_matching_tile_nm=min(distances) if distances else None,
            example_branches=matches[:2]))
    target = next(r for r in results if r['original_conductor'] == 'COARSETHERMAL_CODE[23]' and r['box_internal'] == [16113, 5266, 16113, 5269])
    assert target['classification'] == 'inside_creation_tile_extension'
    out = base/'DCO_C_R_terminal_tile_support_001'
    out.mkdir(exist_ok=False)
    save(out/'supports.json', results)
    save(out/'coarse23_remote_support.json', target)
    paths = [Path(__file__).resolve(), owner, survey, geometry, branches, uncovered,
             Path(__file__).with_name('inventory_DCO_C_to_R_segments.py')]
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in paths},
        artifacts={str(p): sha(p) for p in out.iterdir()}, counts=dict(counts),
        old_maximum_representative_gap_nm=target['nearest_representative_padding_nm'],
        new_mesh_max_gap_example_tile_extension_padding_nm=target['nearest_segment_padding_within_matching_tile_nm'],
        endpoint_C_assignment_or_open_end_R_error_bound_qualified=False,
        all_C_supports_covered_by_recorded_creation_tiles=not counts['outside_all_recorded_creation_tiles'],
        release_qualified=False, adopted=False, scope=__doc__))
    print('C terminal tile support:', dict(counts), '; old43.835um example is a', target['nearest_segment_padding_within_matching_tile_nm'], 'nm tile extension.')


if __name__ == '__main__':
    main()
