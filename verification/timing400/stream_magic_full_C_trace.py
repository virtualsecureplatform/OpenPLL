#!/usr/bin/env python3
"""Bounded-memory two-pass reader for private full-geometry contribution traces.

Retain all raw support records in the native file. Aggregate only matrices,
node IDs and counters, checking every support box. No spatial qualification is
inferred from successful numerical accounting.
"""
from collections import Counter,defaultdict
from decimal import Decimal
import shlex
from check_magic_cap_clip_windows import GROUND


def reconstruct_stream(path):
    mapping={};begins=ends=0
    with path.open() as stream:
        for line in stream:
            if line.startswith('OPENPLL_BEGIN '):
                f=shlex.split(line);assert len(f)==3 and f[-1]=='full_geometry';begins+=1
            elif line.startswith('OPENPLL_ID '):
                f=shlex.split(line);assert len(f)==4 and f[1] not in mapping and f[3] in ['0','1']
                mapping[f[1]]=GROUND if f[3]=='1' else f[2]
            elif line.strip()=='OPENPLL_END':ends+=1
            else:assert line.startswith(('OPENPLL_G ','OPENPLL_P ')),line[:200]
    assert begins==ends==1 and list(mapping.values()).count(GROUND)==1
    totals=defaultdict(Decimal);absolute=defaultdict(Decimal);counts=Counter();keys={}
    total=negative=unlocated=self_branches=0;largest=None;largest_value=Decimal(0)
    scale=Decimal('.001')
    def boxes(tokens):
        assert len(tokens)%4==0
        for i in range(0,len(tokens),4):
            l,b,r,t=map(int,tokens[i:i+4]);assert l<=r and b<=t
    with path.open() as stream:
        for line in stream:
            if line.startswith('OPENPLL_G '):
                f=line.split();assert len(f) in [5,9]
                a,b=f[1],None;value=Decimal(f[2])*scale;reason=f[3]
                if f[4]=='box':assert len(f)==9;boxes(f[5:])
                else:assert len(f)==5 and f[4]=='unlocated' and reason=='output_zero_clamp';unlocated+=1
            elif line.startswith('OPENPLL_P '):
                f=line.split();assert len(f)==14 and f[5]=='boxes';boxes(f[6:])
                a,b=f[1:3];value=Decimal(f[3])*scale;reason=f[4]
            else:continue
            assert value.is_finite() and value!=0 and a in mapping and (b is None or b in mapping)
            total+=1;counts[reason]+=1
            if value<0:negative+=1
            ptrs=(a,b)
            if ptrs not in keys:keys[ptrs]=tuple(sorted([mapping[a],GROUND if b is None else mapping[b]]))
            k=keys[ptrs]
            if k[0]==k[1]:self_branches+=1;continue
            totals[k]+=value;absolute[k]+=abs(value)
            if abs(value)>largest_value:largest=(k,value);largest_value=abs(value)
    assert totals and largest
    return dict(totals),dict(absolute),total,dict(counts),mapping,dict(
        signed_negative_events=negative,unlocated_output_clamp_events=unlocated,
        zero_energy_self_branch_events=self_branches,largest_nonself_event_nodes=list(largest[0]),
        largest_nonself_event_delta_ff=str(largest[1]))
