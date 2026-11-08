"""Select one net from a completed, independently audited native geometry trace."""
import argparse
import json
import math
import os
import re
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from common_v3 import save, sha, verify

OUTPUT_PREFIXES = (b'{"kind":"ground_output"', b'{"kind":"node_name"')
COUPLING = {'overlap', 'sidewall', 'sideoverlap_halo', 'sideoverlap_legacy'}


def output_suffix(trace, target, window=512 * 1024**2):
    """Backtrack until the start of the complete native output suffix is proven."""
    size = trace.stat().st_size
    while True:
        start = max(0, size - window)
        names = {}
        substrates = set()
        target_outputs = []
        counts = Counter()
        seen_other = seen_output = expand = False
        with trace.open('rb') as stream:
            stream.seek(start)
            if start:
                stream.readline()
            for line in stream:
                r = None
                is_output = line.startswith(OUTPUT_PREFIXES)
                if not is_output and not line.startswith(b'{"kind":"'):
                    r = json.loads(line)
                    is_output = r['kind'] in ('ground_output', 'node_name')
                if not is_output:
                    if seen_output:
                        raise ValueError('nonoutput event after native output suffix started')
                    seen_other = True
                    continue
                if not seen_output and start and not seen_other:
                    expand = True
                    break
                seen_output = True
                r = r if r is not None else json.loads(line)
                key = (r['cell'], r['epoch'], r['node_id'])
                if key in names and names[key] != r['name']:
                    raise ValueError('inconsistent observed native node name')
                names[key] = r['name']
                counts[r['kind']] += 1
                if r['kind'] == 'ground_output':
                    if r['substrate'] is True:
                        substrates.add(key)
                    if r['name'] == target:
                        target_outputs.append(r)
        if expand or not seen_output:
            if not start:
                raise ValueError('complete native output suffix required')
            window *= 2
            continue
        if len({k[:2] for k in names}) != 1 or len(substrates) != 1:
            raise ValueError('one extraction epoch and substrate required')
        return dict(names=names, substrates=substrates, target_outputs=target_outputs,
                    counts=counts, suffix_start=start)


def select(trace, ext, target, suffix, destination):
    names, substrates = suffix['names'], suffix['substrates']
    targets = [k for k, name in names.items() if name == target]
    if len(targets) != 1 or len(suffix['target_outputs']) != 1:
        raise ValueError('one uniquely named physical target node required')
    target_key = targets[0]
    needle = ('"' + target_key[2] + '"').encode()
    sums = defaultdict(float)
    scales = {}
    kinds = Counter()
    state = None
    output = None
    with trace.open('rb') as source, destination.open('w') as selected:
        for number, line in enumerate(source, 1):
            if line.startswith(b'{"kind":"node_name"') or needle not in line:
                continue
            r = json.loads(line)
            prefix = (r['cell'], r['epoch'])
            if prefix != target_key[:2]:
                raise ValueError('mixed target extraction epoch')
            kind = r['kind']
            if kind == 'node_name':
                continue
            if kind in COUPLING:
                a, b = r['node1_id'], r['node2_id']
                if target_key[2] not in (a, b):
                    continue
                pair = tuple(sorted((a, b)))
                value, scale = float.fromhex(r['cap_native_hex']), float.fromhex(r['cap_scale_hex'])
                if not math.isfinite(value) or not math.isfinite(scale) or scale <= 0:
                    raise ValueError('finite coupling and scale required')
                if pair in scales and scales[pair] != scale:
                    raise ValueError('mixed pair capacitance scales')
                scales[pair] = scale
                sums[pair] += value
                r['endpoint_names'] = [names[(*prefix, a)], names[(*prefix, b)]]
            elif kind == 'ground_update':
                if r['node_id'] != target_key[2]:
                    continue
                if r['has_before'] is True and state != float.fromhex(r['before_hex']):
                    raise ValueError('selected ground continuity failure')
                if type(r['has_before']) is not bool:
                    raise ValueError('explicit ground before-state presence required')
                state = float.fromhex(r['after_hex'])
                if not math.isfinite(state):
                    raise ValueError('nonfinite selected ground state')
            elif kind == 'ground_output':
                if r['node_id'] != target_key[2]:
                    continue
                if output is not None or state != float.fromhex(r['native_hex']):
                    raise ValueError('selected ground output state mismatch')
                scale = float.fromhex(r['scale_hex'])
                emitted = float.fromhex(r['emitted_hex'])
                if not math.isfinite(scale) or scale <= 0 or not math.isfinite(emitted):
                    raise ValueError('finite ground output and scale required')
                expected = 0.0 if r['substrate'] is True else max(0.0, state / scale)
                if emitted != expected:
                    raise ValueError('selected ground output scale/clamp mismatch')
                output = r
            else:
                raise ValueError('unknown selected trace event')
            kinds[kind] += 1
            r['source_line'] = number
            selected.write(json.dumps(r, separators=(',', ':')) + '\n')
    expected = defaultdict(Fraction)
    capscale = None
    records = 0
    with ext.open() as stream:
        for line in stream:
            if line.startswith('use '):
                raise ValueError('flat native EXT required')
            if line.startswith('scale '):
                capscale = Fraction(line.split()[2])
            if not line.startswith('cap ') or ('"' + target + '"') not in line:
                continue
            m = re.fullmatch(r'cap "([^\"]*)" "([^\"]*)" (\S+)\s*', line)
            if not m:
                raise ValueError('unrecognized selected native coupling')
            a, b, value = m.groups()
            if target not in (a, b):
                continue
            expected[tuple(sorted((a, b)))] += Fraction(value)
            records += 1
    if capscale != 1 or output is None:
        raise ValueError('complete capscale-one target output required')
    reconstructed = defaultdict(Fraction)
    classes = Counter()
    relocated_native = 0.0
    for pair, value in sums.items():
        keys = [(*target_key[:2], p) for p in pair]
        if not value:
            classes['zero_sum'] += 1
        elif any(k in substrates for k in keys):
            classes['substrate_relocated'] += 1
            relocated_native += value / scales[pair]
        else:
            classes['exported_coupling'] += 1
            key = tuple(sorted(names[k] for k in keys))
            reconstructed[key] += Fraction(format(value / scales[pair], '.6g'))
    if expected != reconstructed:
        raise ValueError('selected trace does not reconstruct target native coupling table')
    return dict(target=target, target_node_id=target_key[2], selected_event_kinds=dict(kinds),
                selected_events=sum(kinds.values()), native_pointer_pair_classes=dict(classes),
                exported_target_cap_records=records, exported_target_name_pairs=len(expected),
                exported_coupling_fF=float(sum(expected.values(), Fraction()) / 1000),
                substrate_relocated_coupling_fF=relocated_native / 1000,
                final_native_ground_fF=float.fromhex(output['emitted_hex']) / 1000,
                selected_ground_state_continuity_verified=True,
                all_target_exported_C_pairs_reconstructed=True,
                overlap_shielding_masks_resolved=False, ground_geometry_available=False,
                pointwise_placement_qualified=False, distributed_wire_R_qualified=False,
                native_simulation_allowed=False, release_ready=False)


