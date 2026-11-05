#!/usr/bin/env python3
"""Stream pair-kernel ownership, including native omitted self-conductor pairs."""
from collections import Counter
import json
from pathlib import Path
import time
from verify_magic_C_kernel_trace_v2 import blocks


def owner_rows(path):
    count = last_id = 0
    began = ended = False
    with Path(path).open() as stream:
        for text in stream:
            f = text.split()
            assert f and not ended
            if f[0] == 'BEGIN':
                assert not began
                began = True
            elif f[0] == 'OWNER':
                assert began and len(f) == 11
                row = dict(kernel_id=int(f[1]), a=f[2], b=f[3], source=list(map(int, f[4:7])),
                    target=list(map(int, f[7:10])), same_ideal_conductor=bool(int(f[10])))
                assert row['kernel_id'] > last_id and int(f[10]) in [0, 1]
                assert row['same_ideal_conductor'] == (row['a'] == row['b'])
                last_id = row['kernel_id']
                count += 1
                yield row
            else:
                assert f[0] == 'END' and int(f[1]) == count and int(f[2]) >= last_id
                ended = True
    assert began and ended and count


def owned_blocks(trace, deadline, progress=None):
    rows = iter(owner_rows(trace/'owners.log'))
    pending = next(rows, None)
    for count, block in enumerate(blocks(trace/'kernels.log'), 1):
        if count % 10000 == 0:
            assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
            if progress:
                progress(count)
        owner = None
        if pending and pending['kernel_id'] == block['id']:
            owner = pending
            pending = next(rows, None)
        assert not pending or pending['kernel_id'] > block['id']
        assert (owner is not None) == (block['kind'] in ['OVERLAP', 'FRINGE_HALO', 'SIDEWALL']), block['kind']
        yield block, owner
    assert pending is None and next(rows, None) is None


def verify_owners(trace, deadline):
    mapping = json.loads((trace/'node_ids.json').read_text())
    kinds, same = Counter(), Counter()
    for block, owner in owned_blocks(trace, deadline):
        if owner is None:
            continue
        assert owner['a'] in mapping and owner['b'] in mapping, owner
        assert all(i >= 0 for i in owner['source']+owner['target'])
        kinds[block['kind']] += 1
        if owner['same_ideal_conductor']:
            same[block['kind']] += 1
            assert not any(r[2] == 'P' for r in block['events'])
        if block['kind'] == 'FRINGE_HALO':
            assert all(v[2] == (0 if owner['same_ideal_conductor'] else 1)
                for _, v in block['values']['HALO_RULE_REMAINING'])
    return dict(pair_kernel_counts=dict(kinds), same_ideal_conductor_kernel_counts=dict(same),
        all_pair_kernel_owners_resolve_to_native_IDs=True, explicit_self_pairs_have_no_native_nonzero_P_events=True)
