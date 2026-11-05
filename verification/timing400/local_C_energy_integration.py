#!/usr/bin/env python3
"""Exact local overlap-capacitance energy on piecewise-linear voltage fields.

Integrate voltage products before forming the capacitance matrix. Averaging a
voltage field and then squaring it loses its within-tile variation. Positive
uniform patches retain an explicit positive Gram decomposition.
"""
from collections import defaultdict
from fractions import Fraction as F


def affine_basis(basis, x, y):
    axis = basis['axis']
    knots = basis['voltage_knots_internal']
    coordinate = [x, y][axis] if axis is not None else None
    if axis is None or coordinate <= knots[0][0]:
        return {knots[0][1]: (F(1), F(0), F(0))}
    if coordinate >= knots[-1][0]:
        return {knots[-1][1]: (F(1), F(0), F(0))}
    for (a, na), (b, nb) in zip(knots, knots[1:]):
        if a <= coordinate <= b:
            assert a < b and na != nb
            result = defaultdict(lambda: [F(0), F(0), F(0)])
            result[na][0] += F(b, b-a)
            result[na][axis+1] -= F(1, b-a)
            result[nb][0] -= F(a, b-a)
            result[nb][axis+1] += F(1, b-a)
            assert [sum(v[i] for v in result.values()) for i in range(3)] == [1, 0, 0]
            return {k: tuple(v) for k, v in result.items()}
    raise AssertionError((coordinate, knots))


def integrate_uniform_overlap(source, target, rectangle, density=F(1)):
    """Return symmetric upper matrix, positive Gram factors and subcell count.

    The quadratic form equals integral(density * (Vs(x,y)-Vt(x,y))**2).
    Factors prove positive semidefiniteness of this positive patch only.
    Geometry ownership and all signed shield/ground corrections are separate.
    """
    density = F(density)
    assert density >= 0
    l, b, r, t = map(F, rectangle)
    assert l < r and b < t
    cuts = [{l, r}, {b, t}]
    for basis in [source, target]:
        axis = basis['axis']
        if axis is not None:
            low, high = [(l, r), (b, t)][axis]
            cuts[axis].update(F(x) for x, _ in basis['voltage_knots_internal'] if low < x < high)
    xs, ys = [sorted(c) for c in cuts]
    matrix, factors, cells = defaultdict(F), [], 0
    for x0, x1 in zip(xs, xs[1:]):
        for y0, y1 in zip(ys, ys[1:]):
            xc, yc = (x0+x1)/2, (y0+y1)/2
            coefficients = defaultdict(lambda: [F(0), F(0), F(0)])
            for sign, basis in [(1, source), (-1, target)]:
                for node, polynomial in affine_basis(basis, xc, yc).items():
                    for i, v in enumerate(polynomial):
                        coefficients[node][i] += sign*v
            area = (x1-x0)*(y1-y0)
            vectors = [
                (density*area, {n: c+sx*xc+sy*yc for n, (c, sx, sy) in coefficients.items()}),
                (density*area*(x1-x0)**2/12, {n: v[1] for n, v in coefficients.items()}),
                (density*area*(y1-y0)**2/12, {n: v[2] for n, v in coefficients.items()}),
            ]
            for weight, vector in vectors:
                vector = {n: v for n, v in vector.items() if v}
                assert weight >= 0 and sum(vector.values()) == 0
                if not weight or not vector:
                    continue
                factors.append((weight, vector))
                ordered = sorted(vector)
                for i, na in enumerate(ordered):
                    for nb in ordered[i:]:
                        matrix[na, nb] += weight*vector[na]*vector[nb]
            cells += 1
    return {k: v for k, v in matrix.items() if v}, factors, cells


def quadratic_form(matrix, voltages):
    return sum(value*F(voltages[a])*F(voltages[b])*(1 if a == b else 2)
               for (a, b), value in matrix.items())


def controls():
    source = dict(axis=0, voltage_knots_internal=[(0, 'a'), (6, 'b')])
    ground = dict(axis=None, voltage_knots_internal=[(0, 'g')])
    matrix, factors, cells = integrate_uniform_overlap(source, ground, [0, 0, 6, 1])
    assert matrix == {('a', 'a'): F(2), ('a', 'b'): F(1), ('a', 'g'): F(-3),
                      ('b', 'b'): F(2), ('b', 'g'): F(-3), ('g', 'g'): F(6)}
    assert quadratic_form(matrix, dict(a=1, b=1, g=0)) == 6
    assert quadratic_form(matrix, dict(a=-1, b=1, g=0)) == 2
    # The average-voltage shortcut would yield zero for this linear field.
    wrong_average_energy = 6*(F(-1, 2)+F(1, 2))**2
    assert wrong_average_energy != 2
    sx = dict(axis=0, voltage_knots_internal=[(0, 'a'), (2, 'b')])
    ty = dict(axis=1, voltage_knots_internal=[(0, 'c'), (3, 'd')])
    matrix, factors, cells = integrate_uniform_overlap(sx, ty, [0, 0, 2, 3], F(2))
    assert quadratic_form(matrix, dict(a=0, b=2, c=0, d=3)) == 16
    assert quadratic_form(matrix, dict(a=1, b=1, c=0, d=0)) == 12
    # Check the independent positive-factor energy against the emitted matrix.
    for values in [dict(a=-2, b=3, c=5, d=-7), dict(a=1, b=1, c=1, d=1)]:
        energy = sum(w*sum(v*values[n] for n, v in vector.items())**2 for w, vector in factors)
        assert energy >= 0 and energy == quadratic_form(matrix, values)
    refined = dict(axis=0, voltage_knots_internal=[(0, 'a'), (1, 'm'), (2, 'b')])
    mm, _, cells = integrate_uniform_overlap(refined, ty, [0, 0, 2, 3], F(2))
    assert cells == 2 and quadratic_form(mm, dict(a=0, m=1, b=2, c=0, d=3)) == 16
    return dict(exact_linear_field_mass_matrix_passed=True,
        zero_wire_R_uniform_voltage_charge_conservation_passed=True,
        orthogonal_voltage_fields_exact_second_moment_passed=True,
        affine_mesh_refinement_invariance_passed=True,
        average_voltage_before_squaring_counterexample_rejected=True,
        explicit_nonnegative_Gram_factorization_matches_matrix=True)


if __name__ == '__main__':
    import json
    from pathlib import Path
    import time
    from run_dco_qualification import ROOT, sha, save
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < json.loads(owner.read_text())['deadline_uptime']
    result = controls()
    out = base/'local_C_energy_integration_controls_001'
    out.mkdir(exist_ok=False)
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in [Path(__file__).resolve(), owner]},
        artifacts={}, controls=result, positive_uniform_patch_energy_integrator_controls_passed=True,
        all_DCO_C_kernels_integrated=False, signed_global_capacitance_matrix_passivity_qualified=False,
        physical_RC_or_transient_error_qualified=False, runtime_model_eligible=False,
        release_qualified=False, adopted=False))
    print('Exact local capacitor energy controls passed; full DCO kernel assignment and global passivity remain open.')
