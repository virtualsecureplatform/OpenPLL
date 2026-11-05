#!/usr/bin/env python3
"""Bounded offline SuperLU feasibility test; no circuit or calibration adoption."""
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
import scipy
from scipy.sparse import coo_matrix, diags, load_npz, save_npz
from scipy.sparse.linalg import splu
from scipy.sparse.linalg._dsolve import _superlu
from compile_local_C_operators_v2 import digest, save


def child(folder):
    resource.setrlimit(resource.RLIMIT_AS, (48 * 1024**3, 48 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (180, 181))
    matrix = load_npz(folder / 'numeric_matrix.npz').tocsc()
    known = .1 * (np.sin(np.arange(matrix.shape[0]) * .013) +
                  np.cos(np.arange(matrix.shape[0]) * .027))
    rhs = matrix @ known
    start = time.monotonic()
    factor = splu(matrix, permc_spec='MMD_AT_PLUS_A')
    factor_s = time.monotonic() - start
    start = time.monotonic(); actual = factor.solve(rhs); solve_s = time.monotonic() - start
    relative_residual = float(np.linalg.norm(matrix @ actual - rhs, np.inf) / np.linalg.norm(rhs, np.inf))
    relative_solution_error = float(np.linalg.norm(actual - known, np.inf) / np.linalg.norm(known, np.inf))
    assert np.isfinite(actual).all() and relative_residual < 1e-8
    save(folder / 'numeric_result.json', dict(factorization_completed=True,
        ordering='MMD_AT_PLUS_A', factorization_s=factor_s, triangular_solve_s=solve_s,
        L_nnz=int(factor.L.nnz), U_nnz=int(factor.U.nnz),
        relative_residual=relative_residual, known_solution_relative_error=relative_solution_error,
        maximum_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--child', action='store_true')
    args = parser.parse_args()
    if args.child: child(args.output); return
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    terminal = base / 'campaign_deadline_001/assessment.json'
    assert json.loads(terminal.read_text())['original_runs_stopped']
    start = time.monotonic()
    args.output.mkdir(exist_ok=False)
    save(args.output / 'owner.json', dict(runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(), offline_linear_algebra_only=True,
        completed_campaign_extended=False, native_DCO_restarted=False,
        factor_wall_limit_s=180, factor_address_space_limit_GiB=48))
    def status(state, **extra):
        save(args.output / 'status.json', dict(state=state, runner_pid=os.getpid(),
            release_qualified=False, adopted=False, **extra))
    status('preparing_passive_matrix')
    folder = base / 'DCO_local_C_matrix_nom_no_substrate_G_001'
    names = json.loads((folder / 'nodes.json').read_text())
    assert names[0] == '_dco_substrate_reference'
    index = {name: i for i, name in enumerate(names)}
    C = load_npz(folder / 'C_native_units.npz').tocsc() * 1e-18
    rfile = base / 'DCO_domain_R_corners_002/nom_wire_R_unqualified.spice'
    rr, cc, vv = [], [], []; branches = 0
    for line in rfile.open():
        fields = line.split()
        if not fields or fields[0].startswith('*'): continue
        assert len(fields) == 4 and fields[0].upper().startswith('R')
        a, b = index[fields[1]], index[fields[2]]; g = 1. / float(fields[3])
        assert g > 0 and np.isfinite(g)
        rr.extend([a, b, a, b]); cc.extend([a, b, b, a]); vv.extend([g, g, -g, -g]); branches += 1
    assert branches == 166286
    G = coo_matrix((vv, (rr, cc)), shape=C.shape).tocsc()
    devices = base / 'DCO_complete_domain_model_primitives_001/device_connections.json'
    points = base / 'DCO_direct_native_planes_and_boundaries_001/boundary_connections.json'
    protected = {name for record in json.loads(devices.read_text()).values()
                 for name in record['private_terminals']}
    protected.update(record['private_node'] for record in json.loads(points.read_text()))
    shunts = np.full(len(names), 1e-12)
    for name in protected: shunts[index[name]] += 1e-3
    matrix = (G + C / 10e-12 + diags(shunts, format='csc'))[1:, 1:].tocsc()
    matrix.eliminate_zeros(); matrix.sort_indices()
    matrix_path = args.output / 'numeric_matrix.npz'; save_npz(matrix_path, matrix)
    inputs = [Path(__file__), terminal, folder / 'nodes.json', folder / 'C_native_units.npz',
              rfile, devices, points, Path(_superlu.__file__)]
    pins = {str(path.resolve()): digest(path) for path in inputs}
    metadata = dict(states=matrix.shape[0], numeric_nnz=matrix.nnz, R_branches=branches,
        timestep_s=10e-12, all_node_regularization_S=1e-12, protected_port_shunt_S=1e-3,
        modified_passive_workload_only=True, transistor_Jacobians_and_MNA_sources_omitted=True,
        numpy_version=np.__version__, scipy_version=scipy.__version__,
        input_sha256=pins, matrix_sha256=digest(matrix_path))
    save(args.output / 'input_manifest.json', metadata)
    del matrix, C, G, rr, cc, vv
    with (args.output / 'factor.log').open('x') as log:
        proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--output',
            str(args.output.resolve()), '--child'], stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True, env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'))
        status('offline_factorization_running', factor_pid=proc.pid)
        try: code = proc.wait(timeout=180)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: os.killpg(proc.pid, signal.SIGKILL); proc.wait()
            code = proc.returncode
            status('factor_timeout_inconclusive', factor_exit=code)
    proof = args.output / 'numeric_result.json'
    completed = code == 0 and proof.exists()
    assert all(digest(Path(name)) == value for name, value in pins.items())
    save(args.output / 'assessment.json', dict(offline_passive_factorization_completed=completed,
        factor_exit=code, elapsed_including_preparation_s=time.monotonic() - start,
        metrics=json.loads(proof.read_text()) if completed else None,
        workload=metadata, nonlinear_or_MNA_factorization_tested=False,
        full_DCO_speedup_demonstrated=False, general_solver_equivalence_qualified=False,
        native_DCO_restarted=False, completed_campaign_extended=False,
        release_qualified=False, adopted=False))
    status('completed_offline_factorization' if completed else 'offline_factorization_nonpass', factor_exit=code)


if __name__ == '__main__':
    main()
