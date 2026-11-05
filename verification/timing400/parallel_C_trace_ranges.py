"""Byte ranges aligned across native kernel, owner, surface and scalar streams."""
from collections import defaultdict
import json
import math
from pathlib import Path
import re
import time

from verify_magic_C_kernel_trace_v2 import check_event


def lines(path, span=None):
    with Path(path).open('rb') as stream:
        if span:
            stream.seek(span[0])
        remaining = span[1]-span[0] if span else None
        for row in stream:
            if remaining == 0:
                break
            if span:
                remaining -= len(row)
                assert remaining >= 0, ('split record', path, span)
            yield row.decode()
        assert remaining is None or remaining == 0, ('truncated range', path, span)


def find_record(path, offset, prefix):
    """Find the next complete prefixed line without mapping huge files."""
    with Path(path).open('rb') as stream:
        if offset:
            stream.seek(offset-1)
            if stream.read(1) != b'\n':
                stream.readline()
        while True:
            base = stream.tell()
            chunk = stream.read(1024*1024)
            if not chunk:
                return Path(path).stat().st_size, None
            # Complete the last line so a record cannot straddle scans.
            if not chunk.endswith(b'\n'):
                chunk += stream.readline()
            at = 0 if chunk.startswith(prefix) else chunk.find(b'\n'+prefix)
            if at >= 0:
                at += int(not chunk.startswith(prefix))
                return base+at, chunk[at:chunk.index(b'\n', at)].decode()


def lower_bound(path, prefix, target):
    """First OWNER/SURFACE with serial >= target; END is the sentinel."""
    size = Path(path).stat().st_size
    lo, hi = 0, size
    with Path(path).open('rb') as stream:
        while hi-lo > 1024*1024:
            mid = (lo+hi)//2
            stream.seek(mid)
            stream.readline()
            row = stream.readline().split()
            key = int(row[1]) if row and row[0] == prefix else float('inf')
            if key < target:
                lo = stream.tell()
            else:
                hi = mid
        stream.seek(max(0, lo-1))
        if lo and stream.read(1) != b'\n':
            stream.readline()
        for row in iter(stream.readline, b''):
            start = stream.tell()-len(row)
            fields = row.split()
            if fields[0] == b'END' or (fields[0] == prefix and int(fields[1]) >= target):
                return start
    raise AssertionError(('missing end record', path))


def native_offsets(path, ranks, deadline):
    """Locate event ranks with C-level chunk counting, not Python per line."""
    wanted = sorted(set(ranks))
    result, count = {}, 0
    pattern = re.compile(rb'(?:^|\n)(OPENPLL_[GP] )')
    with Path(path).open('rb') as stream:
        while True:
            assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
            base = stream.tell()
            chunk = stream.read(8*1024*1024)
            if not chunk:
                break
            if not chunk.endswith(b'\n'):
                chunk += stream.readline()
            n = chunk.count(b'\nOPENPLL_G ')+chunk.count(b'\nOPENPLL_P ')
            n += int(chunk.startswith((b'OPENPLL_G ', b'OPENPLL_P ')))
            targets = [r for r in wanted if count <= r < count+n]
            if targets:
                for i, match in enumerate(pattern.finditer(chunk), count):
                    if i in targets:
                        result[i] = base+match.start(1)
            count += n
        if count in wanted:
            result[count] = stream.tell()
    assert set(result) == set(wanted), (wanted, result, count)
    return result, count


