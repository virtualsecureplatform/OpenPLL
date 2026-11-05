#!/usr/bin/env python3
"""Screen a wire-component two-level preconditioner without reducing the fine model."""
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
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import cg
from compile_local_C_operators_v2 import digest, save


def worker(folder, source, package):
    resource.setrlimit(resource.RLIMIT_AS, (48 * 1024**3, 48 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (180, 181))
    sys.path.insert(0, str(package))
    import pyamg
    assert pyamg.__version__ == '5.3.0'
    start = time.monotonic(); A = load_npz(source).tocsr()
    diagonal = A.diagonal(); assert np.isfinite(A.data).all() and np.all(diagonal > 0)
    delta = A - A.T
    assert max(abs(delta.data), default=0.) < 1e-10 * max(abs(A.data))
    scale = 1. / np.sqrt(diagonal)
    S = (diags(scale) @ A @ diags(scale)).tocsr(); S.sort_indices()
    known = .1 * (np.sin(np.arange(A.shape[0]) * .013) + np.cos(np.arange(A.shape[0]) * .027))
    rhs = A @ known; scaled_rhs = scale * rhs
    setup_start = time.monotonic()
    base = source.parents[1]
    cfolder = base / 'DCO_local_C_matrix_nom_no_substrate_G_001'
    names = json.loads((cfolder / 'nodes.json').read_text())
    assert names[0] == '_dco_substrate_reference' and len(names) == A.shape[0] + 1
    index = {name: i - 1 for i, name in enumerate(names)}
    rows, cols = [], []
    branches = 0
    for line in (base / 'DCO_domain_R_corners_002/nom_wire_R_unqualified.spice').open():
        fields = line.split()
        if not fields or fields[0].startswith('*'): continue
        assert len(fields) == 4 and fields[0].upper().startswith('R')
        i, j = index[fields[1]], index[fields[2]]
        assert i >= 0 and j >= 0 and float(fields[3]) > 0
        rows.extend((i, j)); cols.extend((j, i)); branches += 1
    assert branches == 166286
    graph = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=A.shape).tocsr()
    groups, labels = connected_components(graph, directed=False)
    assert groups == 2686
    # Each resistor has both endpoints in one aggregate: G P_original = 0.
    assert np.all(labels[np.asarray(rows)] == labels[np.asarray(cols)])
    devices = base / 'DCO_complete_domain_model_primitives_001/device_connections.json'
    points = base / 'DCO_direct_native_planes_and_boundaries_001/boundary_connections.json'
    protected = {name for record in json.loads(devices.read_text()).values()
                 for name in record['private_terminals']}
    protected.update(record['private_node'] for record in json.loads(points.read_text()))
    shunts = np.full(len(names) - 1, 1e-12)
    for name in protected:
        assert index[name] >= 0
        shunts[index[name]] += 1e-3
    C = (load_npz(cfolder / 'C_native_units.npz')[1:, 1:] * (1e-18 / 10e-12)).tocoo()
    # Assemble P_original.T (C/h + shunts) P_original directly to avoid
    # cancellation of large conductance entries whose exact aggregate sum is zero.
    coarse = coo_matrix((C.data, (labels[C.row], labels[C.col])),
                        shape=(groups, groups)).tocsr()
    coarse += diags(np.bincount(labels, weights=shunts, minlength=groups))
    norms = np.sqrt(np.bincount(labels, weights=diagonal, minlength=groups))
    P = coo_matrix((np.sqrt(diagonal) / norms[labels],
                   (np.arange(A.shape[0]), labels)), shape=(A.shape[0], groups)).tocsr()
    coarse = (diags(1 / norms) @ coarse @ diags(1 / norms)).tocsr()
    coarse_delta = coarse - coarse.T
    assert max(abs(coarse_delta.data), default=0.) < 1e-10 * max(abs(coarse.data))
    # Only the preconditioner is symmetrized; S and A stay untouched.
    coarse = ((coarse + coarse.T) * .5).tocsr()
    from pyamg.multilevel import MultilevelSolver
    from pyamg.relaxation.smoothing import change_smoothers
    levels = [MultilevelSolver.Level(), MultilevelSolver.Level()]
    levels[0].A = S; levels[0].P = P; levels[0].R = P.T.tocsr()
    levels[1].A = coarse
    ml = MultilevelSolver(levels, coarse_solver='splu')
    change_smoothers(ml, presmoother=('gauss_seidel', {'sweep': 'forward'}),
                     postsmoother=('gauss_seidel', {'sweep': 'backward'}))
    setup_s = time.monotonic() - setup_start
    save(folder / 'setup_result.json', dict(setup_s=setup_s, levels=len(ml.levels),
        level_shapes=[list(level.A.shape) for level in ml.levels],
        level_nnz=[int(level.A.nnz) for level in ml.levels], operator_complexity=ml.operator_complexity()))
    count = 0
    def callback(vector):
        nonlocal count
        count += 1
        if count % 10 == 0:
            save(folder / 'iteration_status.json', dict(iterations=count,
                scaled_true_relative_residual=float(np.linalg.norm(S @ vector - scaled_rhs) / np.linalg.norm(scaled_rhs))))
    solve_start = time.monotonic()
    z, info = cg(S, scaled_rhs, M=ml.aspreconditioner(), rtol=1e-12, atol=0., maxiter=300, callback=callback)
    solve_s = time.monotonic() - solve_start
    actual = scale * z
    true_relative = float(np.linalg.norm(A @ actual - rhs, np.inf) / np.linalg.norm(rhs, np.inf))
    scaled_relative = float(np.linalg.norm(S @ z - scaled_rhs) / np.linalg.norm(scaled_rhs))
    solution_error = float(np.linalg.norm(actual - known, np.inf) / np.linalg.norm(known, np.inf))
    assert np.isfinite(actual).all()
    save(folder / 'numeric_result.json', dict(AMG_setup_and_solve_completed=True,
        solver='CG_with_wire_component_two_level_preconditioner', setup_s=setup_s, solve_s=solve_s,
        elapsed_s=time.monotonic() - start, iterations=count, scipy_info=int(info),
        scaled_true_relative_residual=scaled_relative, original_true_relative_residual=true_relative,
        known_solution_relative_error=solution_error,
        converged_at_requested_scaled_tolerance=info == 0 and scaled_relative <= 1e-12,
        maximum_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        preconditioner_operator_complexity=ml.operator_complexity()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    source = root / 'build/timing400/release_001/passive_SuperLU_feasibility_001/numeric_matrix.npz'
    package = root / 'build/timing400/amg_tools_001/site'
    if args.worker: worker(args.output, source, package); return
    base = root / 'build/timing400/release_001'
    prior = base / 'passive_SuperLU_feasibility_001/input_manifest.json'
    old = json.loads(prior.read_text()); assert digest(source) == old['matrix_sha256']
    terminal = base / 'campaign_deadline_001/assessment.json'
    assert json.loads(terminal.read_text())['original_runs_stopped']
    args.output.mkdir(exist_ok=False)
    save(args.output / 'owner.json', dict(runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(), offline_linear_algebra_only=True,
        kernel_wall_limit_s=180, address_space_limit_GiB=48,
        native_DCO_restarted=False, completed_campaign_extended=False))
    def status(state, **extra):
        save(args.output / 'status.json', dict(state=state, runner_pid=os.getpid(),
            release_qualified=False, adopted=False, **extra))
    inputs = [Path(__file__), source, prior, terminal, package.parent / 'source_manifest.json',
        base / 'DCO_local_C_matrix_nom_no_substrate_G_001/nodes.json',
        base / 'DCO_local_C_matrix_nom_no_substrate_G_001/C_native_units.npz',
        base / 'DCO_domain_R_corners_002/nom_wire_R_unqualified.spice',
        base / 'DCO_complete_domain_model_primitives_001/device_connections.json',
        base / 'DCO_direct_native_planes_and_boundaries_001/boundary_connections.json']
    inputs.extend(path for path in package.rglob('*') if path.is_file() and '__pycache__' not in path.parts)
    pins = {str(path.resolve()): digest(path) for path in inputs}
    save(args.output / 'input_manifest.json', dict(input_sha256=pins,
        same_shunted_passive_workload_as_prior_SuperLU=True, nonlinear_Jacobians_and_MNA_omitted=True,
        coarse_basis='one_constant_per_actual_resistor_connected_component',
        coarse_matrix='P.T_(C_over_h_plus_shunts)_P_with_exact_G_nullspace',
        fine_matrix_unchanged=True,
        native_model_changed=False, completed_campaign_extended=False))
    with (args.output / 'worker.log').open('x') as log:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--output',
            str(args.output.resolve()), '--worker'], stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True, env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'))
        status('offline_AMG_running', worker_pid=child.pid)
        timed_out = False
        try: code = child.wait(timeout=180)
        except subprocess.TimeoutExpired:
            timed_out = True; os.killpg(child.pid, signal.SIGTERM)
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired: os.killpg(child.pid, signal.SIGKILL); child.wait()
            code = child.returncode
    result_path = args.output / 'numeric_result.json'
    completed = code == 0 and result_path.exists()
    assert all(digest(Path(name)) == value for name, value in pins.items())
    save(args.output / 'assessment.json', dict(offline_AMG_completed=completed,
        timed_out=timed_out, worker_exit=code,
        metrics=json.loads(result_path.read_text()) if completed else None,
        same_regularized_passive_workload_as_SuperLU=True,
        actual_nonlinear_MNA_Jacobian_tested=False, full_DCO_speedup_demonstrated=False,
        native_DCO_restarted=False, completed_campaign_extended=False,
        release_qualified=False, adopted=False, input_sha256=pins))
    status('completed_offline_AMG' if completed else ('timeout_inconclusive' if timed_out else 'worker_nonpass'), worker_exit=code)


if __name__ == '__main__':
    main()
