#!/usr/bin/env python3
"""Centered voltage-product integrals for signed local C operators.

Area/line moments are exact polynomial formulas in floating arithmetic.
Fringe moments integrate the recorded arctan density, retaining normal and
tangential field variation. Eight-point Gauss integration uses bounded-width
panels; independent adaptive quadrature controls test its error.
"""
from bisect import bisect_right
from collections import defaultdict
import math

# Positive abscissae/weights of Gauss-Legendre order 8 on [-1,1].
GAUSS = ((.1834346424956498, .3626837833783620),
         (.5255324099163290, .3137066458778873),
         (.7966664774136267, .2223810344533745),
         (.9602898564975363, .1012285362903763))


def basis_at(basis, x, y):
    axis, knots = basis['axis'], basis['voltage_knots_internal']
    if axis is None:
        return {knots[0][1]: (1., 0., 0.)}
    coordinate = (x, y)[axis]
    if coordinate <= knots[0][0]:
        return {knots[0][1]: (1., 0., 0.)}
    if coordinate >= knots[-1][0]:
        return {knots[-1][1]: (1., 0., 0.)}
    index = bisect_right([p[0] for p in knots], coordinate)
    (lo, a), (hi, b) = knots[index-1:index+1]
    width = hi-lo
    assert width > 0 and a != b
    slope = 1./width
    fraction = (coordinate-lo)*slope
    return {a: (1.-fraction, -slope if axis == 0 else 0., -slope if axis == 1 else 0.),
            b: (fraction, slope if axis == 0 else 0., slope if axis == 1 else 0.)}


def cuts(bases, rectangle, projected_axis=None):
    out = [{rectangle[0], rectangle[2]}, {rectangle[1], rectangle[3]}]
    for index, basis in enumerate(bases):
        axis = basis['axis']
        if axis is not None and not (index == 0 and axis == projected_axis):
            out[axis].update(p for p, _ in basis['voltage_knots_internal']
                             if rectangle[axis] < p < rectangle[axis+2])
    return [sorted(s) for s in out]


def difference(source, target, source_point, target_point, zero_source_axis=None):
    result = defaultdict(lambda: [0., 0., 0.])
    for sign, basis, point in [(1, source, source_point), (-1, target, target_point)]:
        for node, values in basis_at(basis, *point).items():
            for axis, value in enumerate(values):
                if sign == 1 and axis == (zero_source_axis+1 if zero_source_axis is not None else -1):
                    continue
                result[node][axis] += sign*value
    return {n: v for n, v in result.items() if any(v)}


def add_moments(matrix, vector, factor, xx=0., yy=0., xmean=0., ymean=0.):
    ordered = sorted(vector)
    for i, a in enumerate(ordered):
        va, ax, ay = vector[a]
        for b in ordered[i:]:
            vb, bx, by = vector[b]
            value = factor*(va*vb + xx*ax*bx + yy*ay*by
                            + xmean*(va*bx+ax*vb) + ymean*(va*by+ay*vb))
            if value:
                matrix[a, b] += value


def area(source, target, rectangle, density):
    matrix = defaultdict(float)
    xs, ys = cuts([source, target], rectangle)
    for x0, x1 in zip(xs, xs[1:]):
        for y0, y1 in zip(ys, ys[1:]):
            point = ((x0+x1)/2., (y0+y1)/2.)
            vector = difference(source, target, point, point)
            add_moments(matrix, vector, density*(x1-x0)*(y1-y0), (x1-x0)**2/12., (y1-y0)**2/12.)
    return dict(matrix)


def line(source, target, source_edge, target_edge, density):
    along = 1 if source_edge[0] == source_edge[2] else 0
    normal = 1-along
    assert source_edge[along:along+1] == target_edge[along:along+1]
    assert source_edge[along+2] == target_edge[along+2]
    low, high = source_edge[along], source_edge[along+2]
    points = {low, high}
    for basis in [source, target]:
        if basis['axis'] == along:
            points.update(p for p, _ in basis['voltage_knots_internal'] if low < p < high)
    points = sorted(points)
    matrix = defaultdict(float)
    for lo, hi in zip(points, points[1:]):
        a, b = list(source_edge[:2]), list(target_edge[:2])
        a[along] = b[along] = (lo+hi)/2.
        vector = difference(source, target, a, b)
        # Each voltage is evaluated on its own physical line, with no normal
        # variation in the integration coordinate.
        for values in vector.values():
            values[normal+1] = 0.
        moment = (hi-lo)**2/12.
        add_moments(matrix, vector, density*(hi-lo), moment if along == 0 else 0., moment if along == 1 else 0.)
    return dict(matrix)


def fringe_moments(near, far, mult):
    """Return integral rho(d)*(1, d-center, (d-center)^2).

    rho=.6366*m/(1+(m*d)^2). Panel width in the arctan transition
    coordinate is <=.5; no subtraction of nearly equal second moments.
    """
    assert 0 <= near <= far and mult >= 0
    if mult == 0 or far == near:
        return 0., 0., 0.
    center = (near+far)/2.
    lo, result = near, [[], [], []]
    while lo < far:
        hi = min(far, lo + .5*math.hypot(1., mult*lo)/mult)
        assert hi > lo
        midpoint, half = (lo+hi)/2., (hi-lo)/2.
        for node, weight in GAUSS:
            for sign in [-1, 1]:
                d = midpoint+sign*half*node
                z = d-center
                w = half*weight*.6366*mult/(1.+(mult*d)**2)
                result[0].append(w)
                result[1].append(w*z)
                result[2].append(w*z*z)
        lo = hi
    return tuple(math.fsum(v) for v in result)


