"""Eliminate constant-voltage passive boundaries by exact affine nodal stamping.

For retained voltages, C(x,fixed) becomes C(x,0), while R(x,fixed) becomes
R(x,0) plus current Vfixed/R injected into x. Constant-only branches vanish.
Nonlinear cards and subcircuit definitions remain verbatim. This preserves
retained-node current equations, not fixed-source current or absolute charge.
"""
from collections import defaultdict
from fractions import Fraction
import math

from audit_hierarchical_capacitance import number
from audit_selected_dco_history_inputs import sources


def emit(value):
    converted=float(value)
    if not math.isfinite(converted) or (value and not converted):raise ValueError('coefficient outside finite floating-point range')
    text=format(converted,'.17g')
    parsed=number(text)
    if value and abs(parsed/value-1)>Fraction(1,10**15):raise ValueError('coefficient serialization exceeds 1e-15 relative error')
    return text


def fold(device_text,source_records,allow_signed_capacitors=False):
    fixed={'0':Fraction(0)}
    for node,(_,value) in source_records.items():
        try:fixed[node]=number(value)
        except ValueError:pass # Dynamic or unsupported expressions remain explicit.
    kept=[];passives=[];nonlinear=set();protected=set();depth=0;names=set();last_passive=False
    for line in device_text.splitlines(keepends=True):
        f=line.split()
        if not f or f[0].startswith('*'):kept.append(line);continue
        if f[0].startswith('+'):
            if last_passive and depth==0:raise ValueError('top-level passive continuation is unsupported')
            kept.append(line);continue
        kind=f[0].lower()
        if kind=='.subckt':depth+=1;kept.append(line);continue
        if kind=='.ends':
            depth-=1
            if depth<0:raise ValueError('unbalanced subcircuits')
            kept.append(line);continue
        if depth:kept.append(line);continue
        if kind=='.end':raise ValueError('include file cannot terminate parent deck')
        if f[0].startswith('.'):
            kept.append(line);last_passive=False;continue
        if f[0] in names:raise ValueError('duplicate top-level device name')
        names.add(f[0]);last_passive=f[0][0].upper()in ('R','C')
        if f[0][0].upper() in ('R','C'):
            if len(f)!=4:raise ValueError('constant unparameterized R/C required')
            value=number(f[3])
            if value<0 and (f[0][0].upper()=='R' or not allow_signed_capacitors):raise ValueError('nonnegative R and explicitly certified signed C required')
            passives.append((f,line,value))
            if f[0][0].upper()=='R' and value==0:protected.update(f[1:3])
        else:
            if f[0].startswith('Xflat'):
                stop=[i for i,t in enumerate(f)if t.startswith('__openpll_literal_leaf_')]
                if len(stop)!=1:raise ValueError('explicit literal primitive wrapper required')
                nonlinear.update(f[1:stop[0]])
            elif not f[0].startswith('.'):
                raise ValueError('unreviewed top-level active device')
            kept.append(line)
    if depth:raise ValueError('unbalanced subcircuits')
    prefix='__openpll_fixed_fold_'
    if any(prefix in name for name in names):raise ValueError('generated-name collision')
    caps=defaultdict(Fraction);conductance=defaultdict(Fraction);injection=defaultdict(Fraction)
    old_counts=defaultdict(int);removed_constant_branches=0
    for f,line,value in passives:
        kind=f[0][0].upper();a,b=f[1:3];af,bf=a in fixed,b in fixed
        old_counts[kind]+=1
        if kind=='R' and value==0:kept.append(line);continue
        if a==b or (af and bf):removed_constant_branches+=1;continue
        if kind=='C':
            if value==0:continue
            pair=(b,'0')if af else (a,'0')if bf else tuple(sorted((a,b)))
            caps[pair]+=value
        elif af or bf:
            node=b if af else a;voltage=fixed[a]if af else fixed[b]
            conductance[node]+=1/value;injection[node]+=voltage/value
        else:kept.append(line)
    generated=[]
    for i,((a,b),value)in enumerate(sorted(caps.items())):
        generated.append(f'C{prefix}{i} {a} {b} {emit(value)}\n')
    for i,node in enumerate(sorted(conductance)):
        generated.append(f'R{prefix}{i} {node} 0 {emit(1/conductance[node])}\n')
        if injection[node]:generated.append(f'I{prefix}{i} 0 {node} {emit(injection[node])}\n')
    removed=set(fixed)-nonlinear-protected-{'0'}
    source_text=''.join(f'{name} {node} 0 {value}\n'for node,(name,value)in source_records.items()if node not in removed)
    report=dict(original_top_level_passive_counts=dict(old_counts),generated_capacitors=len(caps),
        generated_bias_conductances=len(conductance),generated_current_injections=sum(bool(v)for v in injection.values()),
        removed_constant_voltage_sources=len(removed),removed_constant_or_self_branches=removed_constant_branches,
        retained_nonlinear_terminals=len(nonlinear),nonlinear_cards_and_subcircuits_unchanged=True,
        coefficient_relative_serialization_bound=1e-15,retained_node_equations_exact_before_serialization=True,
        fixed_source_currents_and_absolute_capacitor_charge_preserved=False,
        signed_capacitor_input_allowed=allow_signed_capacitors,passive_coefficients_nonnegative=all(v>=0 for v in caps.values()),native_response_equivalence_qualified=False,release_ready=False)
    return ''.join(kept)+''.join(generated),source_text,report
