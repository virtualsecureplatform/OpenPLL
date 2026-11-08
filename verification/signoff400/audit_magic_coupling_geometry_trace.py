"""Reconstruct exported flat coupling, rounding each native pointer pair first."""
import argparse
import json
import math
import re
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from common_v3 import save, sha, verify


def lines(path):
    with path.open() as stream:
        yield from stream


def reconstruct(trace, ext):
    names = {}
    sums = defaultdict(float)
    scales = {}
    counts = Counter()
    kinds = Counter()
    epochs = set()
    spans = 0
    for line in lines(trace):
        r = json.loads(line)
        prefix = (r['cell'], r['epoch'])
        epochs.add(prefix)
        if r['kind'] in ('ground_update', 'ground_output'):
            continue  # Validated separately by audit_magic_ground_lifecycle.
        if r['kind'] == 'node_name':
            key = (*prefix, r['node_id'])
            if key in names and names[key] != r['name']:
                raise ValueError('inconsistent native node name')
            names[key] = r['name']
            continue
        if r['kind'] not in ('overlap', 'sidewall', 'sideoverlap_halo', 'sideoverlap_legacy'):
            raise ValueError('unknown contribution')
        if r['pointwise_placement_qualified'] is not False:
            raise ValueError('search support cannot qualify placement')
        value = float.fromhex(r['cap_native_hex'])
        scale = float.fromhex(r['cap_scale_hex'])
        if not math.isfinite(value) or not math.isfinite(scale) or scale <= 0:
            raise ValueError('invalid capacitance or scale')
        key = (*prefix, *sorted((r['node1_id'], r['node2_id'])))
        if key in scales and scales[key] != scale:
            raise ValueError('mixed native scales')
        scales[key] = scale
        sums[key] += value
        counts[key] += 1
        kinds[r['kind']] += 1
        if r['kind'] == 'sidewall':
            box = r['box1']
            span = box[3] - box[1] if box[0] == box[2] else box[2] - box[0]
            if span != r['native_measure']:
                raise ValueError('sidewall support span mismatch')
            spans += 1
    if len(epochs) != 1:
        raise ValueError('exactly one extraction cell and epoch required')
    reconstructed = defaultdict(Fraction)
    unmapped_pairs = unmapped_events = 0
    for key, value in sums.items():
        cell, epoch, a, b = key
        a, b = names.get((cell, epoch, a)), names.get((cell, epoch, b))
        if a is None or b is None:
            unmapped_pairs += 1
            unmapped_events += counts[key]
            continue
        # Native extOutputCoupling emits each hash-table pair with C %lg.
        if value:
            reconstructed[tuple(sorted((a, b)))] += Fraction(format(value / scales[key], '.6g'))
    expected = defaultdict(Fraction)
    for line in lines(ext):
        if line.startswith('use '):
            raise ValueError('flat extraction required')
        if line.startswith('cap '):
            match = re.fullmatch(r'cap "([^\"]*)" "([^\"]*)" (\S+)\s*', line)
            if not match:
                raise ValueError('unrecognized exported coupling')
            a, b, value = match.groups()
            expected[tuple(sorted((a, b)))] += Fraction(value)
    differences = [dict(nodes=list(k), expected=str(expected.get(k, 0)), reconstructed=str(reconstructed.get(k, 0)))
                   for k in sorted(expected.keys() | reconstructed.keys())
                   if expected.get(k, 0) != reconstructed.get(k, 0)]
    return dict(events=sum(kinds.values()), event_kinds=dict(kinds), native_pointer_pairs=len(sums),
                exported_name_pairs=len(expected), unmapped_pointer_pairs=unmapped_pairs,
                unmapped_events=unmapped_events, sidewall_spans_verified=spans,
                differences=differences,
                all_exported_C_pairs_reconstructed_at_native_precision=not differences,
                ground_capacitance_geometry_traced=False, pointwise_placement_qualified=False,
                distributed_wire_R_qualified=False, release_ready=False)


def run(source, output):
    receipt = source / 'assessment.json'
    a = json.loads(receipt.read_text())
    verify(a['input_sha256'])
    verify(a['artifacts'])
    if not a['native_process_completed']:
        raise ValueError('completed native extraction required')
    trace = source / 'coupling.jsonl'
    exts = list(source.glob('*.ext'))
    if len(exts) != 1:
        raise ValueError('one flat EXT required')
    pins = {str(p): sha(p) for p in [receipt, trace, exts[0], Path(__file__).resolve()]}
    result = reconstruct(trace, exts[0])
    verify(pins)
    output.mkdir(parents=True, exist_ok=False)
    save(output / 'assessment.json', dict(input_sha256=pins, **result))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    run(a.source.resolve(), a.output.resolve())
