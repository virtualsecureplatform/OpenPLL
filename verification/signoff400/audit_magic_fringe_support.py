"""Compare rectilinear fringe support integrals with native per-rule fractions."""
import json
import math
from audit_magic_coupling_geometry_trace import lines
from audit_magic_overlap_support import area, subtract
from magic_fringe_kernel import measure


def reconstruct(trace, emit=None):
    active = None
    seen = set()
    epochs = set()
    rules = leaves = unsupported = 0
    max_error = 0.0

    def close(a, b):
        nonlocal max_error
        if not math.isfinite(a) or not math.isfinite(b):
            raise ValueError('nonfinite fringe integral')
        max_error = max(max_error, abs(a - b))
        if not math.isclose(a, b, rel_tol=5e-13, abs_tol=1e-13):
            raise ValueError('native fringe fraction/integral mismatch')

    def value(r, field):
        x = float.fromhex(r[field + '_hex'])
        if not math.isfinite(x):
            raise ValueError('nonfinite native fringe value')
        return x

    for line in lines(trace):
        r = json.loads(line)
        kind = r['kind']
        if kind not in ('fringe_rule_begin', 'fringe_rule_end', 'fringe_shield_leaf'):
            continue
        key = (r['cell'], r['epoch'], r['fringe_id'])
        epochs.add(key[:2])
        if r['pointwise_placement_qualified'] is not False:
            raise ValueError('diagnostic cannot qualify placement')
        length = r['reference_length']
        if type(length) is not int or length <= 0:
            raise ValueError('positive native fringe reference length required')
        if kind == 'fringe_rule_begin':
            if active is not None or key in seen:
                raise ValueError('nested or repeated fringe rule')
            seen.add(key)
            active = dict(key=key, begin=r, pieces=[r['box']], split=bool(r['split']),
                          last_c=0.0, last_s=0.0)
            close(value(r, 'coupling_shield'), 0.0)
            close(value(r, 'substrate_shield'), 0.0)
            for prefix in ('coupling', 'substrate'):
                close(measure(r['box'], r['boundary'], r['direction'], value(r, prefix + '_multiplier')),
                      value(r, prefix + '_fraction') * length)
        elif active is None or active['key'] != key:
            raise ValueError('fringe leaf/end without matching begin')
        elif kind == 'fringe_shield_leaf':
            begin = active['begin']
            for field in ('reference_length', 'boundary', 'direction', 'coupling_multiplier_hex',
                          'substrate_multiplier_hex'):
                if r[field] != begin[field]:
                    raise ValueError('fringe shielding kernel identity changed')
            for prefix, previous in [('coupling', 'last_c'), ('substrate', 'last_s')]:
                increment = measure(r['box'], r['boundary'], r['direction'], value(r, prefix + '_multiplier')) / length
                actual = value(r, prefix + '_shield')
                close(active[previous] + increment, actual)
                active[previous] = actual
            active['split'] |= bool(r['split'])
            if not active['split']:
                before = sum(map(area, active['pieces']))
                pieces = [piece for old in active['pieces'] for piece in subtract(old, r['box'])]
                if before - sum(map(area, pieces)) != area(r['box']):
                    raise ValueError('overlapping or outside fringe shielding leaf')
                active['pieces'] = pieces
            leaves += 1
        else:
            begin = active['begin']
            for field in ('node1_id', 'node2_id', 'box', 'boundary', 'direction', 'reference_length',
                          'coupling_multiplier_hex', 'substrate_multiplier_hex', 'coefficient_hex',
                          'coupling_fraction_hex', 'substrate_fraction_hex', 'split'):
                if r[field] != begin[field]:
                    raise ValueError('fringe rule identity changed')
            close(active['last_c'], value(r, 'coupling_shield'))
            close(active['last_s'], value(r, 'substrate_shield'))
            weights = {}
            if not active['split']:
                for prefix in ('coupling', 'substrate'):
                    integrated = sum(measure(piece, r['boundary'], r['direction'], value(r, prefix + '_multiplier'))
                                     for piece in active['pieces'])
                    native = (value(r, prefix + '_fraction') - value(r, prefix + '_shield')) * length
                    close(integrated, native)
                    weights[prefix] = integrated
            else:
                unsupported += 1
            if emit is not None:
                emit(dict(cell=key[0], epoch=key[1], fringe_id=key[2],
                          node_ids=[r['node1_id'], r['node2_id']],
                          rectangles=active['pieces'] if not active['split'] else None,
                          integrated_weights=weights, rectilinear_support_verified=not active['split'],
                          pointwise_capacitance_placement_qualified=False))
            rules += 1
            active = None
    if active is not None or len(epochs) != 1 or not rules:
        raise ValueError('one completed fringe extraction epoch required')
    return dict(fringe_rules=rules, shielding_leaves=leaves, unsupported_split_rules=unsupported,
                native_fringe_fraction_integrals_verified=True,
                all_rectilinear_fringe_support_verified=not unsupported,
                maximum_absolute_integral_comparison_error=max_error,
                diagnostic_relative_comparison_tolerance=5e-13,
                diagnostic_absolute_comparison_tolerance=1e-13,
                ground_placement_qualified=False, distributed_wire_R_qualified=False, release_ready=False)
