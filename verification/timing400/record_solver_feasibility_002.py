#!/usr/bin/env python3
"""Independently record completed offline preconditioner diagnostics and export control."""
import json
from pathlib import Path
import numpy as np
from scipy.io import mmread
from compile_local_C_operators_v2 import digest, save

root = Path(__file__).resolve().parents[2]
base = root / 'build/timing400/release_001'
out = base / 'solver_feasibility_checks_002'
out.mkdir(exist_ok=False)
pins = {str(Path(__file__).resolve()): digest(Path(__file__))}
results = {}
for name in ['passive_AMG_feasibility_001', 'wire_domain_preconditioner_feasibility_001',
             'wire_block_preconditioner_feasibility_001']:
    assessment = base / name / 'assessment.json'
    data = json.loads(assessment.read_text())
    assert not data['release_qualified'] and not data['adopted']
    for path, sha in data['input_sha256'].items():
        assert digest(Path(path)) == sha, path
    pins[str(assessment)] = digest(assessment)
    results[name] = dict(completed=data['offline_AMG_completed'], timed_out=data['timed_out'],
        metrics=data['metrics'])
assert results['passive_AMG_feasibility_001']['timed_out']
assert not results['wire_domain_preconditioner_feasibility_001']['metrics']['converged_at_requested_scaled_tolerance']
m = results['wire_block_preconditioner_feasibility_001']['metrics']
assert m['scipy_info'] == 0 and m['scaled_true_relative_residual'] < 1e-12
assert m['original_true_relative_residual'] < 1e-12 and m['known_solution_relative_error'] < 1e-7
control = base / 'native_matrix_export_control_001'
for filename in ['control.cir', 'native.log', 'names.log', 'solution.names',
                 'Base_Matrix1.mm', 'Base_RHS1.mm', 'Base_BlockMap.mm']:
    path = control / filename; pins[str(path)] = digest(path)
A = mmread(control / 'Base_Matrix1.mm').toarray()
rhs = np.asarray(mmread(control / 'Base_RHS1.mm')).reshape(-1)
assert A.shape == (13, 13) and rhs.shape == (13,)
assert np.isfinite(A).all() and np.isfinite(rhs).all()
mapping = dict((int(line.split()[0]), line.split()[1])
               for line in (control / 'solution.names').read_text().splitlines()[1:])
assert set(mapping) == set(range(13))
assert '***** End of Xyce(TM) Simulation' in (control / 'native.log').read_text()
x = np.linalg.solve(A, rhs)
error = float(np.linalg.norm(A @ x - rhs, np.inf))
assert error < 1e-15
save(out / 'assessment.json', dict(completed_offline_inputs_unchanged=True,
    passive_diagnostics=results, native_export_control_states=13,
    native_export_control_direct_residual_inf=error,
    export_control_matrix_and_names_validated=True, input_sha256=pins,
    full_DCO_speedup_demonstrated=False, release_qualified=False, adopted=False))
print(json.dumps(dict(passive_block_solve_s=m['solve_s'], passive_block_iterations=m['iterations'],
                     export_control_residual=error)))
