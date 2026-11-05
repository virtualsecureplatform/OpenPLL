#!/usr/bin/env python3
"""Make a resistor-collapsed diode verification copy; preserve simulation RC."""
import argparse
import json
import math
import re
from pathlib import Path


def collapse(source,output):
    text=source.read_text();headers=re.findall(r'^\.subckt (\S+) (.+)$',text,re.M)
    assert len(headers)==1 and headers[0][0]=='sky130_fd_sc_hs__diode_2'
    ports=headers[0][1].split();assert set(ports)=={'DIODE','VGND','VNB','VPB','VPWR'}
    parent={};counts={'resistors':0,'capacitors':0,'diodes':0}
    def root(node):
        parent.setdefault(node,node)
        if parent[node]!=node:parent[node]=root(parent[node])
        return parent[node]
    for line in text.splitlines():
        fields=line.split()
        if not fields:continue
        kind=fields[0][0]
        if kind=='R':
            assert len(fields)==4
            value=float(fields[3]);assert math.isfinite(value) and value>0
            a,b=root(fields[1]),root(fields[2]);parent[a]=b;counts['resistors']+=1
        elif kind=='C':
            assert len(fields)==4
            m=re.fullmatch(r'([0-9.eE+-]+)([fp]?)',fields[3]);assert m
            value=float(m[1]);assert math.isfinite(value) and value>0
            counts['capacitors']+=1
        elif kind=='X':
            assert len(fields)==6 and fields[3]=='sky130_fd_pr__diode_pw2nd_05v5'
            assert {p.split('=')[0] for p in fields[4:]}=={'area','perim'}
            for field in fields[4:]:assert math.isfinite(float(field.split('=')[1])) and float(field.split('=')[1])>0
            root(fields[1]);root(fields[2]);counts['diodes']+=1
        else:assert kind in ('*','.')
    assert counts['diodes']==1 and counts['resistors']>0 and counts['capacitors']>0
    groups={}
    for node in parent:groups.setdefault(root(node),[]).append(node)
    aliases={}
    for nodes in groups.values():
        external=set(nodes)&set(ports);assert len(external)<=1
        preferred=next(iter(external)) if external else min(nodes,key=lambda n:(len(n),n))
        aliases.update({node:preferred for node in nodes})
    lines=[]
    for line in text.splitlines():
        fields=line.split()
        if fields and fields[0][0] in ('R','C'):continue
        if fields and fields[0][0]=='X':
            fields[1:3]=[aliases[node] for node in fields[1:3]];line=' '.join(fields)
        lines.append(line)
    assert not output.exists();output.write_text('\n'.join(lines)+'\n');return counts


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();print(json.dumps(collapse(args.source,args.output)))


if __name__=='__main__':main()
