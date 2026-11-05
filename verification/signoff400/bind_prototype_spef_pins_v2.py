"""Bind conventional SPEF terminals to the matching extracted cell hierarchy."""
import argparse,json,re
from pathlib import Path
from common import save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from audit_hierarchical_capacitance import number


def hierarchy(text,top):
 blocks=subcircuits(text);parsed={}
 for name,block in blocks.items():
  rows=[]
  for line in block.splitlines():
   if line.startswith('+'):rows[-1]+=' '+line[1:]
   elif line and not line.startswith('*'):rows.append(line)
  parsed[name]=(rows[0].split()[2:],rows[1:-1])
 ports,rows=parsed[top];instances={};parent={}
 def find(n):
  parent.setdefault(n,n)
  if parent[n]!=n:parent[n]=find(parent[n])
  return parent[n]
 for line in rows:
  f=line.split()
  if f[0][0].upper()=='R' and number(f[-1])==0:parent[find(f[1])]=find(f[2])
  if f[0][0].upper()!='X':continue
  positional=[]
  for t in f[1:]:
   if '=' in t:break
   positional.append(t)
  model=positional[-1]
  if model not in parsed:raise ValueError('top instance must have a retained cell interface')
  interface=parsed[model][0]
  if len(interface)!=len(positional)-1:raise ValueError('cell port count mismatch')
  name=f[0][1:]
  if name in instances:raise ValueError('duplicate instance')
  instances[name]=dict(model=model,pins=dict(zip(interface,positional[:-1])))
 return ports,instances,find


def bind(spef,text,top,instance_map):
 ports,instances,find=hierarchy(text,top);results=[];failures=[]
 for net in spef['nets']:
  terms=[]
  for c in net['connections']:
   try:
    if c['kind']=='P':
     if c['node'] not in ports:raise ValueError('unknown macro port')
     logical=c['node'];model=None
    else:
     name,pin=c['node'].rsplit(':',1)
     name=re.sub(r'\\(.)',r'\1',name)
     instance=instances[instance_map[name]];logical=instance['pins'][pin];model=instance['model']
    terms.append(dict(c,logical_node=find(logical),cell_model=model))
   except (ValueError,KeyError):failures.append(dict(net=net['name'],terminal=c['node'],reason='unresolved macro/cell terminal'))
  nodes={t['logical_node'] for t in terms}
  if len(nodes)!=1:failures.append(dict(net=net['name'],reason='SPEF terminals do not map to one logical conductor',logical_nodes=sorted(nodes)))
  # Confirm the extracted resistance graph actually joins the named terminals.
  components={}
  def root(n):
   components.setdefault(n,n)
   if components[n]!=n:components[n]=root(components[n])
   return components[n]
  for r in net['resistors']:
   a,b=r['nodes'];components[root(a)]=root(b)
  groups={root(t['node']) for t in terms}
  if len(groups)>1:failures.append(dict(net=net['name'],reason='resistance graph does not connect terminals'))
  results.append(dict(net=net['name'],logical_nodes=sorted(nodes),terminals=terms,resistance_graph_terminal_components=len(groups)))
 return dict(networks=results,failures=failures,all_RC_terminals_bound_and_connected=not failures)


def run(spef_dir,reference,join_dir,output):
 output.mkdir(parents=True,exist_ok=False);sr=spef_dir/'assessment.json';rr=reference/'assessment.json'
 s,a=[json.loads(p.read_text()) for p in (sr,rr)];entry=next(x for x in a['analog_hierarchies'] if x['top'].startswith('IntegerPLL_DCO_'))
 source=Path(entry['file']);files=[spef_dir/(c+'.json') for c in ('nom','min','max')]
 join=join_dir/'join.json';mapping={}
 for row in json.loads(join.read_text())['mapping']:
  key=re.sub(r'\\(.)',r'\1',row['routed_instance'])
  if key in mapping:raise ValueError('ambiguous SPEF instance escaping')
  mapping[key]=row['extracted_instance']
 paths=[sr,rr,source,join,*files,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
 if pins[str(source)]!=a['artifacts'][str(source)]:raise ValueError('analog hierarchy changed')
 results=[];artifacts={}
 for file in files:
  if pins[str(file)]!=s['artifacts'][str(file)]:raise ValueError('parsed SPEF changed')
  result=bind(json.loads(file.read_text()),source.read_text(),entry['top'],mapping);target=output/(file.stem+'.binding.json');save(target,result);artifacts[str(target)]=sha(target)
  results.append(dict(corner=file.stem,networks=len(result['networks']),failures=len(result['failures']),all_RC_terminals_bound_and_connected=result['all_RC_terminals_bound_and_connected']))
 verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
  all_RC_terminals_bound_and_connected=all(r['all_RC_terminals_bound_and_connected'] for r in results),
  capacitance_scope_combination_validated=False,parent_loading_complete=False,validated_for_prototype=False,release_ready=False))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('spef','reference','join','output'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();run(a.spef.resolve(),a.reference.resolve(),a.join.resolve(),a.output.resolve())
