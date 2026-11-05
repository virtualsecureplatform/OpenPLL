#!/usr/bin/env python3
"""Independently check known solutions and roundoff-aware synthetic RHS inputs."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from scipy.sparse import load_npz


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    folder = base / 'native_warm_start_probe_checks_001'
    assessment = json.loads((folder / 'assessment.json').read_text())
    assert assessment['all_original_equation_residual_checks_passed']
    A = load_npz(base / 'DCO_native_linear_system_capture_002/native_Jacobian.npz').tocsr()
    maximum = np.asarray(abs(A).max(axis=1).toarray()).reshape(-1)
    scale = 1/maximum
    inputs = base / 'native_adapter_probe_inputs_001'
    native = np.fromfile(inputs / 'native_Newton_RHS.bin', dtype='<f8')
    known_rhs = np.fromfile(inputs / 'known_solution.bin', dtype='<f8')
    known = .1*(np.sin(np.arange(A.shape[0])*.013)+np.cos(np.arange(A.shape[0])*.027))
    # The C++ generator uses naive positive sums; fsum independently reduces
    # their rounding error. Pointwise relative comparisons fail near cancellation.
    nsum = math.fsum(float(value)**2 for value in native/maximum)
    ksum = math.fsum(float(value)**2 for value in known_rhs/maximum)
    beta = .001*math.sqrt(nsum/ksum)
    perturbed = native+beta*known_rhs
    eps = np.finfo(float).eps
    gamma_n = A.shape[0]*eps/(1-A.shape[0]*eps)
    generation_bound = 16*gamma_n*abs(beta*known_rhs)+16*eps*(abs(native)+abs(beta*known_rhs))
    records = []
    for case in assessment['checks']:
        label = case['case']
        rhs = np.fromfile(folder / (label+'.rhs.bin'), dtype='<f8')
        x = np.fromfile(folder / (label+'.bin'), dtype='<f8')
        synthetic = label.endswith('perturbed_native')
        expected = perturbed if synthetic else known_rhs if 'known_' in label else native
        if synthetic:
            assert np.all(abs(rhs-expected) <= generation_bound)
        else:
            assert np.array_equal(rhs, expected)
        residual = A@x-rhs
        relative = float(np.linalg.norm(scale*residual)/np.linalg.norm(scale*rhs))
        assert np.isfinite(x).all() and relative <= 1e-12
        record = dict(case=label, RHS_generation_checked=True,
            scaled_true_relative_residual=relative,
            RHS_reference_difference_relative=float(np.linalg.norm(scale*(rhs-expected))/np.linalg.norm(scale*expected)))
        if 'known_' in label:
            error = float(np.linalg.norm(x-known,np.inf)/np.linalg.norm(known,np.inf))
            assert error < 1e-7
            record['known_solution_relative_error'] = error
        records.append(record)
    output = folder / 'independent_known_solution_and_RHS_checks.json'
    assert not output.exists()
    result = dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        source_assessment_sha256=hashlib.sha256((folder / 'assessment.json').read_bytes()).hexdigest(),
        checks=records, RHS_rounding_bound_gamma_n=gamma_n,
        synthetic_RHS_generation_bound_only=True, solver_residual_threshold_unchanged=1e-12,
        initial_pointwise_relative_only_audit_failure_retained=True,
        actual_nonlinear_sequence_tested=False, live_solver_changed=False,
        release_qualified=False, adopted=False)
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(all_checks_passed=True,
        maximum_known_solution_relative_error=max(r.get('known_solution_relative_error',0) for r in records))))


if __name__ == '__main__':
    main()
