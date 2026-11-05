#!/usr/bin/env python3
"""Compare repeated native R groups without merging conductor-name aliases.

Exact pointer-independent printed-node/incident-edge fingerprints are diagnostic
only: equal electrical records do not prove equal tile/contact coverage or select
which extraction lifetime belongs to the final exported topology.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shlex
import signal
import time

from common import save, sha
from resources import lease


def fingerprint(group):
    nodes = group['nodes']
    labels = list(nodes.values())
    if len(set(labels)) != len(labels):
        # Do not mistake a coarser quotient graph for an equivalence proof.
        return dict(native_group_id=group['id'], original_conductor=group['name'],
                    nodes=len(nodes), incident_edges=len(group['edges']),
                    ambiguous_node_labels=True, fingerprint=None)
    edges = Counter()
    for owner, a, b, value, material, status in group['edges']:
        if owner not in (a, b) or any(p not in nodes for p in (owner, a, b)):
            raise ValueError('unbound native incident edge')
        ends = tuple(sorted((nodes[a], nodes[b])))
        edges[ends, value, material, status] += 1
    payload = dict(nodes=sorted(labels), incident_edges=sorted((*key, count) for key, count in edges.items()))
    return dict(native_group_id=group['id'], original_conductor=group['name'],
                nodes=len(nodes), incident_edges=len(group['edges']), ambiguous_node_labels=False,
                fingerprint=hashlib.sha256(json.dumps(payload, separators=(',', ':')).encode()).hexdigest())


def groups(lines, deadline=None):
    group = None
    seen = set()
    for count, raw in enumerate(lines):
        if deadline is not None and count % 10000 == 0 and time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            raise TimeoutError('native group audit exhausted whole-check budget')
        line = raw.decode() if isinstance(raw, bytes) else raw
        kind = line.split(None, 1)[0]
        if kind == 'TYPE':
            if group is not None:
                raise ValueError('TYPE inside group')
            continue
        if kind == 'BEGIN':
            f = shlex.split(line)
            if group is not None or len(f) != 3 or f[1] in seen:
                raise ValueError('duplicate or nested native group')
            seen.add(f[1])
            group = dict(id=f[1], name=f[2], nodes={}, edges=[])
            continue
        f = shlex.split(line) if kind == 'NODE' else line.split()
        if group is None or len(f) < 2 or f[1] != group['id']:
            raise ValueError('native group alignment')
        if kind == 'NODE':
            if len(f) != 8 or f[2] in group['nodes']:
                raise ValueError('invalid or duplicate native node')
            group['nodes'][f[2]] = tuple(f[3:])
        elif kind == 'EDGE':
            if len(f) != 8:
                raise ValueError('invalid native edge')
            group['edges'].append(tuple(f[2:]))
        elif kind == 'BRANCH':
            if len(f) != 4:
                raise ValueError('invalid native branch')
        elif kind == 'END':
            if len(f) != 2:
                raise ValueError('invalid group terminator')
            yield fingerprint(group)
            group = None
        else:
            raise ValueError('unknown native group record')
    if group is not None:
        raise ValueError('unclosed native group')


def run(source, output):
    source, out = Path(source).resolve(), Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    started = time.clock_gettime(time.CLOCK_BOOTTIME)
    deadline = started + 43200
    def expired(*_):
        raise TimeoutError('native group audit exhausted whole-check budget')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.alarm(43200)
    save(out / 'status.json', dict(state='waiting_for_resources', release_qualified=False))
    try:
        with lease(1, 4, deadline):
            initial = source.stat()
            digest = hashlib.sha256()
            def lines():
                with source.open('rb') as stream:
                    for line in stream:
                        digest.update(line)
                        yield line
            by_name = defaultdict(list)
            total = 0
            for row in groups(lines(), deadline):
                total += 1
                by_name[row['original_conductor']].append(row)
                if total % 100 == 0:
                    save(out / 'status.json', dict(state='comparing_native_group_records',
                         groups=total, elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started,
                         release_qualified=False))
            final = source.stat()
            identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            if identity(initial) != identity(final):
                raise ValueError('native trace changed during audit')
            repeated = {name: rows for name, rows in by_name.items() if len(rows) > 1}
            records = [dict(original_conductor=name, groups=rows,
                       all_printed_node_incident_edge_fingerprints_match=(
                           all(r['fingerprint'] is not None for r in rows) and
                           len({r['fingerprint'] for r in rows}) == 1))
                       for name, rows in sorted(repeated.items())]
            save(out / 'repeated_groups.json', records)
            report = dict(input_sha256={str(source):digest.hexdigest(),
                          str(Path(__file__).resolve()):sha(Path(__file__)),
                          **{str(Path(__file__).with_name(n).resolve()):sha(Path(__file__).with_name(n))
                             for n in ('common.py', 'resources.py')}},
                 artifacts={str(out / 'repeated_groups.json'):sha(out / 'repeated_groups.json')},
                 native_groups=total, unique_conductor_labels=len(by_name), repeated_conductor_labels=len(records),
                 repeated_labels_with_matching_electrical_fingerprints=sum(
                     r['all_printed_node_incident_edge_fingerprints_match'] for r in records),
                 scope='exact printed-node and incident-edge diagnostic, not domain or final-lifetime selection',
                 physical_domain_complete=False, runtime_model_eligible=False, release_qualified=False,
                 elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started)
            save(out / 'assessment.json', report)
            save(out / 'status.json', dict(state='diagnostic_complete_pending_final_topology_reconciliation',
                                          release_qualified=False))
            return report
    except BaseException as error:
        save(out / 'status.json', dict(state='failed', reason=repr(error), release_qualified=False))
        raise
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(run(a.source, a.output)))


if __name__ == '__main__':
    main()
