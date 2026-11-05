#!/usr/bin/env python3
"""Audit the stock nonlinear adapters before proposing factor-reuse settings."""
import json
from pathlib import Path
from compile_local_C_operators_v2 import digest, save


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    source = Path('/opt/Xyce/src/NonlinearSolverPKG')
    core = source / 'N_NLS_NonLinearSolver.C'
    adapter = source / 'N_NLS_NOX_Interface.C'
    direction = Path('/opt/Trilinos/packages/nox/src/NOX_Direction_ModifiedNewton.C')
    cache = base / 'stock_threaded_Xyce_001/trilinos-build/CMakeCache.txt'
    a = core.read_text(); start = a.index('bool NonLinearSolver::newton_()')
    body = a[start:a.index('\n}', start) + 2]
    assert 'lasSolverRCPtr_->solve( false )' in body
    a = adapter.read_text(); start = a.index('bool Interface::computeNewton(Teuchos::ParameterList& params)')
    nox_body = a[start:a.index('\n}', start) + 2]
    assert 'return Nonlinear::NonLinearSolver::newton_();' in nox_body
    assert '#ifdef WITH_PRERELEASE' in direction.read_text()
    assert 'NOX_BUILD_PRERELEASE:BOOL=OFF' in cache.read_text()
    out = base / 'stock_newton_factor_reuse_audit_001'; out.mkdir(exist_ok=False)
    paths = [Path(__file__), core, adapter, direction, cache]
    save(out / 'assessment.json', dict(stock_nonlinear_adapter_inspected=True,
        base_Newton_linear_solve_requests_reuse_factors_false=True,
        NOX_Newton_adapter_calls_same_base_solver=True,
        modified_Newton_implementation_prerelease_guarded=True,
        current_SDK_NOX_prerelease_enabled=False,
        enabling_modified_Newton_alone_demonstrates_numeric_factor_reuse=False,
        factor_reuse_speed_fix_qualified=False, native_DCO_restarted=False,
        source_code_modified=False, completed_campaign_extended=False,
        release_qualified=False, adopted=False,
        inspected_base_method=body, inspected_NOX_method=nox_body,
        input_sha256={str(path.resolve()): digest(path) for path in paths}))
    print('Stock modified-Newton configuration does not provide the proposed numeric-factor reuse fix.')


if __name__ == '__main__':
    main()
