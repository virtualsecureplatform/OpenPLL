"""Compare expanded primitive cards of analog reference and capacitance extraction."""
import argparse,json
from collections import Counter
from pathlib import Path
from common import save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from audit_hierarchical_capacitance import number


def devices(blocks,top):
 parsed={}
 for name,text in blocks.items():
  rows=[]
  for line in text.splitlines():
   if line.startswith('+'):rows[-1]+=' '+line[1:]
   elif line and not line.startswith('*'):rows.append(line)
  parsed[name]=(rows[0].split()[2:],rows[1:-1])
 parent={};raw=[]
 def find(n):
  parent.setdefault(n,n)
  if parent[n]!=n:parent[n]=find(parent[n])
  return parent[n]
 def expand(name,path,bindings,stack):
  if name in stack:raise ValueError('recursive hierarchy')
  ports,rows=parsed[name]
  if len(ports)!=len(bindings):raise ValueError('port count mismatch')
  mapping=dict(zip(ports,bindings))
  def node(n):return '0' if n=='0' else mapping.get(n,path+'/'+n)
  for line in rows:
   f=line.split()
   if f[0][0].upper()=='R' and number(f[-1])==0:parent[find(node(f[1]))]=find(node(f[2]))
   if f[0][0].upper()!='X':continue
   positional=[];params=[]
   for t in f[1:]:
    if '=' in t:params.append(t)
    elif params:raise ValueError('unexpected parameter continuation')
    else:positional.append(t)
   model=positional[-1];nodes=[node(n) for n in positional[:-1]]
   if model in parsed:expand(model,path+'/'+f[0],nodes,stack+[name])
   elif model.startswith('sky130_fd_pr__'):
    normalized=[]
    for t in params:
     key,value=t.split('=',1)
     try:value=str(number(value))
     except ValueError:raise ValueError('unreviewed primitive parameter '+t)
     normalized.append((key.lower(),value))
    raw.append((model,nodes,tuple(sorted(normalized))))
   else:raise ValueError('unresolved primitive model')
 expand(top,top,parsed[top][0],[])
 canonical={}
 def normalize(n):
  n=find(n);key='/'.join(segment[1:] if segment.startswith('Xsky130_fd_sc_hd__') else segment for segment in n.split('/'))
  if key in canonical and canonical[key]!=n:raise ValueError('ambiguous hierarchical label normalization')
  canonical[key]=n;return key
 return Counter((model,tuple(normalize(n) for n in nodes),params) for model,nodes,params in raw)


def run(reference,capacitance,output):
 output.mkdir(parents=True,exist_ok=False);r=reference/'assessment.json';c=capacitance/'native_assessment.json'
 ra,ca=[json.loads(p.read_text()) for p in (r,c)];paths=[r,c,Path(__file__).resolve()];results=[]
 for entry in ra['analog_hierarchies']:
  a=Path(entry['file']);b=capacitance/entry['top']/'capacitance.spice';paths.extend((a,b))
  if sha(a)!=ra['artifacts'][str(a)] or sha(b)!=ca['artifacts'][str(b)]:raise ValueError('analog source changed')
 pins={str(p):sha(p) for p in paths}
 for entry in ra['analog_hierarchies']:
  top=entry['top'];left=devices(subcircuits(Path(entry['file']).read_text()),top);right=devices(subcircuits((capacitance/top/'capacitance.spice').read_text()),top)
  removed=left-right;added=right-left
  detail=output/(top+'.differences.json');save(detail,dict(removed=[dict(card=list(k),count=v) for k,v in removed.items()],added=[dict(card=list(k),count=v) for k,v in added.items()]))
  results.append(dict(top=top,reference_primitives=left.total(),extracted_primitives=right.total(),removed=removed.total(),added=added.total(),exact_primitive_cards_match=left==right))
 verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in output.glob('*.differences.json')},results=results,
   hierarchical_label_normalization='X prefix on sky130_fd_sc_hd instance path components only; collisions rejected',all_expanded_primitive_cards_match=all(r['exact_primitive_cards_match'] for r in results),validated_for_prototype=False,release_ready=False))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('reference','capacitance','output'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();run(a.reference.resolve(),a.capacitance.resolve(),a.output.resolve())
