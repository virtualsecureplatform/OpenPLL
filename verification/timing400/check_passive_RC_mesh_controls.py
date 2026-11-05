#!/usr/bin/env python3
"""Independent rational Schur and signed-energy controls for branching meshes."""
from fractions import Fraction as F
import json
from pathlib import Path
import time
import numpy as np
from passive_RC_condensation import conductance
from passive_RC_mesh_condensation import harmonic_mesh
from compile_local_C_operators_v2 import digest, save


def main():
    base = Path(__file__).resolve().parents[2] / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    out = base / 'passive_RC_mesh_controls_001'; out.mkdir(exist_ok=False)
    cases = [([(1, 4, '60'), (2, 4, '120'), (3, 4, '240')], 5, [4]),
             ([(1, 5, '100'), (2, 5, '200'), (5, 6, '300'),
               (3, 6, '400'), (4, 6, '500')], 7, [5, 6])]
    results = []
    for branches, size, internal in cases:
        retained = list(range(size - len(internal)))
        T, kept, reduced, provenance = harmonic_mesh(size, branches, internal, set(retained))
        exact = [[F(0) for _ in range(size)] for _ in range(size)]
        for a, b, r in branches:
            g = 1 / F(r)
            exact[a][a] += g; exact[b][b] += g; exact[a][b] -= g; exact[b][a] -= g
        if len(internal) == 1:
            inverse = [[1 / exact[internal[0]][internal[0]]]]
        else:
            a, b = internal
            determinant = exact[a][a] * exact[b][b] - exact[a][b] * exact[b][a]
            inverse = [[exact[b][b] / determinant, -exact[a][b] / determinant],
                       [-exact[b][a] / determinant, exact[a][a] / determinant]]
        expected = np.asarray([[float(exact[a][b] - sum(
            exact[a][i] * inverse[ii][jj] * exact[j][b]
            for ii, i in enumerate(internal) for jj, j in enumerate(internal)))
            for b in retained] for a in retained])
        Gr = conductance(len(kept), reduced).toarray()
        relative = float(np.max(abs(Gr - expected)) / np.max(abs(expected)))
        assert relative < 1e-13
        # Explicit signed globally PSD capacitor energy, including a negative
        # scalar branch; projection must preserve the full quadratic form.
        C = np.zeros((size, size))
        for a, b, c in [(1, 0, 3.), (2, 0, 3.), (1, 2, -1.), (internal[0], 0, 2.)]:
            C[a, a] += c; C[b, b] += c; C[a, b] -= c; C[b, a] -= c
        assert np.linalg.eigvalsh(C).min() > -1e-12
        Cr = T.T @ C @ T
        v = np.linspace(-1, 1, len(kept)); full = T @ v
        energy_error = abs(float(v @ Cr @ v - full @ C @ full))
        assert energy_error < 1e-12 and np.linalg.eigvalsh(Cr).min() > -1e-12
        assert sorted(i for row in provenance for i in row['original_branch_indices']) == list(range(len(branches)))
        results.append(dict(internal_vertices=len(internal), rational_DC_relative_error=relative,
            signed_quadratic_energy_error=energy_error, equivalent_R_all_positive=all(float(r) > 0 for _, _, r in reduced)))
    try: harmonic_mesh(5, cases[0][0], [4], {4})
    except ValueError: pass
    else: raise AssertionError('Protected vertex elimination accepted')
    paths = [Path(__file__).resolve(), Path(__file__).with_name('passive_RC_mesh_condensation.py'),
             Path(__file__).with_name('passive_RC_condensation.py'), owner]
    save(out / 'assessment.json', dict(independent_rational_branching_RC_controls_passed=True,
        signed_quadratic_energy_controls_passed=True, protected_terminal_guard_passed=True, cases=results,
        oscillator_frequency_error_qualified=False, release_qualified=False, adopted=False,
        deadline_uptime=deadline, input_sha256={str(p.resolve()): digest(p) for p in paths}))
    print(json.dumps(results))


if __name__ == '__main__': main()