def run(source, ground_audit, coupling_audit, relocation_audit, target, output):
    receipt_paths = [p / 'assessment.json' for p in (source, ground_audit, coupling_audit, relocation_audit)]
    a, g, c, r = [json.loads(p.read_text()) for p in receipt_paths]
    if not a['native_process_completed'] or not g['exported_ground_records_match'] or not c['all_exported_C_pairs_reconstructed_at_native_precision'] or not r['all_nonexported_pairs_classified']:
        raise ValueError('completed independent numerical audits required')
    for audit in (g, c, r):
        if audit['input_sha256'].get(str(receipt_paths[0])) != sha(receipt_paths[0]):
            raise ValueError('same completed source trace required')
    pins = {str(p): sha(p) for p in [*receipt_paths, Path(__file__).resolve()]}
    closure = {}
    for receipt in (a, g, c, r):
        for key, value in {**receipt['input_sha256'], **receipt.get('artifacts', {})}.items():
            if key in closure and closure[key] != value:
                raise ValueError('conflicting source identity pins')
            closure[key] = value
    trace = source / 'coupling.jsonl'
    exts = list(source.glob('*.ext'))
    if len(exts) != 1:
        raise ValueError('one flat source EXT required')
    def identity(path):
        s = path.stat()
        return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns
    identities = {p: identity(p) for p in (trace, exts[0])}
    verify(closure)
    output.mkdir(parents=True, exist_ok=False)
    save(output / 'owner.json', dict(pid=os.getpid()))
    suffix = output_suffix(trace, target)
    if suffix['counts']['ground_output'] != g['ground_output_records'] or suffix['counts']['node_name'] != 2 * c['exported_name_pairs']:
        raise ValueError('incomplete native output suffix')
    selected = output / 'selected_native_events.jsonl'
    metrics = select(trace, exts[0], target, suffix, selected)
    if any(identity(p) != value for p, value in identities.items()):
        raise ValueError('completed source changed during selection')
    verify(pins)
    # Native source files are immutable; retain the verified closure identities.
    save(output / 'assessment.json', dict(input_sha256={**closure, **pins},
                                          artifacts={str(selected): sha(selected)},
                                          complete_output_suffix_start=suffix['suffix_start'], **metrics))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('source', 'ground_audit', 'coupling_audit', 'relocation_audit', 'output'):
        p.add_argument('--' + name.replace('_', '-'), type=Path, required=True)
    p.add_argument('--target', required=True)
    a = p.parse_args()
    run(a.source.resolve(), a.ground_audit.resolve(), a.coupling_audit.resolve(),
        a.relocation_audit.resolve(), a.target, a.output.resolve())
