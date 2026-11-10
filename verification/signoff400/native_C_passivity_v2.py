"""Exact support-path certificate for a signed linear capacitance Laplacian.

For a negative edge -w and a positive path P between its endpoints,
w*(duv)^2 <= w*sum(1/Ce)*sum(Ce*de^2).  If the sum of these path
loads is <=1, the whole signed energy is nonnegative.  Reciprocal and
load bounds are rounded upward to dyadic rationals, never toward zero.
No resistor contraction or alteration of capacitor cards is performed.
"""
from collections import defaultdict
import heapq
from fractions import Fraction as F

def assess_caps(caps):
    pairs=defaultdict(F)
    for a,b,v in caps:
        if a!=b:pairs[tuple(sorted((a,b)))]+=v
    negative=[(a,b,-v) for (a,b),v in pairs.items() if v<0]
    positive=[(a,b,v) for (a,b),v in pairs.items() if v>0]
    if not negative:return dict(linear_C_PSD_certified=True,positive_pairs=len(positive),negative_pairs=0,negative_path_load_upper_exact='0',method='nonnegative branch energy',capacitors_modified=False,positive_R_contracted=False)
    graph=defaultdict(list)
    for a,b,v in positive:graph[a].append((b,v));graph[b].append((a,v))
    for a,b,v in negative:graph[a];graph[b]
    parent={};depth={};component={};inverse={};serial=0;den=2**64
    for start in sorted(graph,key=lambda n:-len(graph[n])):
        if start in parent:continue
        serial+=1;distance={start:0};pending=[(0,start,None,0)]
        while pending:
            cost,a,prior,edge_inverse=heapq.heappop(pending)
            if a in parent:continue
            parent[a]=prior;depth[a]=0 if prior is None else depth[prior]+1
            component[a]=serial-1
            if prior is not None:inverse[a]=edge_inverse
            for b,c in graph[a]:
                if b in parent:continue
                resistance=(den*c.denominator+c.numerator-1)//c.numerator
                candidate=cost+resistance
                if candidate<distance.get(b,candidate+1):
                    distance[b]=candidate;heapq.heappush(pending,(candidate,b,a,resistance))
    load_units=0;disconnected=[];examples=[]
    for a,b,w in negative:
        if component[a]!=component[b]:
            disconnected.append(dict(nodes=[a,b],negative_C_F_exact=str(-w)));continue
        x,y=a,b;path_units=0;edges=0
        while x!=y:
            if depth[x]>=depth[y]:path_units+=inverse[x];x=parent[x]
            else:path_units+=inverse[y];y=parent[y]
            edges+=1
        # 2^120 * w * (path_units / 2^64), rounded upward exactly.
        product=w*path_units;units=(product.numerator*2**56+product.denominator-1)//product.denominator
        load_units+=units
        if len(examples)<8:examples.append(dict(nodes=[a,b],positive_path_edges=edges,load_upper_exact=str(F(units,2**120))))
    return dict(linear_C_PSD_certified=not disconnected and load_units<=2**120,positive_pairs=len(positive),negative_pairs=len(negative),positive_components=serial,negative_edges_without_positive_path=disconnected,negative_path_load_upper_exact=str(F(load_units,2**120)),method='positive resistance-shortest spanning-forest support paths; weighted Cauchy inequality; upward dyadic bounds',examples=examples,capacitors_modified=False,positive_R_contracted=False)
