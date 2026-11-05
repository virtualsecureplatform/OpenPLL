#!/usr/bin/env python3
"""Offline comparison on one captured Jacobian; no transient/model adoption."""
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import signal
import time
import numpy as np
from scipy.sparse import csr_matrix, diags, load_npz
from scipy.sparse.linalg import LinearOperator, gmres, splu
from compile_local_C_operators_v2 import digest, save


def main():
    started = time.monotonic()
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (180, 181))
    def expired(*_):
        raise TimeoutError('180-second offline comparison deadline')
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(180)
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    out = base / 'retained_C_preconditioner_comparison_001'
    out.mkdir(exist_ok=False)
    save(out / 'owner.json', dict(started_utc=datetime.now(timezone.utc).isoformat(),
        wall_limit_s=180, address_space_limit_GiB=8, native_process_started=False))
    try:
        capture = base / 'DCO_native_linear_system_capture_002'
        metadata = base / 'native_wire_preconditioner_metadata_001/wire_C.bin'
        paths = [Path(__file__).resolve(), capture / 'native_Jacobian.npz',
                 capture / 'native_RHS.npy', capture / 'assessment.json', metadata]
        pins = {str(p): digest(p) for p in paths}
        A = load_npz(capture / 'native_Jacobian.npz').tocsr()
        A.sort_indices()
        rhs = np.load(capture / 'native_RHS.npy')
        with metadata.open('rb') as stream:
            assert stream.read(8) == b'OPLLCAP1'
            n, m = np.fromfile(stream, dtype=np.int32, count=2)
            ptr = np.fromfile(stream, dtype=np.int32, count=int(n)+1)
            cols = np.fromfile(stream, dtype=np.int32, count=int(m))
            cap = np.fromfile(stream, dtype=np.float64, count=int(m))
            keep = np.fromfile(stream, dtype=np.uint8, count=int(m))
            sample = np.fromfile(stream, dtype=np.uint8, count=int(m))
            assert stream.read() == b''
        assert A.shape == (n, n) and rhs.shape == (n,)
        C = csr_matrix((cap, cols, ptr), shape=A.shape)
        rowids = np.repeat(np.arange(n), np.diff(ptr))
        chosen = sample.astype(bool)
        ratios = np.asarray(A[rowids[chosen], cols[chosen]]).reshape(-1)/cap[chosen]
        alpha = float(np.median(ratios))
        assert alpha > 0 and np.max(abs(ratios/alpha-1)) < 1e-9
        row_scale = 1/np.asarray(abs(A).max(axis=1).toarray()).reshape(-1)
        RA = diags(row_scale) @ A
        col_scale = 1/np.asarray(abs(RA).max(axis=0).toarray()).reshape(-1)
        S = (RA @ diags(col_scale)).tocsr()
        scaled_rhs = row_scale*rhs
        results = []
        for label, retained in [('remove_all_wire_C_offdiagonal', False),
                                ('retain_C_on_existing_R_device_pairs', True)]:
            removal = C.copy()
            if retained:
                removal.data[keep.astype(bool)] = 0
                removal.eliminate_zeros()
            B = (A-alpha*removal).tocsr()
            # Match the existing offline prototype's subtraction-remnant cleanup.
            # This is not a native KLU graph/performance measurement.
            B.data[abs(B.data) < 1e-16] = 0
            B.eliminate_zeros()
            BS = (diags(row_scale) @ B @ diags(col_scale)).tocsc()
            before = time.monotonic()
            lu = splu(BS, permc_spec='COLAMD')
            factor_s = time.monotonic()-before
            M = LinearOperator(S.shape, matvec=lu.solve, dtype=float)
            residuals = []
            before = time.monotonic()
            z, info = gmres(S, scaled_rhs, M=M, rtol=1e-12, atol=0,
                restart=50, maxiter=6, callback=residuals.append, callback_type='pr_norm')
            elapsed = time.monotonic()-before
            true_residual = float(np.linalg.norm(S@z-scaled_rhs)/np.linalg.norm(scaled_rhs))
            assert np.isfinite(z).all()
            results.append(dict(case=label, factor_s=factor_s, solve_s=elapsed,
                iterations=len(residuals), scipy_info=int(info),
                scaled_true_relative_residual=true_residual,
                converged=info == 0 and true_residual <= 1e-12,
                approximation_nnz=int(B.nnz), factor_nnz=int(lu.L.nnz+lu.U.nnz)))
            save(out / 'solve_results.json', results)
        for path, sha in pins.items():
            assert digest(path) == sha, path
        save(out / 'assessment.json', dict(input_sha256=pins, results=results,
            captured_alpha_per_s=alpha, elapsed_s=time.monotonic()-started,
            original_captured_matrix_and_RHS_unchanged=True,
            full_transient_tested=False, nonlinear_sequence_tested=False,
            native_KLU_performance_tested=False, release_qualified=False, adopted=False))
        signal.alarm(0)
        print(json.dumps(results))
    except Exception as error:
        signal.alarm(0)
        save(out / 'failure_receipt.json', dict(error_type=type(error).__name__,
            message=str(error), elapsed_s=time.monotonic()-started,
            release_qualified=False, adopted=False))
        raise


if __name__ == '__main__':
    main()
