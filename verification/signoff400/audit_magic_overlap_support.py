"""Reconstruct rectilinear overlap support from ordered shielding leaves.

Split-tile geometry and fringe support remain outside this implementation.
"""
import json
from audit_magic_coupling_geometry_trace import lines


def area(r):
    if len(r) != 4 or any(type(v) is not int for v in r) or r[2] < r[0] or r[3] < r[1]:
        raise ValueError('ordered integer rectangle required')
    return (r[2] - r[0]) * (r[3] - r[1])


def subtract(rect, cut):
    area(rect)
    area(cut)
    x0, y0 = max(rect[0], cut[0]), max(rect[1], cut[1])
    x1, y1 = min(rect[2], cut[2]), min(rect[3], cut[3])
    if x1 <= x0 or y1 <= y0:
        return [rect]
    candidates = [[rect[0], rect[1], x0, rect[3]],
                  [x1, rect[1], rect[2], rect[3]],
                  [x0, rect[1], x1, y0], [x0, y1, x1, rect[3]]]
    return [r for r in candidates if area(r)]


def reconstruct(trace, emit=None):
    active = None
    seen = set()
    epochs = set()
    completed = qualified = split_cases = leaves = 0
    for line in lines(trace):
        r = json.loads(line)
        kind = r['kind']
        if kind not in ('overlap_support_begin', 'overlap_shield_leaf', 'overlap_support_end'):
            continue
        key = (r['cell'], r['epoch'], r['overlap_id'])
        epochs.add(key[:2])
        if r['pointwise_placement_qualified'] is not False:
            raise ValueError('diagnostic cannot qualify placement')
        if kind == 'overlap_support_begin':
            if active is not None or key in seen:
                raise ValueError('nested or repeated overlap support')
            seen.add(key)
            if area(r['box']) != r['native_area']:
                raise ValueError('initial native area differs from support rectangle')
            active = dict(key=key, begin=r, pieces=[r['box']], removed=0,
                          split=bool(r['split']))
        elif active is None or active['key'] != key:
            raise ValueError('shield/end without matching overlap begin')
        elif kind == 'overlap_shield_leaf':
            leaves += 1
            if r['native_area'] < 0:
                raise ValueError('negative shielding area')
            active['removed'] += r['native_area']
            active['split'] |= bool(r['split'])
            if not active['split']:
                if area(r['box']) != r['native_area']:
                    raise ValueError('shielding leaf scalar/rectangle mismatch')
                before = sum(map(area, active['pieces']))
                pieces = [piece for old in active['pieces'] for piece in subtract(old, r['box'])]
                if before - sum(map(area, pieces)) != r['native_area']:
                    raise ValueError('overlapping or out-of-support shielding leaf')
                active['pieces'] = pieces
        else:
            begin = active['begin']
            for field in ('node1_id', 'node2_id', 'box', 'plane1', 'plane2', 'coefficient_hex', 'split'):
                if r[field] != begin[field]:
                    raise ValueError('overlap identity changed')
            if r['native_area'] != begin['native_area'] - active['removed']:
                raise ValueError('native scalar shielding ledger mismatch')
            if not active['split']:
                if sum(map(area, active['pieces'])) != r['native_area']:
                    raise ValueError('surviving geometric area differs from native area')
                qualified += 1
            else:
                split_cases += 1
            if emit is not None:
                emit(dict(cell=key[0], epoch=key[1], overlap_id=key[2],
                          node_ids=[r['node1_id'], r['node2_id']],
                          native_area=r['native_area'],
                          rectangles=active['pieces'] if not active['split'] else None,
                          rectilinear_support_reconstructed=not active['split'],
                          pointwise_capacitance_placement_qualified=False))
            completed += 1
            active = None
    if active is not None or len(epochs) != 1 or not completed:
        raise ValueError('one complete extraction epoch required')
    return dict(overlaps=completed, shielding_leaves=leaves,
                native_scalar_area_ledger_verified=True,
                rectilinear_support_reconstructions=qualified,
                unsupported_split_cases=split_cases,
                all_overlap_support_reconstructed=not split_cases,
                fringe_support_qualified=False, ground_placement_qualified=False,
                distributed_wire_R_qualified=False, release_ready=False)
