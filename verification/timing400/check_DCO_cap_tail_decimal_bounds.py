#!/usr/bin/env python3
"""Independently check reported worst-node bounds using decimal arithmetic.

Checks the retained maximizing nodes, not a second global maximization. The
original audit supplies global coverage; this checks its summation allowance
against exact decimal parsing on each reported witness. Never alters a model.
"""
from decimal import Decimal, localcontext
import json
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest, save

root = Path(__file__).resolve().parents[2]
base = root/'build/timing400/release_001'
report_path = base/'DCO_capacitance_magnitude_tail_audit_001/assessment.json'
report = json.loads(report_path.read_text())
source = base/'DCO_domain_candidate_nom_substrate_output_001/candidate_unqualified.spice'
out = base/'DCO_cap_tail_decimal_bound_checks_001'; out.mkdir(exist_ok=False)
assert report['source_model_modified'] is False and report['coefficient_pruning_selected'] is False
deadline = json.loads((base/'DCO_domain_nom_tt27_c0_f247_80ns_bounded_reuse_gear_001/owner.json').read_text())['deadline_uptime']
pins = {str(p): digest(p) for p in (Path(__file__).resolve(), report_path, source)}
assert digest(source) == report['input_sha256'][str(source)]
witnesses = report['diagnostic_tail_bounds']
selected = {w['bound_attaining_node'] for w in witnesses}
checks = []
with localcontext() as context:
    context.prec = 100
    sums = [Decimal(0) for _ in witnesses]
    counts = [0 for _ in witnesses]
    thresholds = [Decimal(str(w['strict_absolute_coefficient_threshold_F'])) for w in witnesses]
    for lineno, line in enumerate(source.open(), 1):
        if lineno % 100000 == 0: assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
        if not line.startswith('CFIELD_'): continue
        _, first, second, text = line.split()
        if first == second or not (first in selected or second in selected): continue
        exact = abs(Decimal(text))
        for i, witness in enumerate(witnesses):
            if witness['bound_attaining_node'] not in (first, second): continue
            # The original diagnostic groups by parsed binary64. Check the
            # exact decimal magnitudes of those same original branch cards.
            if abs(float(text)) < float(thresholds[i]):
                sums[i] += 2*exact; counts[i] += 1
    for i, witness in enumerate(witnesses):
        allowance = Decimal.from_float(witness['maximum_absolute_incident_row_sum_upper_bound_F'])
        assert sums[i] <= allowance, (i, sums[i], allowance)
        assert counts[i] == witness['incident_branch_count_at_that_node']
        checks.append(dict(threshold_F=str(thresholds[i]), node=witness['bound_attaining_node'],
             incident_branches=counts[i], decimal_absolute_row_sum_F=str(sums[i]),
             reported_binary64_upper_bound_F=str(allowance), bound_contains_exact_decimal_sum=True))
for path, sha in pins.items(): assert digest(Path(path)) == sha, path
save(out/'assessment.json', dict(input_sha256=pins, decimal_precision=100,
     maximizing_node_witness_checks=checks, all_reported_witness_bounds_verified=True,
     independent_global_maximum_search_performed=False, source_model_modified=False,
     pruning_or_frequency_accuracy_qualified=False, release_qualified=False))
print('Verified all nine reported worst-node bounds against original decimal coefficients.')
