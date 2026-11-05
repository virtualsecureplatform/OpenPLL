"""Exact passive-C certificate using residual-capacity parallel positive paths.

Each path allocates a dyadic fraction of its positive edges. Its series
capacitance bounds that share of a negative pair. Parallel shares cover the
negative magnitude; total allocation on every positive edge is at most one.
Failure is inconclusive unless a separate negative-energy witness exists.
"""
from collections import defaultdict
from fractions import Fraction as F
import heapq


def certificate(pairs,bits=40):
    if not 16<=bits<=52:raise ValueError('bounded dyadic allocation precision required')
    pairs={tuple(k):F(v) for k,v in pairs.items()}
    if any(tuple(sorted(k))!=k or len(k)!=2 for k in pairs):raise ValueError('canonical two-node capacitor pairs required')
    graph=defaultdict(dict);positive={};negative=[]
    for (a,b),value in pairs.items():
        if a==b:continue
        key=tuple(sorted((a,b)))
        if value>0:positive[key]=value;graph[a][b]=key;graph[b][a]=key
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
        return list(reversed(path))
    def paths(a,b,remaining):
        common=sorted(graph[a].keys()&graph[b].keys())
        result=[[graph[a][m],graph[m][b]] for m in common
                if remaining.get(graph[a][m],F(1))>0 and remaining.get(graph[m][b],F(1))>0]
        if not result:
            p=shortest(a,b,remaining)
            if p:result=[p]
        return result
    def capacity(path,remaining):return 1/sum((1/(positive[e]*remaining.get(e,F(1))) for e in path),F())
    hardness={}
    for a,b,c in negative:
        ps=paths(a,b,{})
        available=sum((capacity(p,{}) for p in ps),F())
        hardness[a,b]=c/available if available else F(10**100)
    orders=[sorted(negative,key=lambda r:(-hardness[r[0],r[1]],r[0],r[1])),sorted(negative),sorted(negative,reverse=True)]
    attempts=[];grid=1<<bits
    for order in orders:
        remaining={};witnesses=[];failed=None
        for a,b,magnitude in order:
            ps=paths(a,b,remaining)
            total=sum((capacity(p,remaining) for p in ps),F())
            if total<magnitude:
                failed=dict(negative_pair=[a,b],required_F=str(magnitude),available_selected_path_C_F=str(total));break
            ratio=magnitude/total;allocations=[]
            for path in ps:
                items=[]
                for edge in path:
                    residual=remaining.get(edge,F(1));exact=ratio*residual
                    scaled=exact*grid;dyadic=F((scaled.numerator+scaled.denominator-1)//scaled.denominator,grid)
                    if not 0<dyadic<=residual:raise ValueError('dyadic capacity allocation overflow')
                    items.append(dict(pair=list(edge),fraction=str(dyadic)))
                available=1/sum((1/(positive[tuple(i['pair'])]*F(i['fraction'])) for i in items),F())
                allocations.append(dict(edges=items,covered_negative_C_F=str(available)))
            if sum((F(p['covered_negative_C_F']) for p in allocations),F())<magnitude:raise ValueError('negative compensation undercovered')
            for path in allocations:
                for item in path['edges']:
                    edge=tuple(item['pair']);remaining[edge]=remaining.get(edge,F(1))-F(item['fraction'])
                    if remaining[edge]<0:raise ValueError('positive edge overallocated')
            witnesses.append(dict(negative_pair=[a,b],magnitude_F=str(magnitude),paths=allocations))
        attempts.append(dict(covered_pairs=len(witnesses),failure=failed))
        if failed is None:
            return dict(passivity_certified=True,method=__doc__,dyadic_bits=bits,negative_pairs=len(negative),
                positive_pairs=len(positive),attempts=attempts,witnesses=witnesses,
                maximum_positive_edge_allocation=str(max((1-r for r in remaining.values()),default=F())),
                strict_positive_definiteness_claimed=False)
    return dict(passivity_certified=False,inconclusive=True,method=__doc__,negative_pairs=len(negative),attempts=attempts)


def replay(pairs,proof):
    pairs={tuple(k):F(v) for k,v in pairs.items()}
    if any(tuple(sorted(k))!=k or len(k)!=2 for k in pairs):raise ValueError('canonical two-node capacitor pairs required')
    if not proof.get('passivity_certified'):raise ValueError('passing certificate required for witness replay')
    needed={p:-c for p,c in pairs.items() if c<0 and p[0]!=p[1]};seen=set();loads=defaultdict(F)
    for w in proof['witnesses']:
        pair=tuple(w['negative_pair']);a,b=pair
        if pair not in needed or pair in seen or F(w['magnitude_F'])!=needed[pair]:raise ValueError('negative-pair coverage mismatch')
        seen.add(pair);covered=F()
        for path in w['paths']:
            node=a;resistance=F();used=set()
            for item in path['edges']:
                edge=tuple(item['pair']);alpha=F(item['fraction'])
                if edge in used or node not in edge or pairs[edge]<=0 or not 0<alpha<=1:raise ValueError('invalid positive capacity path')
                used.add(edge);node=edge[1] if node==edge[0] else edge[0]
                resistance+=1/(pairs[edge]*alpha);loads[edge]+=alpha
            if node!=b or resistance<=0:raise ValueError('incorrect path endpoint')
            capacity=1/resistance
            if capacity!=F(path['covered_negative_C_F']):raise ValueError('path capacity mismatch')
            covered+=capacity
        if covered<needed[pair]:raise ValueError('negative pair undercovered')
    if seen!=set(needed) or any(v>1 for v in loads.values()):raise ValueError('incomplete or overallocated certificate')
    return dict(all_negative_pairs_covered=True,all_positive_edge_allocations_within_capacity=True,
                maximum_positive_edge_allocation=str(max(loads.values(),default=F())))
