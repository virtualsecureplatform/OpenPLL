#!/usr/bin/env python3
"""Stream aligned local kernels and reconstruct their native physical integrals.

Separate accumulator/zero-clamp residuals from physical kernel capacitance.
Successful accounting is not qualification of spatial weights or RC accuracy.
"""
from collections import Counter, defaultdict
import math
from pathlib import Path


def check_event(fields, serial, kind, kernel_id):
    assert len(fields) == 5 and fields[:4] == ['EVENT', str(serial), kind, str(kernel_id)], fields
    assert kernel_id > 0 and fields[4] != 'MISSING'


def blocks(path):
    current = None
    kernels = events = 0
    began = ended = False
    with Path(path).open() as stream:
        for line in stream:
            f = line.split()
            assert f and not ended
            if f[0] == 'BEGIN':
                assert not began
                began = True
            elif f[0] == 'KERNEL':
                assert began and len(f) == 4 and int(f[1]) == kernels+1
                if current is not None:
                    yield current
                kernels += 1
                current = dict(id=kernels, kind=f[2], direction=int(f[3]), rects=defaultdict(list), values=defaultdict(list), events=[])
            elif f[0] == 'RECT':
                assert current and len(f) == 10 and int(f[1]) == current['id']
                row = dict(rule=int(f[3]), split=int(f[4]), dinfo=int(f[5]), box=list(map(int, f[6:10])))
                l, b, r, t = row['box']
                assert l <= r and b <= t
                current['rects'][f[2]].append(row)
            elif f[0] == 'VALUE':
                assert current and len(f) == 12 and int(f[1]) == current['id']
                v = list(map(float, f[4:]))
                assert all(math.isfinite(x) for x in v)
                current['values'][f[2]].append((int(f[3]), v))
            elif f[0] == 'EVENT':
                assert current
                events += 1
                check_event(f, events, f[2], current['id'])
                current['events'].append(f)
            else:
                assert f == ['END', str(events), str(kernels)]
                if current is not None:
                    yield current
                current = None
                ended = True
    assert began and ended and kernels and events


def close(a, b):
    assert abs(a-b) <= 1e-8+2e-12*max(abs(a), abs(b)), (a, b)


def box_area(box):
    l, b, r, t = box
    return (r-l)*(t-b)


def line_length(box):
    l, b, r, t = box
    assert l == r or b == t, box
    return (r-l)+(t-b)


def fringe_geometry(source, target, values, direction):
    length, near, far = values[:3]
    if source[0] == source[2]:
        assert source[1] <= target[1] <= target[3] <= source[3]
        assert target[3]-target[1] == length
        # BD_LEFT=0, BD_RIGHT=1 in Magic's Boundary definitions.
        distances = [(max(0, source[0]-target[2]), source[0]-target[0]),
                     (max(0, target[0]-source[2]), target[2]-source[2])]
    else:
        assert source[1] == source[3]
        assert source[0] <= target[0] <= target[2] <= source[2]
        assert target[2]-target[0] == length
        distances = [(max(0, source[1]-target[3]), source[1]-target[1]),
                     (max(0, target[1]-source[3]), target[3]-source[3])]
    # Select the nonnegative directed near/far interval without relying on
    # copied enum numbers; vertical/horizontal direction is independently fixed.
    assert (near, far) in distances and 0 <= near <= far, (source, target, values, direction)


