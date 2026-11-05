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


def export(folder, base):
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
    def matrix(path, value):
        value = value.tocsr(); value.sort_indices()
        assert value.shape[0] == value.shape[1] and value.nnz < 2**31
        with path.open('xb') as handle:
            np.array([value.shape[0], value.nnz], dtype='<i4').tofile(handle)
            np.asarray(value.indptr, dtype='<i4').tofile(handle)
            np.asarray(value.indices, dtype='<i4').tofile(handle)
            np.asarray(value.data, dtype='<f8').tofile(handle)
    matrix(folder / 'scaled_A.bin', S)
    matrix(folder / 'scaled_B.bin', BS)
    known = .1 * (np.sin(np.arange(A.shape[0]) * .013) + np.cos(np.arange(A.shape[0]) * .027))
    for label, rhs in [('known_solution', A @ known), ('native_Newton_RHS', rhs_native)]:
        np.asarray(row_scale * rhs, dtype='<f8').tofile(folder / (label + '.bin'))
    np.save(folder / 'row_scale.npy', row_scale)
    np.save(folder / 'col_scale.npy', col_scale)
    (folder / 'dimensions.txt').write_text(str(A.shape[0]) + '\n')
    original = base / 'native_capacitance_preconditioner_feasibility_001/assessment.json'
    inputs = [Path(__file__), original,
        capture / 'native_Jacobian.npz', capture / 'native_RHS.npy',
        capture / 'native_variable_names.json', cfolder / 'C_native_units.npz',
        cfolder / 'nodes.json', devices, points,
        base / 'DCO_domain_R_corners_002/nom_wire_R_unqualified.spice']
    pins = {str(path.resolve()): digest(path) for path in inputs}
    save(folder / 'assessment.json', dict(native_equations_exported=True,
        scaling_only_on_fine_equations=True, preconditioner_only_approximation=True,
        input_sha256=pins, artifacts={str(p): digest(p) for p in folder.iterdir() if p.suffix in ['.bin','.npy']},
        fine_states=A.shape[0], fine_nnz=int(S.nnz), preconditioner_nnz=int(BS.nnz),
        release_qualified=False, adopted=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve(); args.output.mkdir(exist_ok=False)
    export(args.output, Path(__file__).resolve().parents[2] / 'build/timing400/release_001')
