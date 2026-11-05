#!/usr/bin/env python3
"""Read-only coefficient-tail audit. No pruning or model selection is done.

For each diagnostic threshold, bound ||Delta C||_inf by twice the sum of
absolute incident omitted coefficients per node. Nodes include the substrate
reference, so this also bounds any grounded principal matrix. Signed values
are never clamped. This norm alone is not a trajectory/frequency error proof.
"""
from bisect import bisect_right
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import resource
import time
import numpy as np
from compile_local_C_operators_v2 import digest, save

root = Path(__file__).resolve().parents[2]
base = root/'build/timing400/release_001'
source = base/'DCO_domain_candidate_nom_substrate_output_001/candidate_unqualified.spice'
owner = base/'DCO_domain_nom_tt27_c0_f247_80ns_bounded_reuse_gear_001/owner.json'
deadline = json.loads(owner.read_text())['deadline_uptime']
assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
resource.setrlimit(resource.RLIMIT_AS, (2*1024**3, 2*1024**3))
out = base/'DCO_capacitance_magnitude_tail_audit_001'; out.mkdir(exist_ok=False)
pins = {str(p): digest(p) for p in (Path(__file__).resolve(), source, owner)}
assert pins[str(source)] == '13926ab64c12ea54d3a3b2c3e7ad0cf88d65f6f521376cbe83494d224085442e'
thresholds = [1e-33, 1e-30, 1e-27, 1e-24, 1e-21, 1e-20, 1e-19, 1e-18, 1e-17]
rows = np.zeros((250000, len(thresholds)))
incidences = np.zeros((250000, len(thresholds)), dtype=np.int64)
counts = np.zeros(len(thresholds), dtype=np.int64)
negative_counts = np.zeros(len(thresholds), dtype=np.int64)
nodes = {}; capacitors = 0; negative = 0; positive = 0; zero = 0
other_capacitor_cards = 0; minimum = math.inf; maximum = 0.; self_loops = 0
started = time.monotonic()
save(out/'owner.json', dict(started_utc=datetime.now(timezone.utc).isoformat(),
     deadline_uptime=deadline, budget_restarted=False, native_circuit_started=False,
     source_model_modified=False, diagnostic_thresholds_F=thresholds, input_sha256=pins))
with source.open() as stream:
    for lineno, line in enumerate(stream, 1):
        if lineno % 100000 == 0:
            assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
            assert time.monotonic()-started < 300
        if not line.startswith('CFIELD_'):
            if line[:1].upper() == 'C': other_capacitor_cards += 1
            continue
        fields = line.split(); assert len(fields) == 4, lineno
        value = float(fields[3]); assert math.isfinite(value)
        amplitude = abs(value); capacitors += 1
        negative += value < 0; positive += value > 0; zero += value == 0
        if amplitude: minimum = min(minimum, amplitude)
        maximum = max(maximum, amplitude)
        first, second = fields[1:3]
        if first == second: self_loops += 1
        for node in (first, second):
            if node not in nodes: nodes[node] = len(nodes)
        assert len(nodes) <= len(rows)
        bucket = bisect_right(thresholds, amplitude)
        if bucket == len(thresholds): continue
        counts[bucket] += 1; negative_counts[bucket] += value < 0
        if first != second:
            for node in (first, second):
                index = nodes[node]
                rows[index, bucket] += 2*amplitude
                incidences[index, bucket] += 1
assert capacitors == 5492690 and other_capacitor_cards == 0
assert negative+positive+zero == capacitors
rows = np.cumsum(rows[:len(nodes)], axis=1)
incidences = np.cumsum(incidences[:len(nodes)], axis=1)
counts = np.cumsum(counts); negative_counts = np.cumsum(negative_counts)
reverse = {i: name for name, i in nodes.items()}
# Positive summation with N additions has relative error <= gamma_N.
# Use a deliberately larger universal addition count, also covering the
# decimal-to-binary coefficient rounding and cumulative bucket sums.
epsilon = np.finfo(float).eps
operations = 2*capacitors+2*len(thresholds)+10
gamma = operations*epsilon/(1-operations*epsilon)
results = []
for i, threshold in enumerate(thresholds):
    index = int(np.argmax(rows[:, i]))
    upper = float(np.nextafter(rows[index, i]/(1-gamma), math.inf))
    results.append(dict(strict_absolute_coefficient_threshold_F=threshold,
         branches_below_threshold=int(counts[i]),
         branch_fraction_below_threshold=float(counts[i]/capacitors),
         negative_branches_below_threshold=int(negative_counts[i]),
         maximum_absolute_incident_row_sum_upper_bound_F=upper,
         bound_attaining_node=reverse[index],
         incident_branch_count_at_that_node=int(incidences[index, i])))
for p, sha in pins.items(): assert digest(Path(p)) == sha, p
save(out/'assessment.json', dict(input_sha256=pins, total_field_capacitors=capacitors,
     positive_coefficients=positive, negative_coefficients=negative, zero_coefficients=zero,
     distinct_capacitor_nodes=len(nodes), self_loops=self_loops,
     minimum_nonzero_absolute_coefficient_F=minimum, maximum_absolute_coefficient_F=maximum,
     floating_point_summation_relative_allowance=float(gamma), diagnostic_tail_bounds=results,
     norm_bound_includes_substrate_reference=True, original_branch_signs_retained=True,
     source_model_modified=False, native_circuit_started=False, coefficient_pruning_selected=False,
     passivity_after_pruning_qualified=False, trajectory_or_frequency_error_qualified=False,
     full_DCO_runtime_gain_inferred=False, release_qualified=False, adopted=False,
     elapsed_s=time.monotonic()-started))
print(json.dumps(dict(capacitors=capacitors, nodes=len(nodes), diagnostic_tail_bounds=results)))