def verify_kernels(contributions, kernels):
    def actual_events():
        with Path(contributions).open() as stream:
            for line in stream:
                if line.startswith(('OPENPLL_G ', 'OPENPLL_P ')):
                    yield line.split()
    actual = iter(actual_events())
    counts, kinds, components = Counter(), Counter(), Counter()
    residual_abs = defaultdict(float)
    max_residual = 0.0
    wrong_id_rejected = edge_fault = fringe_fault = False
    for block in blocks(kernels):
        kind = block['kind']
        kinds[kind] += 1
        counts['kernels'] += 1
        counts['split_rectangles'] += sum(r['split'] != 0 for rows in block['rects'].values() for r in rows)
        if not block['events']:
            counts['kernels_without_nonzero_contribution'] += 1
            continue
        def value(tag, rule=0):
            rows = [v for n, v in block['values'][tag] if n == rule]
            assert len(rows) == 1, (kind, tag, rule, len(rows))
            return rows[0]
        def rect(tag):
            rows = block['rects'][tag]
            assert len(rows) == 1
            return rows[0]['box']
        def area_shields(rule):
            rr = [r for r in block['rects']['AREA_SHIELD'] if r['rule'] == rule]
            vv = [v for n, v in block['values']['AREA_SHIELD_SIZE'] if n == rule]
            assert len(rr) == len(vv)
            for r, v in zip(rr, vv):
                assert v[0] == box_area(r['box'])//(2 if r['split'] else 1)
            return sum(v[0] for v in vv)
        physical = {}
        if kind == 'AREA':
            a, density = value('AREA_DENSITY')[:2]
            split = block['rects']['TILE'][0]['split']
            assert a == box_area(rect('BASE_A'))//(2 if split else 1)
            physical['AREA_GROUND'] = a*density
        elif kind in ['EDGE', 'DIAGONAL_EDGE']:
            length, density = value('EDGE_DENSITY')[:2]
            if kind == 'EDGE':
                assert line_length(rect('BASE_A')) == length
                if not edge_fault:
                    try:
                        assert line_length(rect('TILE')) == length
                    except AssertionError:
                        edge_fault = True
            else:
                counts['diagonal_kernels_requiring_additional_geometry_qualification'] += 1
            physical['EDGE_GROUND'] = length*density
        elif kind == 'OVERLAP':
            initial, ground_density, coupling_density = value('OVERLAP_BASE')[:3]
            assert initial == box_area(rect('BASE_A'))
            remaining = value('OVERLAP_REMAINING')[0]
            assert initial-area_shields(0) == remaining
            physical['OVERLAP_GROUND'] = -remaining*ground_density
            physical['OVERLAP_PAIR'] = remaining*coupling_density
        elif kind == 'FRINGE_HALO':
            base = value('FRINGE_BASE')
            length, near, far, pair_mult, sub_mult, pair_frac, sub_frac = base[:7]
            fringe_geometry(rect('BASE_A'), rect('BASE_B'), base, block['direction'])
            close(pair_frac, .6366*(math.atan(pair_mult*far)-math.atan(pair_mult*near)))
            close(sub_frac, .6366*(math.atan(sub_mult*far)-math.atan(sub_mult*near)))
            pair_total = sub_shield_total = 0.0
            for rule, rv in block['values']['HALO_RULE']:
                shield_pair = shield_sub = 0.0
                rr = [r for r in block['rects']['FRINGE_SHIELD'] if r['rule'] == rule]
                vv = [v for n, v in block['values']['FRINGE_SHIELD_GEOMETRY'] if n == rule]
                assert len(rr) == len(vv)
                for r, v in zip(rr, vv):
                    ll, total_length, nn, ff, mm_pair, mm_sub = v[:6]
                    assert total_length == length
                    fringe_geometry(rect('BASE_A'), r['box'], [ll, nn, ff], block['direction'])
                    shield_pair += .6366*(math.atan(mm_pair*ff)-math.atan(mm_pair*nn))*ll/total_length
                    shield_sub += .6366*(math.atan(mm_sub*ff)-math.atan(mm_sub*nn))*ll/total_length
                native_pair, native_sub, active = value('HALO_RULE_REMAINING', rule)[:3]
                close(native_pair, shield_pair)
                close(native_sub, shield_sub)
                if active:
                    pair_total += rv[0]*(pair_frac-native_pair)*length
                    sub_shield_total += native_sub
            if block['values']['PAIR_PHYSICAL']:
                pair = value('PAIR_PHYSICAL')[0]
                close(pair, pair_total)
                physical['FRINGE_PAIR'] = pair
            if block['values']['GROUND_PHYSICAL']:
                ground = value('GROUND_PHYSICAL')
                close(ground[3], sub_shield_total)
                close(ground[0], (ground[2]-ground[3])*ground[1]*ground[4])
                physical['FRINGE_GROUND'] = -ground[0]
        elif kind == 'FRINGE_LEGACY':
            length, initial = value('LEGACY_BASE')[:2]
            assert initial == box_area(rect('BASE_B'))
            pair_total = accounted = 0.0
            for rule, rv in block['values']['LEGACY_RULE']:
                remaining, active = value('LEGACY_RULE_REMAINING', rule)[:2]
                assert initial-area_shields(rule) == remaining
                pair_total += rv[0]*remaining if active else 0
                accounted += remaining
            if block['values']['PAIR_PHYSICAL']:
                pair = value('PAIR_PHYSICAL')[0]
                close(pair, pair_total)
                physical['FRINGE_PAIR'] = pair
            if block['values']['GROUND_PHYSICAL']:
                ground = value('GROUND_PHYSICAL')
                assert ground[2] == accounted
                close(ground[0], ground[4]*min(accounted, length))
                physical['FRINGE_GROUND'] = -ground[0]
        elif kind == 'BLOCKED_FRINGE':
            length, near, mult, snear, density, subcap = value('BLOCKED_BASE')[:6]
            assert line_length(rect('BASE_A')) == length
            close(snear, .6366*math.atan(mult*near))
            close(subcap, density*(1-snear)*length)
            physical['BLOCKED_GROUND'] = -subcap
        elif kind == 'SIDEWALL':
            length, separation, derived_length = value('SIDEWALL_BASE')[:3]
            assert line_length(rect('BASE_A')) == line_length(rect('BASE_B')) == length == derived_length
            physical['SIDEWALL_PAIR'] = sum(v[0]*length/(separation+v[1]) for _, v in block['values']['SIDEWALL_RULE'])
        elif kind == 'ROUNDING':
            physical['NODE_ROUNDING'] = 0.0
        else:
            raise AssertionError(kind)
        for event in block['events']:
            native = next(actual)
            counts['events'] += 1
            check_event(event, counts['events'], native[0][-1], block['id'])
            component = event[4]
            assert component in physical, (kind, component, block['values'].keys())
            components[component] += 1
            delta = float(native[2] if native[0] == 'OPENPLL_G' else native[3])
            residual = delta-physical[component]
            assert math.isfinite(residual)
            residual_abs[component] += abs(residual)
            max_residual = max(max_residual, abs(residual))
            if not wrong_id_rejected:
                damaged = list(event)
                damaged[3] = '0'
                try:
                    check_event(damaged, counts['events'], native[0][-1], block['id'])
                except AssertionError:
                    wrong_id_rejected = True
                assert wrong_id_rejected
            if kind == 'FRINGE_HALO' and native[0] == 'OPENPLL_P' and not fringe_fault:
                whole_target = list(map(int, native[10:14]))
                if whole_target != rect('BASE_B'):
                    try:
                        fringe_geometry(rect('BASE_A'), whole_target, value('FRINGE_BASE'), block['direction'])
                    except AssertionError:
                        fringe_fault = True
    assert next(actual, None) is None and counts['events'] and wrong_id_rejected
    return dict(counts=dict(counts), kernel_kinds=dict(kinds), component_counts=dict(components),
        complete_ordered_kernel_to_contribution_alignment=True, local_kernel_integrals_reconstructed=True,
        accumulator_and_clamp_residual_absolute_native_units=dict(residual_abs),
        maximum_absolute_native_unit_residual=max_residual, wrong_kernel_ID_control_rejected=wrong_id_rejected,
        whole_tile_perimeter_control_rejected=edge_fault, whole_target_fringe_control_rejected=fringe_fault,
        spatial_voltage_weights_or_roundoff_error_bound_qualified=False)
