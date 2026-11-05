"""Prune positive Schur edges with an exact PSD guard and unchanged error budget.

Dropping c*(e_i-e_j)*(e_i-e_j)' and adding diagonal guards d_i >=
2*sum_j(c_ij) changes a PSD matrix by a symmetric diagonally dominant PSD
matrix. Its absolute row sum equals d_i. Decimal and native binary coefficient
enclosures are checked independently. Physical Cflat cards are never pruned.
"""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction as F
import json
import math
from pathlib import Path
from common_v3 import save, sha, verify
from bounded_C_diagonal_guard_v2 import coefficient


def select(edges, capacities):
    loads = defaultdict(F)
    chosen = set()
    # Ordering is only a heuristic; exact inequalities decide admission.
    ordered = sorted(edges, key=lambda e: float(e[3] / min(capacities[e[1]], capacities[e[2]])))
    for name, a, b, upper in ordered:
        if upper <= 0 or a == b:
            raise ValueError('positive distinct-terminal edges required')
        if name in chosen:
            raise ValueError('duplicate pruning edge')
        cost = 2 * upper
        if loads[a] + cost <= capacities[a] and loads[b] + cost <= capacities[b]:
            chosen.add(name)
            loads[a] += cost
            loads[b] += cost
    return chosen, {n: value for n, value in loads.items() if value}


def replay(edges, dropped, lower, upper, scales_F, original_relative, budget):
    source = {e[0]: e for e in edges}
    if len(source) != len(edges) or len(set(dropped)) != len(dropped):
        raise ValueError('unique source and witness edges required')
    sums = defaultdict(F)
    for name in dropped:
        if name not in source:
            raise ValueError('witness prunes an unknown edge')
        _, a, b, bound = source[name]
        if bound <= 0 or a == b or a not in scales_F or b not in scales_F:
            raise ValueError('only positive bounded dynamic edges may be pruned')
        sums[a] += bound; sums[b] += bound
    if set(lower) != set(sums) or set(upper) != set(sums):
        raise ValueError('guard node set differs from the dropped-edge boundary')
    if not 0 <= original_relative < budget:
        raise ValueError('source error must leave positive budget headroom')
    final = original_relative
    for node, total in sums.items():
        if not 0 < scales_F[node] or not 2 * total <= lower[node] <= upper[node]:
            raise ValueError('guard fails symmetric diagonal dominance')
        normalized = original_relative + upper[node] / scales_F[node]
        if normalized > budget:
            raise ValueError('pruning and original numerical errors exceed the unchanged budget')
        final = max(final, normalized)
    return dict(dropped_edge_witness_replayed=True,
                pruning_difference_symmetric_diagonal_dominance_verified=True,
                maximum_normalized_final_row_error=str(final),
                relative_row_error_budget=str(budget))


