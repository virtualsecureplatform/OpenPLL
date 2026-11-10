"""Conservation against a finite float64 operation bound, without an absolute floor."""
from collections import defaultdict
from fractions import Fraction as F
from audit_keeper_native_R_contraction import parse,compare
from compare_native_R_with_aliases import compare_with_aliases

def assess(reference,candidate):
    base=parse(reference);rc=parse(candidate)
    metrics=compare_with_aliases(reference,candidate) if base['resistors'] else compare(reference,candidate)
    aliases={}
    def root(table,n):
        table.setdefault(n,n)
        while table[n]!=n:table[n]=table[table[n]];n=table[n]
        return n
    for a,b,v in base['resistors']:
        if v:raise ValueError('only ideal reference aliases supported')
        aliases[root(aliases,a)]=root(aliases,b)
    canon=lambda n:root(aliases,n)
    parent={}
    for a,b,v in rc['resistors']:
        if v<0:raise ValueError('negative native resistance')
        parent[root(parent,canon(a))]=root(parent,canon(b))
    known={canon(n) for _,nodes,_ in base['devices'] for n in nodes}|{canon(n) for n in base['ports']}|{canon(n) for a,b,_ in base['caps'] for n in [a,b]}
    groups=defaultdict(set)
    for n in known:groups[root(parent,n)].add(n)
    collisions=[sorted(v) for v in groups.values() if len(v)>1]
    def original(n):
        n=canon(n);g=groups.get(root(parent,n))
        return min(g) if g else n
    values=[];absolute=[];counts=[]
    for data,convert in [(base,canon),(rc,original)]:
        totals=defaultdict(F);sizes=defaultdict(int);magnitudes=defaultdict(F)
        for a,b,v in data['caps']:
            a,b=convert(a),convert(b)
            if a==b:continue
            key=tuple(sorted([a,b]));totals[key]+=v;magnitudes[key]+=abs(v);sizes[key]+=1
        values.append(totals);absolute.append(magnitudes);counts.append(sizes)
    failures=[];differences=[];eps=F(1,2**52)
    # 32 operations per participating printed card exceeds the flat import,
    # allocation, residual sum, unit conversions and serialization operations.
    for k in sorted(values[0].keys()|values[1].keys()):
        old,new=values[0][k],values[1][k];error=abs(new-old)
        n=32*(counts[0][k]+counts[1][k]+4);neps=n*eps
        if neps>=F(1,100):raise ValueError('roundoff operation bound too large')
        bound=neps/(1-neps)*(absolute[0][k]+absolute[1][k])
        if error:
            row=dict(nodes=list(k),reference_F_exact=str(old),candidate_F_exact=str(new),absolute_error_F_exact=str(error),float64_bound_F_exact=str(bound),within_bound=error<=bound)
            differences.append(row)
            if error>bound:failures.append(row)
    return dict(primitive_models_and_parameters_match=metrics['primitive_multisets_match'],formal_ports_match=metrics['ordered_formal_ports_match'],unintended_component_shorts=collisions,positive_wire_R_cards=metrics['positive_wire_R_cards'],exact_cap_contraction=not differences,float64_C_conservation=not failures,absolute_error_floor_used=False,roundoff_model='gamma_n, eps=2^-52, n=32*(participating cards+4)',C_difference_pairs=len(differences),C_failure_pairs=len(failures),differences=differences,failures=failures,negative_reference_C_cards=sum(v<0 for a,b,v in base['caps']),negative_candidate_C_cards=sum(v<0 for a,b,v in rc['caps']),native_devices_and_C_conserved=metrics['primitive_multisets_match'] and metrics['ordered_formal_ports_match'] and not collisions and not failures)
