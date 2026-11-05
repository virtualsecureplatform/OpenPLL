#!/usr/bin/env python3
"""Add explicitly missing self-pair energy after exact native-operator identity.

The rejected matrix is reused only as a numerical sum of unchanged operators.
The corrected result must independently pass conservation and passivity checks.
"""
import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import time
import traceback

import numpy as np
from scipy.sparse import coo_matrix, diags, load_npz, save_npz
from assemble_local_C_matrix import Atlas, integrate_operator
from compile_local_C_operators_v2 import digest, save


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-matrix', type=Path, required=True)
    parser.add_argument('--operators', type=Path, required=True)
    parser.add_argument('--identity-check', type=Path, required=True)
    parser.add_argument('--family', type=Path, required=True)
    parser.add_argument('--owner', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    deadline = json.loads(args.owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    identity = json.loads(args.identity_check.read_text())
    assert identity['all_original_energy_operators_identical_under_exact_field_key_renaming']
    assert identity['all_increment_endpoints_on_same_original_conductor']
    proof = json.loads((args.base_matrix/'assessment.json').read_text())
    assert proof['full_nominal_C_energy_matrix_assembled']
    source_path = args.operators/'operators.jsonl'
    assert identity['input_sha256'][str(source_path.resolve())] == digest(source_path)
    # Prove the reused numerical sum was assembled from the exact old operator
    # file checked by the identity assessor, on the same complete field atlas.
    old_paths = {p for p in identity['input_sha256'] if p.endswith('/operators.jsonl') and p != str(source_path.resolve())}
    assert len(old_paths) == 1
    old_path = next(iter(old_paths))
    assert proof['input_sha256'][old_path] == identity['input_sha256'][old_path]
    domains = args.family/'voltage_domains.jsonl'
    assert proof['input_sha256'][str(domains.resolve())] == digest(domains)
    for name, value in proof['artifacts'].items():
        assert digest(Path(name)) == value
    delta_path = args.identity_check.parent/'self_operators.jsonl'
    assert identity['artifacts'][str(delta_path.resolve())] == digest(delta_path)
    fields = json.loads((args.operators/'fields.json').read_text())
    atlas = Atlas(domains, fields)
    nodes = json.loads((args.base_matrix/'nodes.json').read_text())
    indices = {name: i for i, name in enumerate(nodes)}
    size = len(nodes)
    matrix = load_npz(args.base_matrix/'C_native_units.npz').tocsr()
    delta = defaultdict(float)
    counts = Counter()
    args.output.mkdir(exist_ok=False)
    def status(state, **more):
        save(args.output/'status.json', dict(state=state, runner_pid=os.getpid(), counts=dict(counts),
            self_upper_entries=len(delta), deadline_uptime=deadline, **more))
    status('assembling_missing_self_energy')
    try:
        with delta_path.open() as stream:
            for text in stream:
                row = json.loads(text)
                assert row[3] < 0 and row[1] != 0 and row[2] != 0
                assert fields[row[1]][0] == fields[row[2]][0]
                for local in integrate_operator(atlas, row):
                    counts['domain_cells'] += 1
                    for (a, b), value in local.items():
                        ia, ib = sorted((indices[a], indices[b]))
                        delta[ia*size+ib] += value
                counts['self_operators'] += 1
                counts[row[0]] += 1
                if counts['self_operators'] % 10000 == 0:
                    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
                    status('assembling_missing_self_energy')
        assert counts['self_operators'] == identity['isolated_missing_self_operators']
        encoded = np.fromiter(delta, dtype=np.int64, count=len(delta))
        values = np.fromiter(delta.values(), dtype=np.float64, count=len(delta))
        upper = coo_matrix((values, (encoded//size, encoded % size)), shape=matrix.shape).tocsr()
        addition = upper+upper.T-diags(upper.diagonal())
        corrected = matrix+addition
        row_norm = np.asarray(abs(corrected).sum(axis=1)).ravel()
        relative = abs(np.asarray(corrected.sum(axis=1)).ravel())/np.maximum(row_norm, 1e-30)
        assert np.isfinite(corrected.data).all() and max(relative) < 1e-11, max(relative)
        save_npz(args.output/'C_native_units.npz', corrected)
        save(args.output/'nodes.json', nodes)
        inputs = [Path(__file__).resolve(), args.owner, args.identity_check, delta_path,
            args.base_matrix/'assessment.json', args.base_matrix/'C_native_units.npz', args.base_matrix/'nodes.json',
            args.operators/'assessment.json', args.operators/'fields.json', source_path, domains,
            Path(__file__).with_name('assemble_local_C_matrix.py'), Path(__file__).with_name('local_C_field_integrals.py')]
        result = dict(full_nominal_C_energy_matrix_assembled=True, full_C_energy_matrix_assembled=True, RC_corner='nom',
            finite_R_same_conductor_pair_energy_restored=True,
            original_operators_numerically_reused_after_exact_identity=identity['original_operators'],
            added_same_conductor_operators=counts['self_operators'], counts=dict(counts),
            native_private_voltage_vertices=size-1, explicit_substrate_reference_vertex=True,
            maximum_relative_charge_row_residual=float(max(relative)), matrix_nonzeros=corrected.nnz, capacitance_unit_F=1e-18,
            signed_global_passivity_qualified=False, runtime_model_eligible=False, release_qualified=False, adopted=False,
            deadline_uptime=deadline, input_sha256={str(p.resolve()): digest(p) for p in inputs},
            artifacts={str(p.resolve()): digest(p) for p in [args.output/'C_native_units.npz', args.output/'nodes.json']})
        assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
        save(args.output/'assessment.json', result)
        status('completed_global_passivity_check_required')
    except BaseException:
        status('failed_or_inconclusive', error=traceback.format_exc())
        raise


if __name__ == '__main__':
    main()
