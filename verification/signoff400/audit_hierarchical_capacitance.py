"""Exact hierarchical capacitance aggregation; preserves negative values and zero-R aliases."""
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
 return {k:v for k,v in pairs.items() if v},dict(counts)


def run(source,output):
 output.mkdir(parents=True,exist_ok=False);receipt=source/'native_assessment.json';a=json.loads(receipt.read_text())
 files=sorted(source.glob('*/capacitance.spice'));paths=[receipt,*files,Path(__file__).resolve(),Path(__file__).with_name('prepare_prototype_analog_reference.py')];pins={str(p):sha(p) for p in paths}
 results=[];artifacts={}
 for file in files:
  if pins[str(file)]!=a['artifacts'][str(file)]:raise ValueError('extracted source changed')
  pairs,counts=flatten(subcircuits(file.read_text()),file.parent.name);target=output/(file.parent.name+'.pairs.jsonl')
  target.write_text(''.join(json.dumps(dict(nodes=list(k),farads=str(v)))+'\n' for k,v in sorted(pairs.items())))
  negative=[v for v in pairs.values() if v<0]
  results.append(dict(top=file.parent.name,counts=counts,nonzero_aggregated_pairs=len(pairs),negative_aggregated_pairs=len(negative),negative_absolute_sum_F=str(-sum(negative,F(0))),positive_sum_F=str(sum((v for v in pairs.values() if v>0),F(0)))))
  artifacts[str(target)]=sha(target)
 verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,all_signed_capacitances_preserved=True,global_passivity_proved=False,device_capacitance_included=False,validated_for_prototype=False,release_ready=False))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('source','output'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();run(a.source.resolve(),a.output.resolve())
