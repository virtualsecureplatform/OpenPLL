#!/usr/bin/env python3
"""Reconstruct one failed private-node diagonal from its owned signed pieces."""
from collections import defaultdict
import json
from pathlib import Path
import time

from assemble_local_C_matrix import Atlas, integrate_operator
from compile_local_C_operators_v2 import digest, save
from scipy.sparse import load_npz


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    family = base/'DCO_complete_domain_model_primitives_001'
    operators = base/'DCO_local_C_operators_nom_001'
    matrix_dir = base/'DCO_local_C_matrix_nom_001'
    target_node = '_rdomain_2688_222285'
    domains = [json.loads(s) for s in (family/'voltage_domains.jsonl').open()]
    affected = [r for r in domains if any(n == target_node for _, n in r['voltage_knots_internal'])]
    assert len(affected) == 1
    target_domain = affected[0]
    box = target_domain['box_internal']
    fields = json.loads((operators/'fields.json').read_text())
    field = fields.index([target_domain[k] for k in ['original_conductor', 'plane', 'effective_material']])
    atlas = Atlas(family/'voltage_domains.jsonl', fields)
    def touches(a, b):
        return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]
    out = base/'DCO_negative_C_diagonal_diagnosis_001'
    out.mkdir(exist_ok=False)
    terms, counts = [], defaultdict(float)
    for serial, text in enumerate((operators/'operators.jsonl').open(), 1):
        row = json.loads(text)
        kind, a, b, event, *data = row
        if serial % 100000 == 0:
            assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
            save(out/'status.json', dict(state='tracing_signed_node_terms', operators_checked=serial, terms=len(terms)))
        if field not in [a, b]:
            continue
        supports = [data[0]] if kind == 'A' else data[:2]
        if not ((a == field and touches(supports[0], box)) or (b == field and touches(supports[-1], box))):
            continue
        total = sum(part.get((target_node, target_node), 0.) for part in integrate_operator(atlas, row))
        if total:
            coefficient = data[1] if kind == 'A' else data[2] if kind == 'L' else data[3]
            category = kind+('_GROUND' if b == 0 else '_PAIR')+('_POSITIVE' if coefficient > 0 else '_NEGATIVE')
            counts[category] += total
            terms.append(dict(operator_serial=serial, event=event, diagonal_native_cap_units=total,
                category=category, operator=row))
    names = json.loads((matrix_dir/'nodes.json').read_text())
    diagonal = float(load_npz(matrix_dir/'C_native_units.npz').diagonal()[names.index(target_node)])
    recovered = sum(r['diagonal_native_cap_units'] for r in terms)
    assert abs(recovered-diagonal) < 1e-9, (recovered, diagonal)
    terms.sort(key=lambda r: r['diagonal_native_cap_units'])
    save(out/'terms.json', terms)
    result = dict(target_node=target_node, target_domain=target_domain,
        negative_diagonal_native_cap_units=diagonal, reconstructed_diagonal_native_cap_units=recovered,
        terms_by_category=dict(counts), matching_terms=len(terms),
        source_serials_of_largest_negative_terms=[r['event'] for r in terms[:10]],
        source_serials_of_largest_positive_terms=[r['event'] for r in terms[-10:]],
        runtime_model_eligible=False, release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256={str(p.resolve()): digest(p) for p in [Path(__file__).resolve(), owner,
            operators/'assessment.json', operators/'operators.jsonl', operators/'fields.json',
            family/'voltage_domains.jsonl', matrix_dir/'assessment.json', matrix_dir/'C_native_units.npz']},
        artifacts={str((out/'terms.json').resolve()): digest(out/'terms.json')})
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(out/'assessment.json', result)
    save(out/'status.json', dict(state='completed', reconstructed_diagonal=recovered))
    print(json.dumps({k: v for k, v in result.items() if k not in ['input_sha256', 'artifacts']}, indent=2))


if __name__ == '__main__':
    main()
