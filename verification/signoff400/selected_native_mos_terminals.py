"""Enumerate external MOS wrappers and bind each terminal to saved native voltage.

Known parameterized R/D wrappers are checked before excluding them. PDK MOS
wrappers remain external device boundaries; intrinsic BSIM nodes are not implied.
"""
from collections import Counter
from audit_hierarchical_capacitance import number
from check_selected_boundary_waveforms import bind

def mos_cards(blocks,top):
 parsed={}
 for name,text in blocks.items():
  rows=[]
  for line in text.splitlines():
   if line.startswith('+'):rows[-1]+=' '+line[1:]
   elif line and not line.startswith('*'):rows.append(line)
  parsed[name]=(rows[0].split()[2:],rows[1:-1])
 for name,kind in {'__openpll_xyce_poly_resistor':'R','__openpll_xyce_pw2nd':'D'}.items():
  if name not in parsed:continue
  ports,body=parsed[name]
  if ports[:2]!=['p','n'] or any('=' not in p for p in ports[2:]) or len(body)!=1 or body[0].split()[0][0].upper()!=kind:
   raise ValueError('non-MOS wrapper changed: '+name)
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
   if f[0][0].upper()=='M':raise ValueError('bare MOS outside reviewed external wrapper')
   if f[0][0].upper()!='X':continue
   positional=[];params=[]
   for t in f[1:]:
    if '=' in t:params.append(t)
    elif params:raise ValueError('unexpected parameter continuation')
    else:positional.append(t)
   model=positional[-1];nodes=[node(n) for n in positional[:-1]]
   if model in {'__openpll_xyce_poly_resistor','__openpll_xyce_pw2nd'}:continue
   if model in parsed and not model.startswith('sky130_fd_pr__'):expand(model,path+'/'+f[0],nodes,stack+[name])
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
 return Counter((model,tuple(normalize(n) for n in nodes),params) for model,nodes,params in raw if 'nfet' in model or 'pfet' in model)

def plan(cards,top,names):
    nodes=sorted({n for (_,nn,_),count in cards.items() for n in nn})
    native=lambda n:(n[len(top)+1:] if n.startswith(top+'/') else n).replace('/',':')
    mapped={n:native(n) for n in nodes}
    coverage=bind(sorted({n for n in mapped.values() if n!='0'}),names)
    if not coverage['all_bound']:raise ValueError('missing or ambiguous native MOS terminal voltage')
    models=sorted({model for model,nn,params in cards});records=[]
    for index,((model,nn,params),count) in enumerate(sorted(cards.items())):
        if len(nn)!=4 or count<=0:raise ValueError('positive four-terminal MOS inventory required')
        indices=[-1 if mapped[n]=='0' else coverage['bindings'][mapped[n]]['index'] for n in nn]
        records.append(dict(id=index,model=model,model_index=models.index(model),nodes=list(nn),native_nodes=[mapped[n] for n in nn],indices=indices,multiplicity=count))
    return dict(models=models,records=records,expanded_MOS=sum(r['multiplicity'] for r in records),unique_MOS_cards=len(records),unique_terminal_nodes=len(nodes),bound_terminal_nodes=len(coverage['bindings']),missing_terminal_nodes=0,ambiguous_terminal_nodes=0)
