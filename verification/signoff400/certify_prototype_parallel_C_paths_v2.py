"""Exact parallel-path energy witnesses with bounded dyadic capacity sums.

Per-path rational inequalities remain exact. Only downward dyadic enclosures
are summed, avoiding unbounded coprime denominators on dense Kron meshes.
Failure summaries are approximate diagnostics, never passing witnesses.
"""
from collections import defaultdict
from fractions import Fraction as F
import heapq
import math


def lower(value):
    value=F(value)
    if value<=0:return F()
    approximate=float(value)
    if not math.isfinite(approximate):raise ValueError('capacity outside supported numeric range')
    while F.from_float(approximate)>value:approximate=math.nextafter(approximate,0.)
    return F.from_float(approximate)


def summary(value):
    value=F(value)
    try:approx=float(value)
    except OverflowError:approx=None
    return dict(approximate_F=approx,numerator_bits=value.numerator.bit_length(),denominator_bits=value.denominator.bit_length(),exact_value_claimed=False)


def certificate(pairs,bits=40):
    if not 16<=bits<=52:raise ValueError('bounded dyadic allocation precision required')
    pairs={tuple(k):F(v) for k,v in pairs.items()}
    if any(len(k)!=2 or tuple(sorted(k))!=k for k in pairs):raise ValueError('canonical two-node capacitor pairs required')
    graph=defaultdict(dict);positive={};negative=[]
    for (a,b),value in pairs.items():
        if a==b:continue
        edge=(a,b)
        if value>0:positive[edge]=value;graph[a][b]=edge;graph[b][a]=edge
        elif value<0:negative.append((a,b,-value))
    def shortest(a,b,remaining):
        dist={a:F()};prev={};queue=[(F(),a)]
        while queue:
            d,n=heapq.heappop(queue)
            if dist[n]!=d:continue
            if n==b:break
            for other,e in graph[n].items():
                r=remaining.get(e,F(1))
                if r<=0:continue
                nd=d+1/(positive[e]*r)
                if other not in dist or nd<dist[other]:dist[other]=nd;prev[other]=(n,e);heapq.heappush(queue,(nd,other))
        if b not in dist:return []
        path=[];n=b
        while n!=a:n,e=prev[n];path.append(e)
        return path[::-1]
    def paths(a,b,remaining):
        result=[[graph[a][n],graph[n][b]] for n in sorted(graph[a].keys()&graph[b].keys())
                if remaining.get(graph[a][n],F(1))>0 and remaining.get(graph[n][b],F(1))>0]
        if not result:
            path=shortest(a,b,remaining)
            if path:result=[path]
        return result
    def capacity(path,remaining):return 1/sum((1/(positive[e]*remaining.get(e,F(1))) for e in path),F())
    hardness={}
    for a,b,c in negative:
        available=sum((lower(capacity(p,{})) for p in paths(a,b,{})),F())
        hardness[a,b]=c/available if available else F(10**100)
    orders=[sorted(negative,key=lambda r:(-hardness[r[0],r[1]],r[0],r[1])),sorted(negative),sorted(negative,reverse=True)]
    attempts=[];grid=1<<bits
    for order in orders:
        remaining={};witnesses=[];failed=None
        for a,b,magnitude in order:
            ps=paths(a,b,remaining)
            total=sum((lower(capacity(p,remaining)) for p in ps),F())
            if total<magnitude:
                failed=dict(negative_pair=[a,b],required=summary(magnitude),available_path_capacity_lower=summary(total));break
            ratio=magnitude/total;allocations=[]
            for path in ps:
                items=[]
                for edge in path:
                    residual=remaining.get(edge,F(1));scaled=ratio*residual*grid
                    ticks=(scaled.numerator+scaled.denominator-1)//scaled.denominator
                    alpha=min(residual,F(ticks+1,grid))
                    if not 0<alpha<=residual:raise ValueError('capacity allocation overflow')
                    items.append(dict(pair=list(edge),fraction=str(alpha)))
                cap=1/sum((1/(positive[tuple(item['pair'])]*F(item['fraction'])) for item in items),F())
                allocations.append(dict(edges=items,covered_negative_C_lower_F=str(lower(cap))))
            covered=sum((F(p['covered_negative_C_lower_F']) for p in allocations),F())
            if covered<magnitude:
                failed=dict(negative_pair=[a,b],reason='dyadic coverage enclosure insufficient',required=summary(magnitude),covered_lower=summary(covered));break
            for path in allocations:
                for item in path['edges']:
                    edge=tuple(item['pair']);remaining[edge]=remaining.get(edge,F(1))-F(item['fraction'])
                    if remaining[edge]<0:raise ValueError('positive edge overallocated')
            witnesses.append(dict(negative_pair=[a,b],magnitude_F=str(magnitude),paths=allocations))
        attempts.append(dict(covered_pairs=len(witnesses),failure=failed))
        if failed is None:
            return dict(passivity_certified=True,method=__doc__,dyadic_bits=bits,negative_pairs=len(negative),positive_pairs=len(positive),attempts=attempts,witnesses=witnesses,
                        maximum_positive_edge_allocation=str(max((1-r for r in remaining.values()),default=F())),strict_positive_definiteness_claimed=False)
    return dict(passivity_certified=False,inconclusive=True,method=__doc__,negative_pairs=len(negative),attempts=attempts)


def replay(pairs,proof):
    pairs={tuple(k):F(v) for k,v in pairs.items()}
    if not proof.get('passivity_certified'):raise ValueError('passing certificate required')
    needed={p:-c for p,c in pairs.items() if c<0 and p[0]!=p[1]};seen=set();loads=defaultdict(F)
    for witness in proof['witnesses']:
        pair=tuple(witness['negative_pair']);a,b=pair
        if pair not in needed or pair in seen or F(witness['magnitude_F'])!=needed[pair]:raise ValueError('negative-pair coverage mismatch')
        seen.add(pair);covered=F()
        for path in witness['paths']:
            node=a;resistance=F();used=set()
            for item in path['edges']:
                edge=tuple(item['pair']);alpha=F(item['fraction'])
                if edge in used or node not in edge or pairs[edge]<=0 or not 0<alpha<=1:raise ValueError('invalid positive path allocation')
                used.add(edge);node=edge[1] if node==edge[0] else edge[0];resistance+=1/(pairs[edge]*alpha);loads[edge]+=alpha
            enclosure=F(path['covered_negative_C_lower_F'])
            if node!=b or resistance<=0 or enclosure<0 or enclosure>1/resistance:raise ValueError('invalid rational path-capacity enclosure')
            covered+=enclosure
        if covered<needed[pair]:raise ValueError('negative pair undercovered')
    if seen!=set(needed) or any(v>1 for v in loads.values()):raise ValueError('incomplete or overallocated witness')
    return dict(all_negative_pairs_covered=True,all_positive_edge_allocations_within_capacity=True,maximum_positive_edge_allocation=str(max(loads.values(),default=F())))
