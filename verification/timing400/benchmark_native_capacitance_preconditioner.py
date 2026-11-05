#!/usr/bin/env python3
"""Solve captured native equations with wire-C-offdiagonal removal in a preconditioner.

The actual Jacobian and RHS remain unchanged. This is offline feasibility only.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import numpy as np
from scipy.sparse import coo_matrix, diags, load_npz
from scipy.sparse.linalg import splu, gmres, LinearOperator
from compile_local_C_operators_v2 import digest, save


def worker(folder, base):
    resource.setrlimit(resource.RLIMIT_AS, (48 * 1024**3, 48 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (180, 181))
    start = time.monotonic()
    capture = base / 'DCO_native_linear_system_capture_002'
    A = load_npz(capture / 'native_Jacobian.npz').tocsr()
    rhs_native = np.load(capture / 'native_RHS.npy')
    variables = json.loads((capture / 'native_variable_names.json').read_text())
    lookup = {name.upper(): i for i, name in enumerate(variables)}
    cfolder = base / 'DCO_local_C_matrix_nom_no_substrate_G_001'
    nodes = json.loads((cfolder / 'nodes.json').read_text())
    assert nodes[0] == '_dco_substrate_reference'
    mapping = np.array([lookup['XDCO:XPHYSICAL:' + name.upper()] for name in nodes[1:]])
    assert len(np.unique(mapping)) == len(mapping)
    C = (load_npz(cfolder / 'C_native_units.npz')[1:, 1:] * 1e-18).tocoo()
    idx = {name: i - 1 for i, name in enumerate(nodes)}
    devices = base / 'DCO_complete_domain_model_primitives_001/device_connections.json'
    points = base / 'DCO_direct_native_planes_and_boundaries_001/boundary_connections.json'
    protected = {name for item in json.loads(devices.read_text()).values() for name in item['private_terminals']}
    protected.update(item['private_node'] for item in json.loads(points.read_text()))
    mask = np.ones(len(nodes) - 1, dtype=bool)
    for name in protected: mask[idx[name]] = False
    n = len(nodes) - 1
    resistor_pairs = set()
    for line in (base / 'DCO_domain_R_corners_002/nom_wire_R_unqualified.spice').open():
        fields = line.split()
        if not fields or fields[0].startswith('*'): continue
        i, j = idx[fields[1]], idx[fields[2]]
        assert min(i, j) >= 0
        resistor_pairs.update((i * n + j, j * n + i))
    eligible = np.flatnonzero((C.row != C.col) & mask[C.row] & mask[C.col] & (abs(C.data) > 1e-22))
    candidates = eligible[::max(1, len(eligible) // 20000)][:20000]
    sample = np.array([k for k in candidates if int(C.row[k]) * n + int(C.col[k]) not in resistor_pairs])
    assert len(sample) >= 1000
    observed = np.asarray(A[mapping[C.row[sample]], mapping[C.col[sample]]]).reshape(-1)
    ratios = observed / C.data[sample]
    alpha = float(np.median(ratios))
    ratio_error = float(np.max(abs(ratios / alpha - 1)))
    assert np.isfinite(alpha) and alpha > 0 and ratio_error < 1e-10
    save(folder / 'coefficient_check.json', dict(inferred_C_multiplier_per_s=alpha,
        sampled_pure_passive_C_pairs=len(sample), maximum_relative_coefficient_error=ratio_error,
        device_and_point_terminals_excluded=True, resistor_pairs_excluded=True))
    offdiag = C.row != C.col
    wire_offdiag = coo_matrix((alpha * C.data[offdiag],
        (mapping[C.row[offdiag]], mapping[C.col[offdiag]])), shape=A.shape).tocsr()
    B = (A - wire_offdiag).tocsr()
    # Preconditioner-only cleanup removes floating-point subtraction remnants.
    cleanup = abs(B.data) < 1e-16
    cleanup_count = int(np.count_nonzero(cleanup)); B.data[cleanup] = 0; B.eliminate_zeros()
    rowmax = np.asarray(abs(A).max(axis=1).toarray()).reshape(-1)
    assert np.all(rowmax > 0)
    row_scale = 1 / rowmax
    row_scaled = diags(row_scale) @ A
    colmax = np.asarray(abs(row_scaled).max(axis=0).toarray()).reshape(-1)
    assert np.all(colmax > 0)
    col_scale = 1 / colmax
    S = (row_scaled @ diags(col_scale)).tocsr()
    BS = (diags(row_scale) @ B @ diags(col_scale)).tocsc()
    factor_start = time.monotonic()
    factor = splu(BS, permc_spec='COLAMD')
    factor_s = time.monotonic() - factor_start
    M = LinearOperator(S.shape, matvec=factor.solve, dtype=float)
    save(folder / 'setup_result.json', dict(preparation_s=time.monotonic() - start,
        factorization_s=factor_s, fine_states=A.shape[0], fine_nnz=int(A.nnz),
        preconditioner_nnz=int(B.nnz), factor_L_nnz=int(factor.L.nnz), factor_U_nnz=int(factor.U.nnz),
        preconditioner_cleanup_threshold=1e-16, cleanup_entries=cleanup_count))
    results = []
    known = .1 * (np.sin(np.arange(A.shape[0]) * .013) + np.cos(np.arange(A.shape[0]) * .027))
    for label, rhs in [('known_solution', A @ known), ('native_Newton_RHS', rhs_native)]:
        count = 0
        scaled_rhs = row_scale * rhs
        def callback(value):
            nonlocal count
            count += 1
            if count % 10 == 0:
                save(folder / 'iteration_status.json', dict(case=label, iterations=count,
                    preconditioned_relative_residual=float(value)))
        solve_start = time.monotonic()
        z, info = gmres(S, scaled_rhs, M=M, rtol=1e-12, atol=0.,
            restart=50, maxiter=10, callback=callback, callback_type='pr_norm')
        x = col_scale * z
        residual = A @ x - rhs
        scaled_residual = float(np.linalg.norm(row_scale * residual) / np.linalg.norm(scaled_rhs))
        backward = float(np.max(abs(residual) / (abs(A) @ abs(x) + abs(rhs) + 1e-30)))
        assert np.isfinite(x).all()
        record = dict(case=label, iterations=count, scipy_info=int(info),
            solve_s=time.monotonic() - solve_start,
            scaled_true_relative_residual=scaled_residual,
            original_true_relative_residual=float(np.linalg.norm(residual, np.inf) / np.linalg.norm(rhs, np.inf)),
            maximum_componentwise_backward_error=backward,
            converged_at_requested_tolerance=info == 0 and scaled_residual <= 1e-12)
        if label == 'known_solution':
            record['known_solution_relative_error'] = float(np.linalg.norm(x - known, np.inf) / np.linalg.norm(known, np.inf))
        results.append(record)
        save(folder / 'solve_results.json', results)
    save(folder / 'numeric_result.json', dict(cases=results,
        both_captured_equation_tests_converged=all(case['converged_at_requested_tolerance'] for case in results),
        elapsed_s=time.monotonic() - start,
        maximum_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]; base = root / 'build/timing400/release_001'
    if args.worker: worker(args.output, base); return
    args.output = args.output.resolve(); args.output.mkdir(exist_ok=False)
    capture = base / 'DCO_native_linear_system_capture_002'
    assert json.loads((capture / 'assessment.json').read_text())['first_native_Jacobian_captured']
    inputs = [Path(__file__), capture / 'assessment.json', capture / 'native_Jacobian.npz',
        capture / 'native_RHS.npy', capture / 'native_variable_names.json',
        base / 'DCO_local_C_matrix_nom_no_substrate_G_001/nodes.json',
        base / 'DCO_local_C_matrix_nom_no_substrate_G_001/C_native_units.npz',
        base / 'DCO_domain_R_corners_002/nom_wire_R_unqualified.spice',
        base / 'DCO_complete_domain_model_primitives_001/device_connections.json',
        base / 'DCO_direct_native_planes_and_boundaries_001/boundary_connections.json']
    pins = {str(path.resolve()): digest(path) for path in inputs}
    save(args.output / 'input_manifest.json', dict(input_sha256=pins,
        actual_native_Jacobian_unchanged=True, actual_native_RHS_unchanged=True,
        preconditioner_only_approximation=True))
    save(args.output / 'owner.json', dict(runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(), kernel_wall_limit_s=180,
        address_space_limit_GiB=48, native_DCO_restarted=False))
    def status(state, **extra):
        save(args.output / 'status.json', dict(state=state, runner_pid=os.getpid(),
            release_qualified=False, adopted=False, **extra))
    with (args.output / 'worker.log').open('x') as log:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--output',
            str(args.output), '--worker'], stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True, env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'))
        status('offline_native_matrix_solver_running', worker_pid=child.pid)
        timed_out = False
        try: code = child.wait(timeout=180)
        except subprocess.TimeoutExpired:
            timed_out = True; os.killpg(child.pid, signal.SIGTERM)
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired: os.killpg(child.pid, signal.SIGKILL); child.wait()
            code = child.returncode
    result = args.output / 'numeric_result.json'
    metrics = json.loads(result.read_text()) if code == 0 and result.exists() else None
    assert all(digest(Path(name)) == value for name, value in pins.items())
    save(args.output / 'assessment.json', dict(worker_exit=code, timed_out=timed_out,
        metrics=metrics, input_sha256=pins, actual_native_matrix_tested=True,
        full_transient_tested=False, nonlinear_iteration_sequence_tested=False,
        full_DCO_speedup_demonstrated=False, release_qualified=False, adopted=False))
    status('timeout_inconclusive' if timed_out else ('completed_offline_solve' if metrics else 'worker_nonpass'))


if __name__ == '__main__': main()
