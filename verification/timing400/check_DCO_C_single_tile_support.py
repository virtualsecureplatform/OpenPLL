#!/usr/bin/env python3
"""Check outstanding C boxes against native one-breakpoint conductor tiles.

Keep candidate node identities separate. A geometric intersection is not a C
weight or an assertion that a conductor tile has zero internal AC resistance.
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
    binding = base/'DCO_native_pointer_binding_index_001/assessment.json'
    assert verify(binding)['ambiguous_terminal_bindings'] == 0
    previous = base/'DCO_C_R_terminal_tile_support_001/assessment.json'
    assert verify(previous)['counts']['outside_all_recorded_creation_tiles'] == 8213
    tile_path = binding.parent/'single_breakpoint_tiles.json'
    support_path = previous.parent/'supports.json'
    tiles = defaultdict(list)
    split = 0
    for tile in json.loads(tile_path.read_text()):
        if tile['split']:
            split += 1
            continue
        tiles[tile['original_conductor']].append(tile)
    results, counts = [], Counter()
    for row in json.loads(support_path.read_text()):
        if row['classification'] != 'outside_all_recorded_creation_tiles':
            continue
        matches = [tile for tile in tiles[row['original_conductor']] if overlaps(row['box_internal'], tile['box_internal'])]
        candidates = sorted({tile['private_id'] for tile in matches})
        state = ('one_single_tile_voltage_candidate' if len(candidates) == 1 else
                 'multiple_single_tile_voltage_candidates' if candidates else 'outside_recorded_single_tiles')
        counts[state] += 1
        results.append(dict(original_conductor=row['original_conductor'], box_internal=row['box_internal'],
            classification=state, possible_private_nodes=candidates, example_tiles=matches[:2]))
    assert sum(counts.values()) == 8213
    out = base/'DCO_C_single_tile_support_001'
    out.mkdir(exist_ok=False)
    save(out/'supports.json', results)
    save(out/'uncovered_supports.json', [row for row in results if not row['possible_private_nodes']])
    paths = [Path(__file__).resolve(), owner, binding, previous, tile_path, support_path,
             Path(__file__).with_name('inventory_DCO_C_to_R_segments.py')]
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in paths},
        artifacts={str(p): sha(p) for p in out.iterdir()},
        original_outstanding_signal_supports=8213, classification_counts=dict(counts),
        native_single_breakpoint_tiles_checked=sum(map(len, tiles.values())), excluded_split_tiles=split,
        capacitor_values_or_geometry_modified=False, C_attachment_or_error_bound_qualified=False,
        release_qualified=False, adopted=False))
    print('Outstanding C support / one-breakpoint tiles:', dict(counts))


if __name__ == '__main__':
    main()