def fringe(source, target, source_edge, rectangle, direction, cap, mult):
    normal = 0 if direction in [1, 4] else 1
    along = 1-normal
    sign = -1 if direction in [1, 8] else 1
    origin = source_edge[normal]
    xs, ys = cuts([source, target], rectangle, projected_axis=normal)
    matrix = defaultdict(float)
    for x0, x1 in zip(xs, xs[1:]):
        for y0, y1 in zip(ys, ys[1:]):
            bounds = [(x0, x1), (y0, y1)]
            near, far = sorted(sign*(v-origin) for v in bounds[normal])
            m0, m1, m2 = fringe_moments(near, far, mult)
            if m0 == 0:
                continue
            point = ((x0+x1)/2., (y0+y1)/2.)
            projected = list(point)
            projected[normal] = origin
            vector = difference(source, target, projected, point, zero_source_axis=normal)
            moments = [0., 0.]
            moments[normal] = m2/m0
            moments[along] = (bounds[along][1]-bounds[along][0])**2/12.
            mean = [0., 0.]
            mean[normal] = sign*m1/m0
            add_moments(matrix, vector, cap*m0*(bounds[along][1]-bounds[along][0]), *moments, *mean)
    return dict(matrix)


def controls():
    from fractions import Fraction
    from scipy.integrate import quad
    from local_C_energy_integration import integrate_uniform_overlap
    ground = dict(axis=None, voltage_knots_internal=[(0, 'g')])
    sx = dict(axis=0, voltage_knots_internal=[(0, 'a'), (2, 'b'), (6, 'c')])
    sy = dict(axis=1, voltage_knots_internal=[(0, 'd'), (3, 'e')])
    checks = 0
    for source, target, box in [(sx, sy, [0, 0, 6, 3]), (sx, ground, [0, 0, 6, 1])]:
        exact, _, _ = integrate_uniform_overlap(source, target, box, Fraction(2))
        numeric = area(source, target, box, 2.)
        for key in set(exact) | set(numeric):
            assert abs(float(exact.get(key, 0))-numeric.get(key, 0)) < 1e-13
        checks += 1
    # Normal voltage gradients contribute a constant evaluated on each edge;
    # tangential gradients retain their exact variance.
    mm = line(sx, ground, [0, 0, 6, 0], [0, 4, 6, 4], 1.)
    exact, _, _ = integrate_uniform_overlap(sx, ground, [0, 0, 6, 1])
    assert all(abs(mm.get(k, 0)-float(v)) < 1e-13 for k, v in exact.items())
    moment_cases = 0
    for near, far, mult in [(0., 2000., .1), (1999., 2000., .1), (0., 1., 1e-12),
                            (10., 11., 1e4), (0., 100., 10.), (0., 100., 0.), (.01, .010001, 1e-3)]:
        values = fringe_moments(near, far, mult)
        center = (near+far)/2.
        for power, value in enumerate(values):
            reference, error = quad(lambda d: .6366*mult/(1+(mult*d)**2)*(d-center)**power,
                near, far, epsabs=1e-13, epsrel=1e-12, limit=400)
            assert abs(value-reference) <= 3e-12*max(abs(reference), 1e-14), (near, far, mult, power, value, reference, error)
            moment_cases += 1
    # All four physical directions, two independent voltage axes, actual
    # projected source point, and signed coefficients vs adaptive quadrature.
    field_cases = 0
    for direction in [1, 2, 4, 8]:
        normal = 0 if direction in [1, 4] else 1
        along = 1-normal
        sign = -1 if direction in [1, 8] else 1
        edge = [0, 0, 0, 3] if normal == 0 else [0, 0, 3, 0]
        box = [-4, 0, -1, 3] if direction == 1 else ([1, 0, 4, 3] if direction == 4 else ([0, 1, 3, 4] if direction == 2 else [0, -4, 3, -1]))
        source = dict(axis=along, voltage_knots_internal=[(0, 'a'), (3, 'b')])
        target = dict(axis=normal, voltage_knots_internal=[(-4, 'c'), (4, 'd')])
        for cap in [-2., 2.]:
            matrix = fringe(source, target, edge, box, direction, cap, .2)
            voltage = dict(a=-1., b=2., c=3., d=-2.)
            actual = math.fsum(v*voltage[a]*voltage[b]*(1 if a == b else 2) for (a, b), v in matrix.items())
            def normal_energy(d):
                def along_energy(u):
                    p = [0., 0.]
                    p[along], p[normal] = u, sign*d
                    q = list(p)
                    q[normal] = 0.
                    va = sum(v[0]*voltage[n] for n, v in basis_at(source, *q).items())
                    vb = sum(v[0]*voltage[n] for n, v in basis_at(target, *p).items())
                    return (va-vb)**2
                return cap*.6366*.2/(1+(.2*d)**2)*quad(along_energy, 0, 3, epsabs=1e-12)[0]
            reference = quad(normal_energy, 1, 4, epsabs=1e-12)[0]
            assert abs(actual-reference) < 1e-11, (direction, cap, actual, reference)
            row_sums = defaultdict(float)
            for (a, b), value in matrix.items():
                row_sums[a] += value
                if a != b:
                    row_sums[b] += value
            assert max(map(abs, row_sums.values())) < 1e-12
            field_cases += 1
    return dict(exact_rational_area_matrix_comparisons=checks, exact_line_mass_matrix_passed=True,
        independent_adaptive_fringe_moment_comparisons=moment_cases,
        signed_fringe_field_energy_and_charge_conservation_cases=field_cases,
        global_signed_DCO_passivity_qualified=False)
