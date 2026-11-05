"""Reparse exported pruning cards and replay the exact source/guard witness."""
import argparse
from fractions import Fraction as F
import json
import math
from pathlib import Path
from common_v3 import save, sha, verify
from prune_prototype_context_C import replay


def reconcile(source_lines, target_lines, dropped):
    originals = {line.split()[0]: line for line in source_lines
                 if line.startswith('Ckron') and line.split()[0][5:].isdigit()}
    if set(dropped) - originals.keys():
        raise ValueError('witness references absent source Schur cards')
    guards = {}
    rest = []
    for line in target_lines:
        fields = line.split()
        if fields and fields[0].startswith('CkronSparseGuard'):
            if len(fields) != 4 or fields[2] != '0' or fields[1] in guards:
                raise ValueError('unique two-terminal numerical shunts to global ground required')
            value = F(fields[3])
            binary = float(fields[3])
            if value <= 0 or not math.isfinite(binary) or binary <= 0:
                raise ValueError('positive finite numerical guard required')
            guards[fields[1]] = min(value, F.from_float(binary)), max(value, F.from_float(binary))
        else:
            rest.append(line)
    expected = [line for line in source_lines if not (line.split() and line.split()[0] in dropped)]
    if rest != expected:
        raise ValueError('export changes cards beyond declared pruning and numerical guards')
    return guards


def run(source, pruned, output):
    sr = source / 'assessment.json'; pr = pruned / 'assessment.json'
    s, p = records = [json.loads(path.read_text()) for path in (sr, pr)]
    for record in records:
        verify(record['input_sha256']); verify(record['artifacts'])
    if p['input_sha256'].get(str(sr)) != sha(sr) or not s['complete_reduced_fixed_supply_C_passivity_certified']:
        raise ValueError('one certified source reference required')
    source_model = source / 'context.spice'; target_model = pruned / 'context.spice'
    witness = pruned / 'pruning_certificate.json'; bounds = source / 'guards.json'
    paths = (sr, pr, source_model, target_model, witness, bounds, Path(__file__).resolve(),
             Path(__file__).with_name('prune_prototype_context_C.py'))
    pins = {str(path): sha(path) for path in paths}
    scales = {row['node']: F(row['reference_scale_lower_fF']) / 10**15
              for row in json.loads(bounds.read_text())}
    proof = json.loads(witness.read_text())
    dropped = proof['dropped_edge_ids']
    original = source_model.read_text().splitlines(); target = target_model.read_text().splitlines()
    guards = reconcile(original, target, set(dropped))
    if {n: dict(lower=str(lo), upper=str(hi)) for n, (lo, hi) in guards.items()} != proof['guard_enclosures_F']:
        raise ValueError('witness guard coefficients differ from exported decimal/binary values')
    edges = []
    for line in original:
        fields = line.split()
        if not fields or not fields[0].startswith('Ckron') or not fields[0][5:].isdigit():
            continue
        name, a, b, value = fields
        if a in scales and b in scales:
            edges.append((name, a, b, max(F(value), F.from_float(float(value)))))
    result = replay(edges, dropped, {n: x[0] for n, x in guards.items()},
                    {n: x[1] for n, x in guards.items()}, scales,
                    F(s['maximum_normalized_final_row_error']), F(str(s['relative_row_error_budget'])))
    if result['maximum_normalized_final_row_error'] != p['maximum_normalized_final_row_error']:
        raise ValueError('producer final error bound does not match independent replay')
    verify(pins)
    output.mkdir(parents=True, exist_ok=False)
    save(output / 'assessment.json', dict(input_sha256=pins, artifacts={}, **result,
        source_and_target_cards_independently_reparsed=True,
        all_nondeclared_source_cards_preserved=True,
        actual_exported_guard_coefficients_replayed=True,
        complete_reduced_fixed_supply_C_passivity_certified=True,
        numerical_budget_unchanged=True, native_waveform_correlation_complete=False,
        native_throughput_improvement_measured=False, diagnostic=True,
        validated_for_prototype=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'pruned', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    run(args.source.resolve(), args.pruned.resolve(), args.output.resolve())
