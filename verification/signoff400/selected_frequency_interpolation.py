"""Diagnostic interpolation within native tuning knots, never extrapolation.

A dense table is an estimated model, not additional native measurements.
Independent holdouts and uncertainty validation remain required for release.
"""
from fractions import Fraction

KINDS=('linear_period','linear_frequency')


def build(points,kind='linear_period'):
    if kind not in KINDS or not points:raise ValueError('nonempty measured knots and explicit supported interpolation required')
    banks={}
    for (coarse,fine),frequency in points.items():
        if type(coarse) is not int or type(fine) is not int or not 0<=coarse<=47 or not 8<=fine<=247 or type(frequency) is not int or frequency<=0:
            raise ValueError('valid native codes and positive integer-millihertz knots required')
        banks.setdefault(coarse,{})[fine]=frequency
    table=dict(points);estimated=[]
    for coarse,knots in banks.items():
        ordered=sorted(knots)
        for lo,hi in zip(ordered,ordered[1:]):
            for code in range(lo+1,hi):
                x=Fraction(code-lo,hi-lo);a,b=knots[lo],knots[hi]
                value=1/((1-x)/a+x/b) if kind=='linear_period' else (1-x)*a+x*b
                frequency=round(value)
                if frequency<=0:raise ValueError('positive interpolated frequency required')
                table[coarse,code]=frequency
                estimated.append(dict(coarse=coarse,fine=code,frequency_millihertz=frequency,
                    lower_native_knot=lo,upper_native_knot=hi,origin='interpolated_estimate'))
    report=dict(kind=kind,native_knots=[dict(coarse=c,fine=f,frequency_millihertz=v,origin='native_measurement') for (c,f),v in sorted(points.items())],
        interpolated_points=estimated,extrapolation_allowed=False,independent_holdouts_complete=False,
        uniform_frequency_error_bound_qualified=False,physical_models_qualified=False,release_ready=False)
    return table,report