def partition(trace, workers, deadline):
    path = trace/'kernels.log'
    size = path.stat().st_size
    end, footer = find_record(path, max(0, size-1024), b'END ')
    _, event_total, kernel_total = footer.split()
    event_total, kernel_total = int(event_total), int(kernel_total)
    _, surface_footer = find_record(trace/'surfaces.log', max(0, (trace/'surfaces.log').stat().st_size-1024), b'END ')
    _, owner_footer = find_record(trace/'owners.log', max(0, (trace/'owners.log').stat().st_size-1024), b'END ')
    assert surface_footer.split() == ['END', str(event_total)]
    assert int(owner_footer.split()[2]) == kernel_total
    boundaries = []
    for i in range(workers):
        offset, row = find_record(path, size*i//workers, b'KERNEL ')
        assert row is not None
        kernel = int(row.split()[1])
        _, event = find_record(path, offset, b'EVENT ')
        event_start = int(event.split()[1])-1 if event else event_total
        boundaries.append((offset, kernel, event_start))
    boundaries.append((end, kernel_total+1, event_total))
    assert boundaries[0][1:] == (1, 0)
    assert all(a[1] < b[1] and a[2] <= b[2] for a, b in zip(boundaries, boundaries[1:]))
    offsets, counted = native_offsets(trace/'contributions.log', [b[2] for b in boundaries], deadline)
    assert counted == event_total
    result = []
    for a, b in zip(boundaries, boundaries[1:]):
        result.append(dict(kernel_start=a[1], kernel_end=b[1], event_start=a[2], event_end=b[2],
            kernels=[a[0], b[0]], contributions=[offsets[a[2]], offsets[b[2]]],
            owners=[lower_bound(trace/'owners.log', b'OWNER', k) for k in (a[1], b[1])],
            surfaces=[lower_bound(trace/'surfaces.log', b'SURFACE', e+1) for e in (a[2], b[2])]))
    with (trace/'surfaces.log').open('rb') as stream:
        stream.seek(result[-1]['surfaces'][1])
        assert stream.readline().decode().split() == ['END', str(event_total)]
    with (trace/'owners.log').open('rb') as stream:
        stream.seek(result[-1]['owners'][1])
        assert stream.readline().decode().strip() == owner_footer
    result[-1]['expected_owner_total'] = int(owner_footer.split()[1])
    return result


def metadata(trace):
    residues, types, planes = {}, {}, {}
    for line in lines(trace/'surfaces.log'):
        if line.startswith(('TYPE ', 'PLANE ')):
            kind, key, value = line.split(maxsplit=2)
            (types if kind == 'TYPE' else planes)[int(key)] = json.loads(value)
        elif line.startswith('SURFACE '):
            f = line.split()
            for i in (3, 6):
                if f[i] != '-1':
                    key, value = (int(f[i]), int(f[i+1])), int(f[i+2])
                    assert residues.get(key, value) == value
                    residues[key] = value
    return dict(types=types, planes=planes, residues=[[p, raw, v] for (p, raw), v in sorted(residues.items())])


def ranged_owned_blocks(trace, deadline, spec):
    def owners():
        last = spec['kernel_start']-1
        for text in lines(trace/'owners.log', spec['owners']):
            f = text.split()
            assert len(f) == 11 and f[0] == 'OWNER' and int(f[10]) in (0, 1)
            key = int(f[1])
            assert last < key < spec['kernel_end']
            last = key
            row = dict(kernel_id=key, a=f[2], b=f[3], source=list(map(int, f[4:7])),
                       target=list(map(int, f[7:10])), same_ideal_conductor=bool(int(f[10])))
            assert row['same_ideal_conductor'] == (row['a'] == row['b'])
            yield row
    rows = iter(owners())
    pending = next(rows, None)
    for count, block in enumerate(ranged_blocks(trace/'kernels.log', spec), 1):
        if count % 10000 == 0:
            assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
        owner = None
        if pending and pending['kernel_id'] == block['id']:
            owner, pending = pending, next(rows, None)
        assert not pending or pending['kernel_id'] > block['id']
        assert (owner is not None) == (block['kind'] in ['OVERLAP', 'FRINGE_HALO', 'SIDEWALL'])
        yield block, owner
    assert pending is None and next(rows, None) is None
def ranged_blocks(path, spec):
    current = None
    kernels, events = spec["kernel_start"]-1, spec["event_start"]
    began, ended = True, False
    if True:
        for line in lines(path, spec['kernels']):
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
                raise AssertionError(('unexpected range record', f))
    if current is not None:
        yield current
    assert kernels == spec['kernel_end']-1 and events == spec['event_end']
