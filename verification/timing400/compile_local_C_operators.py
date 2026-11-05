#!/usr/bin/env python3
"""Compile aligned Magic traces to owned local charge-energy operators.

Coordinates are native 5 nm units. Coefficients use native capacitance units
(1e-18 F). A, L and F rows represent integrals of (Va - Vb)^2. Signed
shielding terms are retained. Field 0 is an explicit substrate reference;
it is not an interior well voltage. This does not qualify the global matrix.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import time

from verify_magic_C_kernel_trace_v2 import blocks, box_area, line_length, close


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


def project(edge, patch):
    if edge[0] == edge[2]:
        return [edge[0], patch[1], edge[2], patch[3]]
    assert edge[1] == edge[3]
    return [patch[0], edge[1], patch[2], edge[3]]


def outward_clip(edge, patch, direction):
    p = list(patch)
    if direction == 1:
        p[2] = min(p[2], edge[0])
    elif direction == 2:
        p[1] = max(p[1], edge[1])
    elif direction == 4:
        p[0] = max(p[0], edge[0])
    elif direction == 8:
        p[3] = min(p[3], edge[1])
    else:
        raise AssertionError(direction)
    assert p[0] <= p[2] and p[1] <= p[3], (edge, patch, direction)
    return p


def fringe_integral(edge, patch, direction, cap, mult):
    p = outward_clip(edge, patch, direction)
    if direction == 1:
        near, far = edge[0]-p[2], edge[0]-p[0]
    elif direction == 2:
        near, far = p[1]-edge[1], p[3]-edge[1]
    elif direction == 4:
        near, far = p[0]-edge[0], p[2]-edge[0]
    else:
        near, far = edge[1]-p[3], edge[1]-p[1]
    assert 0 <= near <= far and mult >= 0
    return cap * line_length(project(edge, p)) * .6366 * (
        math.atan(mult*far)-math.atan(mult*near))


def local_ops(block, pair):
    """Return geometry-only pieces; caller supplies the two voltage fields.

    A: area patch, coefficient. L: source/target edges, coefficient,
    source/target inward BD directions. F: source edge, target area,
    outward BD direction, coefficient and arctan multiplier.
    """
    def v(tag, rule=0):
        rows = [x for n, x in block['values'][tag] if n == rule]
        assert len(rows) == 1, (tag, rule)
        return rows[0]
    def r(tag):
        rows = block['rects'][tag]
        assert len(rows) == 1 and not rows[0]['split']
        return rows[0]['box']
    kind, direction = block['kind'], block['direction']
    a = r('BASE_A')
    if kind == 'AREA':
        assert not pair
        yield ['A', a, v('AREA_DENSITY')[1]]
    elif kind == 'EDGE':
        assert not pair
        inside = {0: 2, 1: 1, 2: 8, 3: 4}[direction]
        yield ['L', a, a, v('EDGE_DENSITY')[1], inside, 0]
    elif kind == 'OVERLAP':
        density = v('OVERLAP_BASE')[2 if pair else 1] * (1 if pair else -1)
        yield ['A', a, density]
        for shield in block['rects']['AREA_SHIELD']:
            assert shield['rule'] == 0 and not shield['split']
            yield ['A', shield['box'], -density]
    elif kind == 'FRINGE_HALO':
        b = r('BASE_B')
        base = v('FRINGE_BASE')
        if not pair:
            ground = v('GROUND_PHYSICAL')
            yield ['L', project(a, b), project(a, b), -ground[4]*base[6], direction, 0]
        for rule, rv in block['values']['HALO_RULE']:
            if not v('HALO_RULE_REMAINING', rule)[2]:
                continue
            if pair:
                yield ['F', a, outward_clip(a, b, direction), direction, rv[0], base[3]]
            rr = [x for x in block['rects']['FRINGE_SHIELD'] if x['rule'] == rule]
            vv = [x for n, x in block['values']['FRINGE_SHIELD_GEOMETRY'] if n == rule]
            assert len(rr) == len(vv)
            for shield, sv in zip(rr, vv):
                assert not shield['split']
                box = shield['box']
                if pair:
                    yield ['F', a, outward_clip(a, box, direction), direction, -rv[0], sv[4]]
                else:
                    density = ground[4]*.6366*(math.atan(sv[5]*sv[3])-math.atan(sv[5]*sv[2]))
                    yield ['L', project(a, box), project(a, box), density, direction, 0]
    elif kind == 'BLOCKED_FRINGE':
        assert not pair
        base = v('BLOCKED_BASE')
        yield ['L', a, a, -base[4]*(1-base[3]), direction, 0]
    elif kind == 'SIDEWALL':
        assert pair
        separation = v('SIDEWALL_BASE')[1]
        density = math.fsum(x[0]/(separation+x[1]) for _, x in block['values']['SIDEWALL_RULE'])
        opposite = {1: 4, 2: 8, 4: 1, 8: 2}[direction]
        yield ['L', a, r('BASE_B'), density, direction, opposite]
    else:
        raise AssertionError(('unsupported actual kernel', kind))


def integral(op):
    if op[0] == 'A':
        return box_area(op[1])*op[2]
    if op[0] == 'L':
        assert line_length(op[1]) == line_length(op[2])
        return line_length(op[1])*op[3]
    assert op[0] == 'F'
    return fringe_integral(*op[1:])


def compile_trace(trace, output, deadline, allowed=None):
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    output.mkdir(parents=True, exist_ok=False)
    ids = json.loads((trace/'node_ids.json').read_text())
    types, planes = {}, {}
    def surfaces():
        with (trace/'surfaces.log').open() as stream:
            for line in stream:
                f = line.split()
                if f[0] in ['TYPE', 'PLANE']:
                    (types if f[0] == 'TYPE' else planes)[int(f[1])] = json.loads(' '.join(f[2:]))
                elif f[0] == 'SURFACE':
                    yield f
    def natives():
        with (trace/'contributions.log').open() as stream:
            for line in stream:
                if line.startswith(('OPENPLL_G ', 'OPENPLL_P ')):
                    yield line.split()
    native, surface = iter(natives()), iter(surfaces())
    fields = {('@SUBSTRATE_REFERENCE', 'reference', 'reference'): 0}
    count, reason, residual_abs = Counter(), Counter(), defaultdict(float)
    collapse = defaultdict(lambda: [0., 0., 0.])
    def field(pointer, p, t):
        name = ids[pointer]
        if name == '@SUBSTRATE':
            name = 'VGND'
        key = (name, planes[int(p)], types[int(t)])
        assert allowed is None or key in allowed, key
        if key not in fields:
            fields[key] = len(fields)
        return fields[key]
    opfile = output/'operators.jsonl'
    with opfile.open('w', buffering=1024*1024) as stream:
        for block in blocks(trace/'kernels.log'):
            count['kernels'] += 1
            if count['kernels'] % 10000 == 0:
                assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
                save(output/'status.json', dict(state='running', counts=dict(count), deadline_uptime=deadline))
            if not block['events']:
                count['native_kernels_without_nonzero_events'] += 1
                continue
            assert all(not x['split'] for rows in block['rects'].values() for x in rows)
            for event in block['events']:
                count['events'] += 1
                n, s = next(native), next(surface)
                pair = n[0] == 'OPENPLL_P'
                assert s[:3] == ['SURFACE', str(count['events']), 'P' if pair else 'G']
                assert event[1:4] == [str(count['events']), s[2], str(block['id'])]
                a = field(n[1], s[3], s[5])
                b = field(n[2], s[6], s[8]) if pair else 0
                delta = float(n[3] if pair else n[2])
                pieces = list(local_ops(block, pair))
                total = math.fsum(integral(op) for op in pieces)
                # Independently recorded native physical total, before accumulator loss.
                tag = {'AREA': 'AREA_DENSITY', 'EDGE': 'EDGE_DENSITY',
                    'OVERLAP': 'OVERLAP_REMAINING', 'FRINGE_HALO': 'PAIR_PHYSICAL' if pair else 'GROUND_PHYSICAL',
                    'SIDEWALL': 'SIDEWALL_BASE', 'BLOCKED_FRINGE': 'BLOCKED_BASE'}[block['kind']]
                vv = block['values'][tag][0][1]
                if block['kind'] in ['AREA', 'EDGE']:
                    expected = vv[0]*vv[1]
                elif block['kind'] == 'OVERLAP':
                    bv = block['values']['OVERLAP_BASE'][0][1]
                    expected = vv[0]*bv[2 if pair else 1]*(1 if pair else -1)
                elif block['kind'] == 'FRINGE_HALO':
                    expected = vv[0]*(1 if pair else -1)
                elif block['kind'] == 'BLOCKED_FRINGE':
                    expected = -vv[5]
                else:
                    expected = math.fsum(x[0]*vv[0]/(vv[1]+x[1]) for _, x in block['values']['SIDEWALL_RULE'])
                close(total, expected)
                residue = delta-total
                residual_abs[event[4]] += abs(residue)
                key = tuple(sorted((a, b)))
                row = collapse[key]
                row[0] += delta
                row[1] += total
                row[2] += abs(residue)
                reason[event[4]] += 1
                for op in pieces:
                    # Event serial is retained to make each signed piece auditable.
                    stream.write(json.dumps([op[0], a, b, count['events'], *op[1:]], separators=(',', ':'))+'\n')
                    count['operators'] += 1
                    count['operator_'+op[0]] += 1
        assert next(native, None) is None and next(surface, None) is None
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(output/'fields.json', [list(k) for k, _ in sorted(fields.items(), key=lambda kv: kv[1])])
    save(output/'collapsed_matrix_ledger.json', [[*k, *v] for k, v in sorted(collapse.items())])
    inputs = [Path(__file__), Path(__file__).with_name('verify_magic_C_kernel_trace_v2.py'),
        *[trace/n for n in ['node_ids.json', 'kernels.log', 'surfaces.log', 'contributions.log']]]
    receipt = dict(local_operator_integrals_match_native_physical_totals=True,
        aligned_events_have_owned_voltage_fields=True, counts=dict(count), components=dict(reason),
        arithmetic_residual_absolute_native_cap_units=dict(residual_abs), voltage_fields=len(fields),
        native_self_conductor_pair_omission_convention_preserved=True,
        implicit_ground_return='explicit substrate reference, original conductor VGND at zero wire R',
        units=dict(length_m=5e-9, capacitance_F=1e-18), deadline_uptime=deadline,
        full_C_energy_matrix_assembled=False, global_passivity_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False,
        input_sha256={str(p.resolve()): digest(p) for p in inputs},
        artifacts={str(p.resolve()): digest(p) for p in [opfile, output/'fields.json', output/'collapsed_matrix_ledger.json']})
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(output/'assessment.json', receipt)
    save(output/'status.json', dict(state='completed', counts=dict(count), deadline_uptime=deadline))
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--trace', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--owner', type=Path, required=True)
    parser.add_argument('--domains', type=Path)
    args = parser.parse_args()
    deadline = json.loads(args.owner.read_text())['deadline_uptime']
    allowed = None
    if args.domains:
        allowed = set()
        for line in args.domains.open():
            r = json.loads(line)
            allowed.add((r['original_conductor'], r['plane'], r['effective_material']))
    compile_trace(args.trace, args.output, deadline, allowed)


if __name__ == '__main__':
    main()
