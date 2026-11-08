"""Inspect raw native area contributions without inferring final-node placement."""
import json
import math
import struct
from collections import Counter


def f32(x):
    return struct.unpack('f', struct.pack('f', x))[0]


def audit(trace):
    sites = Counter()
    negative = []
    support_mismatches = []
    count = split = 0
    with trace.open() as stream:
        for line in stream:
            r = json.loads(line)
            if r['kind'] != 'raw_resistance_area' or r['placement_qualified'] is not False:
                raise ValueError('raw unqualified area event required')
            before, added, after, weight = (float.fromhex(r[k + '_hex'])
                                            for k in ('before', 'native_added', 'after', 'weight'))
            if not all(math.isfinite(x) for x in (before, added, after, weight)):
                raise ValueError('nonfinite native area')
            if f32(f32(before) + f32(added)) != after:
                raise ValueError('native float area update mismatch')
            box = r['support_box']
            if len(box) != 4 or box[2] < box[0] or box[3] < box[1]:
                raise ValueError('invalid support rectangle')
            geometric = (box[2] - box[0]) * (box[3] - box[1]) * weight
            if added < 0:
                negative.append(r)
            if geometric != added:
                support_mismatches.append(dict(site=r['site'], support_box=box,
                                               geometric_area=geometric, native_added=added))
            count += 1
            split += bool(r['split'])
            sites[r['site']] += 1
    if not count:
        raise ValueError('native resistance area events required')
    return dict(raw_area_events=count, sites=dict(sites), native_float_updates_verified=True,
                negative_native_contributions=len(negative), negative_examples=negative[:10],
                geometric_area_disagreements=len(support_mismatches),
                disagreement_examples=support_mismatches[:10], split_events=split,
                merge_lineage_verified=False, final_node_area_continuity_verified=False,
                capacitance_placement_qualified=False, distributed_wire_R_qualified=False,
                release_ready=False)
