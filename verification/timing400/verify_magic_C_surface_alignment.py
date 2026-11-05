#!/usr/bin/env python3
"""Verify one native surface record per unchanged C contribution in order."""
from collections import Counter
from pathlib import Path
import shlex


def validate_surface(fields, index, kind, planes, types, unlocated=False):
    assert len(fields) == 9 and fields[:3] == ['SURFACE', str(index), kind], (index, fields)
    values = list(map(int, fields[3:]))
    if unlocated:
        assert kind == 'G' and values == [-1]*6
        return values
    assert values[0] in planes and values[1] >= 0 and values[2] in types, (index, values)
    if kind == 'G':
        assert values[3:] == [-1]*3
    else:
        assert values[3] in planes and values[4] >= 0 and values[5] in types, (index, values)
    return values


def verify_alignment(contributions, surface):
    types, planes, by_kind, pairs, unknown = {}, {}, Counter(), Counter(), 0
    began = ended = False
    count = 0
    with Path(surface).open() as auxiliary:
        def next_record():
            nonlocal began, ended
            for line in auxiliary:
                f = line.split()
                assert f and not ended
                if f[0] == 'BEGIN':
                    assert not began
                    began = True
                elif f[0] in ['TYPE', 'PLANE']:
                    assert began and count == 0
                    row = shlex.split(line)
                    assert len(row) == 3
                    table = types if f[0] == 'TYPE' else planes
                    assert int(row[1]) not in table
                    table[int(row[1])] = row[2]
                elif f[0] == 'SURFACE':
                    assert began and types and planes
                    return f
                else:
                    assert f == ['END', str(count)]
                    ended = True
            return None
        with Path(contributions).open() as original:
            for line in original:
                if not line.startswith(('OPENPLL_G ', 'OPENPLL_P ')):
                    continue
                row = line.split()
                count += 1
                kind = row[0][-1]
                unlocated = kind == 'G' and row[4] == 'unlocated'
                if unlocated:
                    assert row[3] == 'output_zero_clamp'
                fields = next_record()
                assert fields is not None, ('missing surface record', count)
                values = validate_surface(fields, count, kind, planes, types, unlocated)
                by_kind[kind] += 1
                if unlocated:
                    unknown += 1
                else:
                    pairs[(planes[values[0]], types[values[2]],
                        planes[values[3]] if kind == 'P' else '$SUB',
                        types[values[5]] if kind == 'P' else '$SUB')] += 1
                if count == 1:
                    # A displaced serial ID cannot silently associate a C with
                    # the next surface. Test the guard on the actual first row.
                    wrong = list(fields)
                    wrong[1] = str(count+1)
                    try:
                        validate_surface(wrong, count, kind, planes, types, unlocated)
                    except AssertionError:
                        pass
                    else:
                        raise AssertionError('displaced surface serial accepted')
        assert next_record() is None and began and ended and count > 0
    return dict(events=count, by_kind=dict(by_kind), unlocated_clamp_events=unknown,
        surface_material_pairs=[dict(plane_a=k[0], material_a=k[1], plane_b=k[2], material_b=k[3], events=v)
                                for k, v in sorted(pairs.items())],
        complete_one_to_one_surface_alignment=True, displaced_surface_serial_rejected=True)
