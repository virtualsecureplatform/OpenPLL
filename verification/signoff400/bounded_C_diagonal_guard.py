"""Exact export checks for a symmetric row-error diagonal passivity guard.

If A is PSD, E is symmetric and sum_j |E_ij| <= r_i, then
A+E+diag(d) is PSD for d_i >= r_i. The final row error is <= r_i+d_i.
"""
from fractions import Fraction as F
import math


def coefficient(row_error_fF):
    bound=F(row_error_fF)/10**15
    if bound<0:raise ValueError('nonnegative row error required')
    if not bound:return '0',F()
    value=float(bound)
    if not math.isfinite(value):raise ValueError('finite guard coefficient required')
    while True:
        text=format(value,'.17e');actual=F(text)
        if actual>=bound:return text,actual
        value=math.nextafter(value,math.inf)


def review(row_errors_fF,scales_lower_fF,guards_F,fixed,budget):
    final={}
    for node,error in row_errors_fF.items():
        error=F(error);scale=F(scales_lower_fF[node])
        if error<0 or scale<=0:raise ValueError('valid row error and reference scale required')
        guard=F(guards_F.get(node,0))
        if node not in fixed and guard*10**15<error:raise ValueError('guard does not dominate symmetric row error')
        if guard<0:raise ValueError('negative numerical guard')
        if node not in fixed:
            final[node]=(error+guard*10**15)/scale
            if final[node]>F(budget):raise ValueError('combined approximation and guard exceed error budget')
    if set(guards_F)-set(row_errors_fF):raise ValueError('guard outside the bounded subspace')
    return dict(symmetric_row_error_domination_verified=True,maximum_normalized_final_row_error=str(max(final.values(),default=F())),
                final_error_budget=str(F(budget)),strict_positive_definiteness_claimed=False)
