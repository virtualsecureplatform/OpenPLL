#!/usr/bin/env python3
"""Reconstruct a failed max-C mode from every unchanged owned energy operator."""
from collections import defaultdict
import heapq
import json
import math
import os
from pathlib import Path
import signal
import time
import numpy as np
from scipy.sparse import load_npz
from assemble_local_C_matrix import Atlas, integrate_operator
from compile_local_C_operators_v2 import digest, save


def main():
    base = Path(__file__).resolve().parents[2]/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    signal.alarm(max(1, int(deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    out = base/'DCO_max_C_mode_energy_trace_001'
    out.mkdir(exist_ok=False)
    operators = base/'DCO_local_C_operators_max_self_001'
    family = base/'DCO_complete_domain_model_primitives_001'
    matrix = base/'DCO_local_C_matrix_max_self_001'
    mode = base/'DCO_max_C_negative_mode_diagnosis_001/physical_mode_voltages.npz'
    voltage = np.load(mode)['voltages'][0]
    names = json.loads((matrix/'nodes.json').read_text())
    assert len(names) == len(voltage)
    values = dict(zip(names, voltage))
    expected = float(voltage@load_npz(matrix/'C_native_units.npz')@voltage)
    assert expected < 0
    fields = json.loads((operators/'fields.json').read_text())
    atlas = Atlas(family/'voltage_domains.jsonl', fields)
    sums = defaultdict(lambda:[0.,0.])
    negative, positive = [], []
    count = 0
    def status(state):
        save(out/'status.json', dict(state=state, runner_pid=os.getpid(), deadline_uptime=deadline,
            operators_checked=count, expected_total_energy_native_units=expected))
    status('tracing_owned_energy_operators')
    for count, text in enumerate((operators/'operators.jsonl').open(), 1):
        row = json.loads(text)
        energy = math.fsum(value*values[a]*values[b]*(1 if a == b else 2)
            for local in integrate_operator(atlas,row) for (a,b),value in local.items())
        coefficient = row[5] if row[0] == 'A' else row[6] if row[0] == 'L' else row[7]
        category = '_'.join([row[0], 'GROUND' if row[2] == 0 else 'PAIR',
            'SELF' if row[3] < 0 else 'NATIVE', 'NEGATIVE' if coefficient < 0 else 'POSITIVE'])
        # Compensated accumulation retains cancellation between shields and bases.
        acc = sums[category]
        y = energy-acc[1]
        total = acc[0]+y
        acc[1] = (total-acc[0])-y
        acc[0] = total
        heap = negative if energy < 0 else positive
        magnitude = abs(energy)
        entry = (magnitude,count,energy,row)
        if len(heap) < 300:
            heapq.heappush(heap,entry)
        elif magnitude > heap[0][0]:
            heapq.heapreplace(heap,entry)
        if count % 20000 == 0:
            assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
            status('tracing_owned_energy_operators')
    assert count == json.loads((operators/'assessment.json').read_text())['counts']['operators']
    recovered = math.fsum(v[0] for v in sums.values())
    assert abs(recovered-expected) < 1e-5, (recovered,expected)
    def describe(heap):
        return [dict(operator_serial=n, energy_native_units=e, operator=row,
            source_field=fields[row[1]], target_field=fields[row[2]])
            for _,n,e,row in sorted(heap,reverse=True)]
    save(out/'largest_negative_operators.json',describe(negative))
    save(out/'largest_positive_operators.json',describe(positive))
    inputs = [Path(__file__).resolve(), owner, mode, operators/'operators.jsonl', operators/'fields.json',
        operators/'assessment.json', family/'voltage_domains.jsonl', matrix/'nodes.json',matrix/'C_native_units.npz',
        Path(__file__).with_name('assemble_local_C_matrix.py'),Path(__file__).with_name('local_C_field_integrals.py')]
    save(out/'assessment.json', dict(all_owned_operators_checked=count,
        expected_matrix_energy_native_units=expected, reconstructed_operator_energy_native_units=recovered,
        energy_by_category_native_units={k:v[0] for k,v in sums.items()},
        negative_energy_mode_reconstruction_passed=True, model_changed=False,
        runtime_model_eligible=False,release_qualified=False,adopted=False,deadline_uptime=deadline,
        input_sha256={str(p.resolve()):digest(p) for p in inputs},
        artifacts={str(p.resolve()):digest(p) for p in [out/'largest_negative_operators.json',out/'largest_positive_operators.json']}))
    status('completed')
    print(json.dumps(dict(expected=expected,reconstructed=recovered,categories={k:v[0] for k,v in sums.items()}),indent=2))


if __name__ == '__main__':
    main()
