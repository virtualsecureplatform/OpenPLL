"""Alias-aware exact hierarchical capacitance aggregation; retains canonical node resolver."""
import argparse,json,re
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path
from common import save,sha,verify
from prepare_prototype_analog_reference import subcircuits


def number(text):
 m=re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([munpfa]?)',text)
 if not m:raise ValueError('unsupported numeric capacitor/resistor: '+text)
 return F(m[1])*{'':F(1),'m':F(1,10**3),'u':F(1,10**6),'n':F(1,10**9),'p':F(1,10**12),'f':F(1,10**15),'a':F(1,10**18)}[m[2]]


def flatten(blocks,top):
 parsed={}
 for name,text in blocks.items():
  rows=[]
  for line in text.splitlines():
   if line.startswith('+'):rows[-1]+=' '+line[1:]
   elif line.strip() and not line.startswith('*'):rows.append(line)
  parsed[name]=(rows[0].split()[2:],rows[1:-1])
 parent={};caps=[];counts=defaultdict(int)
 def find(n):
  parent.setdefault(n,n)
  while parent[n]!=n:parent[n]=parent[parent[n]];n=parent[n]
  return n
 def expand(name,path,bindings,stack):
  if name in stack:raise ValueError('recursive hierarchy')
  ports,rows=parsed[name]
  if len(ports)!=len(bindings):raise ValueError('hierarchical port count mismatch: '+name)
  mapping=dict(zip(ports,bindings))
  def node(n):return '0' if n=='0' else mapping.get(n,path+'/'+n)
  for line in rows:
   fields=line.split();kind=fields[0][0].upper()
   if kind=='C':
    if len(fields)!=4:raise ValueError('constant two-terminal capacitance required')
    caps.append((node(fields[1]),node(fields[2]),number(fields[3])));counts['expanded_capacitors']+=1
   elif kind=='R':
    if len(fields)!=4:raise ValueError('constant two-terminal resistance required')
    if number(fields[3])==0:parent[find(node(fields[1]))]=find(node(fields[2]));counts['zero_R_aliases']+=1
   elif kind=='X':
    tokens=[]
    for t in fields[1:]:
     if '=' in t:break
     tokens.append(t)
    model=tokens[-1]
    if model in parsed:expand(model,path+'/'+fields[0],[node(n) for n in tokens[:-1]],stack+[name])
    elif model.startswith('sky130_fd_pr__'):counts['primitive_instances']+=1
    else:raise ValueError('unresolved model: '+model)
 expand(top,top,parsed[top][0],[])
 pairs=defaultdict(F)
 for a,b,c in caps:
  a,b=find(a),find(b)
  if a!=b:pairs[tuple(sorted((a,b)))]+=c
 return {k:v for k,v in pairs.items() if v},dict(counts),find

