"""Bounded exact sparse congruence test of the fixed-rail capacitance operator."""
import argparse,json,time,heapq,os
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from project_prototype_fixed_rail_C_v2 import project,RAILS,FIXED
from audit_hierarchical_capacitance import number
from resources import lease


def eliminate(pairs,deadline,max_fill=300000):
    diag=defaultdict(F);adj=defaultdict(dict)
    for (a,b),c in pairs.items():
        if a!=FIXED:diag[a]+=c
        if b!=FIXED:diag[b]+=c
        if FIXED not in (a,b):adj[a][b]=-c;adj[b][a]=-c
    for n in diag:adj[n]
    history=[];queue=[(len(adj[n]),n)for n in diag];heapq.heapify(queue);vector=None
    while diag:
        if time.monotonic()>deadline:return dict(conclusive=False,reason='exact elimination time bound',eliminated=len(history),remaining=len(diag)),history
        if sum(map(len,adj.values()))>max_fill:return dict(conclusive=False,reason='exact fill bound',eliminated=len(history),remaining=len(diag)),history
        while queue:
            degree,n=heapq.heappop(queue)
            if n in diag and degree==len(adj[n]):break
        else:raise ValueError('elimination queue lost nodes')
        d=diag[n];row=dict(adj[n])
        if d<0:vector={n:F(1)};break
        if d==0 and row:
            j,c=next(iter(row.items()));vector={n:F(1),j:-c/(abs(diag[j])+1)};break
        history.append((n,d,row))
        if d:
            for a,c in row.items():
                diag[a]-=c*c/d
            neighbors=list(row)
            for i,a in enumerate(neighbors):
                for b in neighbors[i+1:]:
                    value=adj[a].get(b,F())-row[a]*row[b]/d
                    if value:adj[a][b]=value;adj[b][a]=value
                    else:adj[a].pop(b,None);adj[b].pop(a,None)
        for a in row:adj[a].pop(n);heapq.heappush(queue,(len(adj[a]),a))
        del adj[n];del diag[n]
    if vector is not None:
        for n,d,row in reversed(history):vector[n]=-sum((c*vector.get(a,F())for a,c in row.items()),F())/d if d else F()
        energy=sum((c*(vector.get(a,F())-vector.get(b,F()))**2 for (a,b),c in pairs.items()),F())
        if energy>=0:raise ValueError('negative pivot did not verify against original operator')
        return dict(conclusive=True,passivity_certified=False,indefiniteness_proved=True,exact_twice_energy_J=str(energy),voltage_vector={n:str(v)for n,v in vector.items()if v}),history
    return dict(conclusive=True,passivity_certified=True,indefiniteness_proved=False,method='exact rational sparse LDL congruence; nonnegative pivots and zero residual rows'),history


def run(source,corner,attachment,output,seconds):
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    model=source/(corner+'_'+attachment+'.spice')
    if r['artifacts'].get(str(model))!=sha(model):raise ValueError('source model differs')
    output.mkdir(parents=True,exist_ok=False);pins={str(p):sha(p)for p in [receipt,model,Path(__file__).resolve()]};pairs=defaultdict(F)
    for line in model.read_text().splitlines():
        f=line.split()
        if f and f[0].startswith('Cflat'):pairs[tuple(sorted(f[1:3]))]+=number(f[3])
    pairs=project(pairs,set(RAILS));os.sched_setaffinity(0,{24});start=time.monotonic()
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+seconds+60):result,history=eliminate(pairs,start+seconds)
    proof=output/'elimination.json';save(proof,[dict(node=n,pivot=str(d),row={a:str(c)for a,c in row.items()})for n,d,row in history]);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(proof):sha(proof)},corner=corner,attachment=attachment,result=result,elapsed_s=time.monotonic()-start,models_modified=False,native_simulation_allowed=False,physical_RC_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--corner',default='nom');p.add_argument('--attachment',default='driver');p.add_argument('--seconds',type=int,default=600);a=p.parse_args();run(a.source.resolve(),a.corner,a.attachment,a.output.resolve(),a.seconds)
