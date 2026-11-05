#!/usr/bin/env python3
"""Compare repeated-name native graph fingerprints without selecting snapshots."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import shlex
import time
from pathlib import Path
from common import save, sha
from resources import lease


def fingerprint(nodes, branches):
    keys = list(nodes.values())
    if len(set(keys)) != len(keys):
        return None
    edges = Counter()
    for a, b, *values in branches.values():
        ends = tuple(sorted((nodes[a], nodes[b])))
        edges[ends, tuple(values)] += 1
    encoded = json.dumps([sorted(keys), sorted((key, count) for key, count in edges.items())],
                         separators=(',', ':')).encode()
    return hashlib.sha256(encoded).hexdigest()


def scan(job):
    path, start, end, deadline = job
    result = []
    current = None
    with Path(path).open('rb') as stream:
        stream.seek(start)
        while stream.tell() < end:
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('snapshot inventory deadline')
            line = stream.readline().decode()
            f = shlex.split(line)
            if f[0] == 'BEGIN':
                if current is not None:
                    raise ValueError('nested snapshot')
                current = dict(group=f[1], original=f[2], nodes={}, branches={})
                pending = None
            elif f[0] == 'TYPE':
                if current is not None:
                    raise ValueError('type inside snapshot')
            else:
                if current is None or f[1] != current['group']:
                    raise ValueError('snapshot identity mismatch')
                if f[0] == 'NODE':
                    if len(f) != 8 or f[2] in current['nodes']:
                        raise ValueError('duplicate/malformed native node')
                    current['nodes'][f[2]] = (f[3], *map(int, f[4:]))
                elif f[0] == 'BRANCH':
                    if pending is not None:
                        raise ValueError('missing edge')
                    pending = f[3]
                elif f[0] == 'EDGE':
                    if pending is None or len(f) != 8:
                        raise ValueError('malformed branch/edge pair')
                    row = tuple(f[3:])
                    old = current['branches'].setdefault(pending, row)
                    if old != row:
                        raise ValueError('inconsistent repeated branch pointer')
                    pending = None
                elif f[0] == 'END':
                    if pending is not None:
                        raise ValueError('unfinished branch')
                    result.append(dict(group=current['group'], original=current['original'],
                        nodes=len(current['nodes']), branches=len(current['branches']),
                        fingerprint=fingerprint(current['nodes'], current['branches'])))
                    current = None
                else:
                    raise ValueError('unknown native graph record')
    if current is not None:
        raise ValueError('incomplete graph range')
    return result


def run(args):
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    source = args.domain.resolve()/'trace/R_provenance.log'
    receipt = args.domain.resolve()/'assessment.json'
    report = json.loads(receipt.read_text())
    expected = report['artifacts'][str(source)]
    save(out/'status.json', dict(state='checking_and_partitioning_native_snapshots', release_qualified=False))
    with lease(8, 16, deadline):
        offsets = []
        h = hashlib.sha256()
        with source.open('rb') as stream:
            while True:
                position = stream.tell()
                line = stream.readline()
                if not line:
                    break
                h.update(line)
                if line.startswith(b'BEGIN '):
                    offsets.append(position)
        if h.hexdigest() != expected or not offsets:
            raise ValueError('source identity mismatch or empty graph stream')
        boundaries = [offsets[len(offsets)*i//8] for i in range(8)]+[source.stat().st_size]
        save(out/'status.json', dict(state='comparing_all_native_graphs', workers=8, release_qualified=False))
        with ProcessPoolExecutor(max_workers=8) as pool:
            rows = sum(pool.map(scan, [(str(source), a, b, deadline) for a,b in zip(boundaries,boundaries[1:])]), [])
        if len(rows) != len(offsets) or len({r['group'] for r in rows}) != len(rows):
            raise ValueError('incomplete or duplicate snapshot coverage')
        grouped = defaultdict(list)
        for row in rows:
            grouped[row['original']].append(row)
        repeated = {k:v for k,v in grouped.items() if len(v)>1}
        classifications = Counter()
        for entries in repeated.values():
            kind = ('ambiguous_node_identity' if any(r['fingerprint'] is None for r in entries)
                    else 'same_exported_graph_fingerprint' if len({r['fingerprint'] for r in entries}) == 1
                    else 'different_exported_graphs')
            classifications[kind] += 1
        save(out/'groups.json', rows)
        save(out/'repeated_names.json', repeated)
        save(out/'assessment.json', dict(native_groups=len(rows), original_names=len(grouped),
            repeated_names=len(repeated), classifications=dict(classifications),
            input_sha256={str(source):expected,str(receipt):sha(receipt),str(Path(__file__).resolve()):sha(Path(__file__))},
            artifacts={str(out/n):sha(out/n) for n in ('groups.json','repeated_names.json')},
            snapshot_selection_qualified=False, snapshots_dropped=0, release_qualified=False))
        save(out/'status.json', dict(state='snapshot_graph_inventory_complete', release_qualified=False))
        print(json.dumps(dict(native_groups=len(rows), repeated_names=len(repeated), classifications=dict(classifications))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--domain', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    run(p.parse_args())