def run(source, output):
    receipt = source / 'assessment.json'
    r = json.loads(receipt.read_text())
    verify(r['input_sha256']); verify(r['artifacts'])
    if not r['complete_reduced_fixed_supply_C_passivity_certified']:
        raise ValueError('certified complete context source required')
    if not r['all_active_primitive_and_port_alias_cards_unchanged']:
        raise ValueError('unchanged active physical model required')
    original = F(r['maximum_normalized_final_row_error'])
    budget = F(str(r['relative_row_error_budget']))
    if not 0 <= original < budget <= F('1e-6'):
        raise ValueError('supported unchanged source error budget required')
    model = source / 'context.spice'
    bounds = source / 'guards.json'
    paths = (receipt, model, bounds, Path(__file__).resolve(),
             Path(__file__).with_name('bounded_C_diagonal_guard_v2.py'))
    pins = {str(p): sha(p) for p in paths}
    detail = json.loads(bounds.read_text())
    scales_F = {row['node']: F(row['reference_scale_lower_fF']) / 10**15 for row in detail}
    if len(scales_F) != len(detail) or any(s <= 0 for s in scales_F.values()):
        raise ValueError('unique positive bounded source row scales required')
    # Leave a rounding allowance for the outward decimal/binary guard export.
    capacities = {n: (budget - original) * scale * F(99, 100) for n, scale in scales_F.items()}
    rows = model.read_text().splitlines()
    edges = []
    for line in rows:
        fields = line.split()
        if not fields or not fields[0].startswith('Ckron') or not fields[0][5:].isdigit():
            continue
        if len(fields) != 4:
            raise ValueError('explicit two-terminal Schur coefficient required')
        name, a, b, value = fields
        decimal = F(value)
        binary = float(value)
        if not math.isfinite(binary) or decimal <= 0 or binary <= 0:
            raise ValueError('positive finite Schur edge required')
        if a in scales_F and b in scales_F:
            edges.append((name, a, b, max(decimal, F.from_float(binary))))
    selected, loads = select(edges, capacities)
    new_cards, lower, upper = [], {}, {}
    for node in sorted(loads):
        spelling, decimal = coefficient(loads[node] * 10**15)
        binary = F.from_float(float(spelling))
        lower[node], upper[node] = min(decimal, binary), max(decimal, binary)
        new_cards.append('CkronSparseGuard' + str(len(new_cards)) + ' ' + node + ' 0 ' + spelling)
    # Independent replay starts from the selected edge IDs and source
    # coefficient enclosures, not the selector's cumulative budget counters.
    proof = replay(edges, sorted(selected), lower, upper, scales_F, original, budget)
    emitted = []
    for line in rows:
        fields = line.split()
        if fields and fields[0] in selected:
            continue
        if fields and fields[0].lower() == '.ends':
            emitted.extend(new_cards)
        emitted.append(line)
    result = '\n'.join(emitted) + '\n'
    source_active = [line for line in rows if line.startswith(('Xflat', 'Rwire'))]
    target_active = [line for line in emitted if line.startswith(('Xflat', 'Rwire'))]
    if source_active != target_active:
        raise ValueError('active primitive or wire card changed')
    # Reconcile all actual emitted cards against the precise declared edits.
    def capacitor_cards(lines):
        return Counter(line for line in lines if line.startswith(('Cflat', 'Ckron')))
    expected = capacitor_cards(rows)
    for line in rows:
        if line.split() and line.split()[0] in selected:
            expected[line] -= 1
    expected += Counter(new_cards)
    if capacitor_cards(result.splitlines()) != +expected:
        raise ValueError('capacitor export differs from the certified edit')
    verify(pins)
    output.mkdir(parents=True, exist_ok=False)
    target = output / 'context.spice'
    target.write_text(result)
    witness = output / 'pruning_certificate.json'
    save(witness, dict(**proof, dropped_edge_ids=sorted(selected),
        source_coefficient_enclosure='max(exact decimal, native binary64)',
        guard_enclosures_F={n: dict(lower=str(lower[n]), upper=str(upper[n])) for n in lower},
        method=__doc__, physical_Cflat_cards_pruned=False))
    save(output / 'assessment.json', dict(input_sha256=pins,
        artifacts={str(p): sha(p) for p in (target, witness)},
        assembled_candidate_gds_sha256=r['assembled_candidate_gds_sha256'], top=r['top'],
        bounded_complete_context_floating_C_reduction_verified=True,
        all_active_primitive_and_port_alias_cards_unchanged=True,
        actual_supply_terminal_identity_preserved=True,
        complete_reduced_fixed_supply_C_passivity_certified=True,
        passivity_method='source PSD plus exact diagonal-dominant PSD pruning correction',
        source_maximum_normalized_row_error=str(original),
        maximum_normalized_final_row_error=proof['maximum_normalized_final_row_error'],
        relative_row_error_budget=float(budget), positive_dynamic_Schur_edges_considered=len(edges),
        positive_dynamic_Schur_edges_pruned=len(selected), added_numerical_guard_capacitors=len(new_cards),
        original_capacitor_cards=sum(capacitor_cards(rows).values()),
        emitted_capacitor_cards=sum(capacitor_cards(emitted).values()),
        numerical_guards_included_in_error_budget=True, physical_Cflat_cards_unchanged=True,
        numerical_reduction_with_explicit_error_bound=True, floating_charge_solve_reexecuted=False,
        native_throughput_improvement_measured=False, native_waveform_correlation_complete=False,
        distributed_wire_R_added=r['distributed_wire_R_added'],
        FOM_fill_electrical_coverage_complete=r.get('FOM_fill_electrical_coverage_complete', False),
        neighborhood_convergence_verified=False, domain_stimuli_supplied=False,
        loaded_native_model_qualified=False, diagnostic=True,
        validated_for_prototype=False, release_ready=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    run(a.source.resolve(), a.output.resolve())
