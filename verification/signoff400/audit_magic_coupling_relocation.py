"""Classify coupling pairs using observed substrate identity and native updates."""
import json
import math
import argparse
from pathlib import Path
from collections import Counter, defaultdict
from audit_magic_coupling_geometry_trace import lines
from common_v3 import save, sha, verify


def audit(trace, relocation_sites):
    sums = defaultdict(float)
    counts = Counter()
    names = {}
    exported_pairs = set()
    pending_export = None
    substrates = set()
    relocations = []
    epochs = set()
    for line in lines(trace):
        r = json.loads(line)
        prefix = (r['cell'], r['epoch'])
        epochs.add(prefix)
        kind = r['kind']
        if kind in ('overlap', 'sidewall', 'sideoverlap_halo', 'sideoverlap_legacy'):
            key = (*prefix, *sorted((r['node1_id'], r['node2_id'])))
            value = float.fromhex(r['cap_native_hex'])
            if not math.isfinite(value):
                raise ValueError('nonfinite coupling')
            sums[key] += value
            counts[key] += 1
        elif kind == 'node_name':
            key = (*prefix, r['node_id'])
            if pending_export is None:
                pending_export = key
            else:
                if pending_export[:2] != prefix:
                    raise ValueError('mixed native coupling writer epoch')
                pair = (*prefix, *sorted((pending_export[2], key[2])))
                if pair in exported_pairs:
                    raise ValueError('duplicate native coupling writer pair')
                exported_pairs.add(pair)
                pending_export = None
        elif kind == 'ground_output':
            key = (*prefix, r['node_id'])
            if key in names:
                raise ValueError('duplicate native node output')
            names[key] = r['name']
            if r['substrate'] is True:
                substrates.add(key)
        elif kind == 'ground_update':
            if r['site'] in relocation_sites:
                if r['has_before'] is not True:
                    raise ValueError('relocation requires native before value')
                before, after = (float.fromhex(r[k]) for k in ('before_hex', 'after_hex'))
                if not math.isfinite(before) or not math.isfinite(after):
                    raise ValueError('nonfinite relocation')
                relocations.append(((*prefix, r['node_id']), before, after))
        else:
            raise ValueError('unknown combined trace event')
    if len(epochs) != 1 or len(substrates) != 1 or pending_export is not None:
        raise ValueError('one extraction epoch and observed substrate required')
    substrate = next(iter(substrates))
    classes = Counter()
    event_classes = Counter()
    expected = {}
    unresolved = []
    for key, value in sums.items():
        a, b = (*key[:2], key[2]), (*key[:2], key[3])
        if not value:
            tag = 'zero_sum'
        elif a == substrate or b == substrate:
            other = b if a == substrate else a
            if other not in names or other in expected:
                raise ValueError('ambiguous substrate relocation endpoint')
            expected[other] = value
            tag = 'substrate_relocated'
        elif key in exported_pairs:
            tag = 'exported_coupling'
        else:
            tag = 'unresolved'
            unresolved.append(dict(node_ids=[key[2], key[3]], native_cap_hex=value.hex()))
        classes[tag] += 1
        event_classes[tag] += counts[key]
    observed = set()
    for key, before, after in relocations:
        if key not in expected or key in observed or before + expected[key] != after:
            raise ValueError('native substrate relocation addition mismatch')
        observed.add(key)
    if observed != expected.keys():
        raise ValueError('missing native substrate relocation updates')
    if not exported_pairs <= sums.keys():
        raise ValueError('exported pair without logged contributions')
    return dict(native_pointer_pairs=len(sums), pair_classes=dict(classes),
                event_classes=dict(event_classes), unresolved_pairs=unresolved,
                all_nonexported_pairs_classified=not unresolved,
                native_substrate_relocation_additions_verified=len(observed),
                substrate_name=names[substrate], spatial_ground_placement_qualified=False,
                distributed_wire_R_qualified=False, release_ready=False)


def run(source, engine, output):
    receipt = source / 'assessment.json'
    engine_receipt = engine / 'assessment.json'
    a = json.loads(receipt.read_text())
    e = json.loads(engine_receipt.read_text())
    for r in (a, e):
        verify(r['input_sha256'])
        verify(r['artifacts'])
    if not a['native_process_completed'] or not a['numeric_ground_lifecycle_trace_available']:
        raise ValueError('completed native ground trace required')
    if a['input_sha256'].get(str(engine_receipt)) != sha(engine_receipt):
        raise ValueError('matching native trace engine required')
    instrumentation = engine / 'instrumentation.json'
    meta = json.loads(instrumentation.read_text())
    sites = {r['file'] + ':' + str(r['line']) for r in meta['direct_ground_mutation_inventory']
             if r['statement'] in ('rbp->nreg_cap += cap;', 'rtp->nreg_cap += cap;')}
    if len(sites) != 2:
        raise ValueError('two inspected substrate relocation sites required')
    trace = source / 'coupling.jsonl'
    pins = {str(p): sha(p) for p in (receipt, engine_receipt, instrumentation, trace,
                                    Path(__file__).resolve(),
                                    Path(__file__).with_name('audit_magic_coupling_geometry_trace.py'))}
    result = audit(trace, sites)
    verify(pins)
    output.mkdir(parents=True, exist_ok=False)
    save(output / 'assessment.json', dict(input_sha256=pins, **result))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('source', 'engine', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    run(a.source.resolve(), a.engine.resolve(), a.output.resolve())
