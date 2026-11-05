"""Exact weighted-Cauchy certificate with local positive paths before Dijkstra.

A shortest path is not required by the energy inequality. Two-edge paths avoid
repeatedly exploring a large shared supply neighborhood. Longer paths retain
the original exact rational shortest-path fallback.
"""
from collections import defaultdict
from fractions import Fraction as F
import heapq


def certify(pairs):
    diagonal=defaultdict(F)
    for (a,b),value in pairs.items():
        if a!=b:diagonal[a]+=value;diagonal[b]+=value
    bad=[(n,v) for n,v in diagonal.items() if v<0]
    if bad:
        return dict(passivity_certified=False,reason='exact negative diagonal energy witness',
            negative_diagonal_witnesses=[dict(node=n,energy_F=str(v),unit_coordinate_voltage=True) for n,v in sorted(bad)],
            strict_positive_definiteness_claimed=False)
    graph=defaultdict(dict);positive={};negative=[]
    for (a,b),value in pairs.items():
        if a==b:continue
        edge=tuple(sorted((a,b)))
        if value>0:
            positive[edge]=value
            graph[a][b]=(1/value,edge);graph[b][a]=(1/value,edge)
        elif value<0:negative.append((a,b,-value))
    loads=defaultdict(F);witnesses=[];local=0;fallback=0
    for a,b,magnitude in sorted(negative):
        common=graph[a].keys()&graph[b].keys()
        best=None
        for mid in common:
            ra,ea=graph[a][mid];rb,eb=graph[b][mid]
            ratio=magnitude*(ra+rb)
            score=(max(loads[ea]+ratio,loads[eb]+ratio),ratio,mid)
            if best is None or score<best[0]:best=(score,[ea,eb],ratio)
        if best is not None:
            _,path,ratio=best;local+=1
        else:
            fallback+=1;distance={a:F()};previous={};queue=[(F(),a)]
            while queue:
                d,node=heapq.heappop(queue)
                if distance[node]!=d:continue
                if node==b:break
                for other,(r,edge) in graph[node].items():
                    nd=d+r
                    if other not in distance or nd<distance[other]:
                        distance[other]=nd;previous[other]=(node,edge);heapq.heappush(queue,(nd,other))
            if b not in distance:return dict(passivity_certified=False,reason='negative edge has no positive path',failed_pair=[a,b])
            path=[];node=b
            while node!=a:
                node,edge=previous[node];path.append(edge)
            path.reverse();ratio=magnitude*distance[b]
        for edge in path:loads[edge]+=ratio
        witnesses.append(dict(negative_pair=[a,b],negative_magnitude_F=str(magnitude),
            positive_path=[list(e) for e in path],allocated_fraction=str(ratio)))
    over=[dict(pair=list(e),allocated_fraction=str(v)) for e,v in loads.items() if v>1]
    return dict(passivity_certified=not over,
        method='exact weighted Cauchy inequality; local two-edge paths then rational Dijkstra; summed allocations <= 1',
        maximum_positive_edge_allocation=str(max(loads.values(),default=F())),
        overallocated_edges=over,witnesses=witnesses,negative_pairs=len(negative),positive_pairs=len(positive),
        local_two_edge_paths=local,longer_path_searches=fallback,strict_positive_definiteness_claimed=False)
