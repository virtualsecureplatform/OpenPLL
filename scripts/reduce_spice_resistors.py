#!/usr/bin/env python3
"""Exact star-mesh elimination of resistor-only internal nodes in flat RCX.

Keeps all non-resistor statements byte-for-byte. No capacitances are discarded.
Only positive, constant, unmodelled resistors at a common temperature qualify.
External ports and every node mentioned by any other device remain protected.
"""
import argparse
from collections import deque
import hashlib
import json
import math
import re
from pathlib import Path


def reduce_network(text, max_degree=8):
    if not 1 <= max_degree <= 8:
        raise ValueError('max_degree must be 1..8')
    # Renaming/removing a resistor would invalidate branch-current references.
    active = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('*'))
    if re.search(r'\bi\s*\(\s*r', active, re.IGNORECASE) or re.search(r'^\s*[fh]\S*\s', active, re.IGNORECASE | re.MULTILINE):
        raise ValueError('branch-current references are not supported')
    lines=text.splitlines(keepends=True)
    if sum(line.lower().startswith('.subckt ') for line in lines)!=1:
        raise ValueError('requires one flat extracted subcircuit')
    graph={};protected={'0'};keep=[];count=0;names=set()
    def edge(a,b,g):
        if a==b:return
        value=graph.setdefault(a,{}).get(b,0)+g
        if not math.isfinite(value) or value <= 0:
            raise ValueError('conductance overflow or underflow')
        graph[a][b]=value;graph.setdefault(b,{})[a]=value
    for line in lines:
        tokens=line.split()
        if tokens and not tokens[0].startswith('*') and tokens[0][0].lower()=='r':
            if len(tokens)!=4:
                raise ValueError('modelled/parameterized resistors are not supported')
            value=float(tokens[3])
            if not math.isfinite(value) or value<=0:raise ValueError('invalid resistance')
            name=tokens[0].lower()
            if name in names:raise ValueError('duplicate resistor name')
            names.add(name)
            edge(tokens[1].lower(),tokens[2].lower(),1/value);count+=1
        else:
            keep.append(line)
            if tokens and not tokens[0].startswith('*'):
                protected.update(token.lower() for token in tokens)
    original_nodes=len(graph)
    queue=deque(n for n in graph if n not in protected and len(graph[n])<=max_degree)
    eliminated=0
    while queue:
        node=queue.popleft()
        if node not in graph or node in protected or len(graph[node])>max_degree:continue
        neighbors=list(graph[node].items());total=sum(g for _,g in neighbors)
        for i,(a,ga) in enumerate(neighbors):
            for b,gb in neighbors[i+1:]:edge(a,b,ga*(gb/total))
        for other,_ in neighbors:
            del graph[other][node]
            if other not in protected and len(graph[other])<=max_degree:queue.append(other)
        del graph[node];eliminated+=1
    resistors=[]
    for a in sorted(graph):
        for b,g in sorted(graph[a].items()):
            if a<b:resistors.append(f'RRED{len(resistors)} {a} {b} {1/g:.17g}\n')
    insertion=next((i for i,line in enumerate(keep) if line.lower().startswith('.ends')),None)
    if insertion is None:raise ValueError('missing subcircuit end')
    keep[insertion:insertion]=resistors
    return ''.join(keep),dict(original_resistors=count,reduced_resistors=len(resistors),
                             original_resistor_nodes=original_nodes,eliminated_nodes=eliminated,
                             max_degree=max_degree,approximation='none; constant-resistor Schur complement')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--max-degree',type=int,choices=range(1,9),default=8)
    a=p.parse_args()
    if a.source.resolve()==a.output.resolve():p.error('source and output must differ')
    source=a.source.read_text();result,stats=reduce_network(source,a.max_degree)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(result)
    stats.update(source=str(a.source.resolve()),source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                 output_sha256=hashlib.sha256(result.encode()).hexdigest())
    a.output.with_suffix(a.output.suffix+'.json').write_text(json.dumps(stats,indent=2))
    print(json.dumps(stats,indent=2))


if __name__=='__main__':main()
