#!/usr/bin/env python3
"""Check assembled C: zero-wire-R collapse, conservation, and signed passivity.

Passivity is tested on the full normalized sparse matrix, with disconnected
zero-capacitance vertices removed. A failed eigenvalue bound is diagnostic;
it never adopts a runtime model or changes the frozen release requirements.
"""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import time

import numpy as np
from scipy.sparse import coo_matrix, diags, load_npz
from scipy.sparse.linalg import eigsh
from compile_local_C_operators_v2 import digest, save


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--matrix', required=True, type=Path)
    p.add_argument('--family', required=True, type=Path)
    p.add_argument('--operators', required=True, type=Path)
    p.add_argument('--owner', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--corner', choices=['min', 'nom', 'max'], default='nom')
    args = p.parse_args()
    deadline = json.loads(args.owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    proof = json.loads((args.matrix/'assessment.json').read_text())
    if args.corner == 'nom':
        assert proof['full_nominal_C_energy_matrix_assembled']
    else:
        assert proof['full_C_energy_matrix_assembled'] and proof['RC_corner'] == args.corner
    for name, expected in proof['artifacts'].items():
        assert digest(Path(name)) == expected, name
    args.output.mkdir(parents=True, exist_ok=False)
    nodes = json.loads((args.matrix/'nodes.json').read_text())
    original = {r['private_id']: r['original_conductor'] for r in json.loads((args.family/'nodes.json').read_text())}
    original['_dco_substrate_reference'] = 'VGND'
    names = sorted(set(original.values()))
    names_index = {n: i for i, n in enumerate(names)}
    assignment = np.asarray([names_index[original[n]] for n in nodes], dtype=np.int64)
    matrix = load_npz(args.matrix/'C_native_units.npz').tocsr()
    entries = matrix.tocoo()
    collapsed = coo_matrix((entries.data, (assignment[entries.row], assignment[entries.col])),
        shape=(len(names), len(names))).tocsr()
    fields = json.loads((args.operators/'fields.json').read_text())
    ledger = json.loads((args.operators/'collapsed_matrix_ledger.json').read_text())
    expected = defaultdict(float)
    residual = 0.
    for a, b, native, physical, error in ledger:
        a = names_index['VGND' if a == 0 else fields[a][0]]
        b = names_index['VGND' if b == 0 else fields[b][0]]
        if a == b:
            continue
        expected[a, a] += physical
        expected[b, b] += physical
        expected[a, b] -= physical
        expected[b, a] -= physical
        residual += error
    rr, cc, vv = zip(*[(a, b, v) for (a, b), v in expected.items()])
    reference = coo_matrix((vv, (rr, cc)), shape=collapsed.shape).tocsr()
    difference = collapsed-reference
    maximum_error = max(abs(difference.data), default=0.)
    scale = max(abs(reference.data), default=1.)
    assert maximum_error <= 1e-10*scale, (maximum_error, scale)
    # Rayleigh spectrum in units of local total absolute charge. Use a
    # deterministic start and keep all signed terms, including positive
    # same-conductor off-diagonal mass entries.
    row_norm = np.asarray(abs(matrix).sum(axis=1)).ravel()
    active = row_norm > 0
    positive_diagonal = bool(np.all(matrix.diagonal() >= -1e-12*np.maximum(row_norm, 1e-30)))
    norm = diags(1./np.sqrt(row_norm[active]))
    normalized = norm @ matrix[active][:, active] @ norm
    save(args.output/'status.json', dict(state='checking_signed_spectrum', runner_pid=os.getpid(), deadline_uptime=deadline,
        active_vertices=int(active.sum()), zero_R_collapse_max_error_native_units=float(maximum_error)))
    def checkpoint():
        assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    # eigsh has a finite iteration budget. Its wall-clock budget is enforced by
    # an independent process alarm in addition to the shared owner deadline.
    import signal
    def expired(signum, frame):
        save(args.output/'status.json', dict(state='timeout_inconclusive', runner_pid=os.getpid(), deadline_uptime=deadline))
        raise TimeoutError('Original shared check deadline expired')
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(max(1, int(deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    eigenvalues, vectors = eigsh(normalized, k=3, which='SA', tol=1e-9,
        maxiter=3000, v0=np.sin(np.arange(normalized.shape[0])+1.))
    checkpoint()
    errors = np.asarray([np.linalg.norm(normalized@vectors[:, i]-eigenvalues[i]*vectors[:, i]) for i in range(3)])
    passivity = positive_diagonal and bool(np.min(eigenvalues-errors) >= -1e-9)
    np.savez(args.output/'minimum_modes.npz', eigenvalues=eigenvalues, residual_norms=errors,
        vectors=vectors, active_node_indices=np.flatnonzero(active))
    inputs = [Path(__file__).resolve(), args.owner, args.matrix/'assessment.json',
        args.matrix/'nodes.json', args.matrix/'C_native_units.npz', args.family/'nodes.json',
        args.operators/'fields.json', args.operators/'collapsed_matrix_ledger.json']
    receipt = dict(zero_wire_R_collapse_matches_owned_physical_operator_totals=True, RC_corner=args.corner,
        zero_R_collapse_max_error_native_units=float(maximum_error),
        retained_native_accumulator_residual_absolute_native_units=residual,
        normalized_minimum_eigenvalues=eigenvalues.tolist(), eigenpair_residual_norms=errors.tolist(),
        negative_diagonal_absent=positive_diagonal,
        signed_global_passivity_numerical_check_passed=passivity,
        rigorous_all_eigenvalue_error_bound_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False,
        input_sha256={str(f.resolve()): digest(f) for f in inputs},
        artifacts={str((args.output/'minimum_modes.npz').resolve()): digest(args.output/'minimum_modes.npz')},
        deadline_uptime=deadline)
    save(args.output/'assessment.json', receipt)
    save(args.output/'status.json', dict(state='completed', numerical_passivity_check_passed=passivity))
    print(json.dumps({k: v for k, v in receipt.items() if k not in ['input_sha256', 'artifacts']}, indent=2))


if __name__ == '__main__':
    main()
