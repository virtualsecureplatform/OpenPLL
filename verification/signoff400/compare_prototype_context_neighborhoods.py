"""Compare guarded context operators through proved physical conductor identity.

Reports exact fixed-supply matrix row differences. This diagnostic does not
establish waveform convergence or invent a neighborhood acceptance threshold.
"""
import argparse
from collections import defaultdict
from fractions import Fraction as F
import json
from pathlib import Path
from common_v3 import save, sha, verify
from rebind_prototype_floating_reduction import capacitor_pairs
from project_prototype_fixed_rail_C_v2 import project, FIXED


def matrix_rows(pairs):
    diagonal = defaultdict(F)
    off_absolute = defaultdict(F)
    for (a, b), value in pairs.items():
        for node, other in ((a, b), (b, a)):
            if node == FIXED:
                continue
            diagonal[node] += value
            if other != FIXED:
                off_absolute[node] += abs(value)
    return {node: abs(diagonal[node]) + off_absolute[node]
            for node in diagonal.keys() | off_absolute.keys()}


def comparison(previous, current):
    delta = dict(current)
    for pair, value in previous.items():
        delta[pair] = delta.get(pair, F()) - value
    delta = {p: v for p, v in delta.items() if v}
    errors, scales = matrix_rows(delta), matrix_rows(previous)
    rows = []
    for node in errors.keys() | scales.keys():
        error, scale = errors.get(node, F()), scales.get(node, F())
        rows.append(dict(node=node, matrix_row_absolute_difference_F=str(error),
                         reference_matrix_row_absolute_sum_F=str(scale),
                         relative_row_difference=float(error / scale) if scale else None))
    rows.sort(key=lambda r: (r['relative_row_difference'] is None,
                            r['relative_row_difference'] or 0), reverse=True)
    return rows, len(delta)


def load(reference, guarded, graph):
    receipts = [p / 'assessment.json' for p in (reference, guarded, graph)]
    rr, gr, dr = records = [json.loads(p.read_text()) for p in receipts]
    for record in records:
        verify(record['input_sha256']); verify(record['artifacts'])
    if not gr['complete_reduced_fixed_supply_C_passivity_certified']:
        raise ValueError('guarded passive reference required')
    if not dr['primitive_terminal_conductor_bijection_verified']:
        raise ValueError('physical conductor proof required')
    if rr['assembled_candidate_gds_sha256'] != gr['assembled_candidate_gds_sha256']:
        raise ValueError('reference and reduced manufacturing identity differ')
    if gr['input_sha256'].get(str(receipts[0])) != sha(receipts[0]):
        raise ValueError('guarded model derives from a different flat reference')
    if rr['input_sha256'].get(str(receipts[2])) != sha(receipts[2]):
        raise ValueError('flat reference physical graph proof differs')
    raw_path = graph / 'primitive_conductor_bijection.json'
    node_path = reference / 'nodes.json'
    raw = json.loads(raw_path.read_text())
    metadata = json.loads(node_path.read_text())
    mapping = {metadata['original_to_emitted'][native]: old for old, native in raw.items()}
    if len(mapping) != len(raw):
        raise ValueError('physical conductor map is not bijective')
    mapping['0'] = '0'
    pairs = capacitor_pairs((guarded / 'context.spice').read_text(), mapping)
    fixed = {mapping[metadata['original_to_emitted'][n]]
             for n in metadata['original_fixed_supply_nodes']} | {'0'}
    return project(pairs, fixed), raw, fixed, records, receipts, [raw_path, node_path, guarded / 'context.spice']


def run(previous_reference, previous_guarded, previous_graph,
        current_reference, current_guarded, current_graph, output):
    a, amap, afixed, ar, ap, ax = load(previous_reference, previous_guarded, previous_graph)
    b, bmap, bfixed, br, bp, bx = load(current_reference, current_guarded, current_graph)
    if amap.keys() != bmap.keys() or afixed != bfixed:
        raise ValueError('physical conductor bases or fixed supplies differ')
    if ar[0]['assembled_candidate_gds_sha256'] != br[0]['assembled_candidate_gds_sha256']:
        raise ValueError('manufacturing candidates differ')
    # Both bijections must anchor the identical previous native extraction.
    shared = {p: h for p, h in ar[2]['input_sha256'].items()
              if p.endswith('/capacitance.spice') and p in br[2]['input_sha256']}
    if len(shared) != 1 or any(br[2]['input_sha256'][p] != h for p, h in shared.items()):
        raise ValueError('physical bijections lack a common native reference')
    pins = {str(p): sha(p) for p in [*ap, *bp, *ax, *bx, Path(__file__).resolve(),
        Path(__file__).with_name('rebind_prototype_floating_reduction.py'),
        Path(__file__).with_name('project_prototype_fixed_rail_C_v2.py')]}
    rows, changed = comparison(a, b)
    verify(pins)
    output.mkdir(parents=True, exist_ok=False)
    target = output / 'row_differences.json'
    save(target, dict(rows=rows))
    save(output / 'assessment.json', dict(input_sha256=pins, artifacts={str(target): sha(target)},
        physical_conductor_basis=len(amap), fixed_supply_projection=True,
        changed_aggregated_pairs=changed, compared_dynamic_rows=len(rows),
        maximum_relative_row_difference=max((r['relative_row_difference'] for r in rows
                                            if r['relative_row_difference'] is not None), default=0),
        rows_with_zero_reference_and_nonzero_difference=sum(r['relative_row_difference'] is None for r in rows),
        numerical_guards_included=True, neighborhood_convergence_verified=False,
        loaded_waveform_comparison_performed=False, diagnostic=True,
        validated_for_prototype=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    names = ('previous-reference', 'previous-guarded', 'previous-graph',
             'current-reference', 'current-guarded', 'current-graph', 'output')
    for name in names:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    run(*(getattr(args, n.replace('-', '_')).resolve() for n in names))
