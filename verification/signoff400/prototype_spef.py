"""Strict exact-value SPEF reader for the conventional prototype interconnect flow."""
import argparse,json,re
from fractions import Fraction as F
from pathlib import Path
from common import save,sha,verify


def parse(text):
 names={};nets=[];current=None;section=None;units={};design=None;pin_caps_excluded=False
 def resolve(token):
  if not token.startswith('*'):return token
  m=re.fullmatch(r'\*(\d+)(.*)',token)
  if not m or m[1] not in names:raise ValueError('unresolved SPEF name '+token)
  return names[m[1]]+m[2]
 def positive(token):
  value=F(token)
  if value<0:raise ValueError('negative SPEF element value')
  return value
 for line in text.splitlines():
  f=line.split()
  if not f or line.startswith('//'):continue
  if f[0]=='*DESIGN':design=' '.join(f[1:]).strip('"')
  elif f[0]=='*DESIGN_FLOW':pin_caps_excluded='PIN_CAP NONE' in line
  elif f[0] in ('*C_UNIT','*R_UNIT'):
   if f[0] in units or len(f)!=3:raise ValueError('duplicate or invalid SPEF units')
   factors={'PF':F(1,10**12),'FF':F(1,10**15),'OHM':F(1)}
   if f[2] not in factors:raise ValueError('unsupported SPEF unit')
   units[f[0]]=positive(f[1])*factors[f[2]]
   if units[f[0]]<=0:raise ValueError('positive SPEF unit required')
  elif f[0]=='*NAME_MAP':section='names'
  elif f[0]=='*D_NET':
   if current is not None or len(f)!=3:raise ValueError('unterminated SPEF network')
   current=dict(name=resolve(f[1]),declared_capacitance=positive(f[2]),connections=[],capacitors=[],resistors=[]);section=None
  elif f[0] in ('*CONN','*CAP','*RES'):
   if current is None:raise ValueError('SPEF section outside network')
   section=f[0]
  elif f[0]=='*END':
   if current is None:raise ValueError('unexpected network end')
   nets.append(current);current=None;section=None
  elif section=='names':
   if len(f)!=2 or not re.fullmatch(r'\*\d+',f[0]) or f[0][1:] in names:raise ValueError('invalid SPEF name map')
   names[f[0][1:]]=f[1]
  elif current is not None:
   if section=='*CONN':
    if f[0] not in ('*P','*I') or len(f)<3 or f[2] not in ('I','O','B'):raise ValueError('unsupported SPEF connection')
    current['connections'].append(dict(kind=f[0][1:],node=resolve(f[1]),direction=f[2]))
   elif section=='*CAP':
    if len(f) not in (3,4) or not f[0].isdigit():raise ValueError('invalid SPEF capacitance')
    current['capacitors'].append(dict(id=f[0],nodes=[resolve(t) for t in f[1:-1]],value=positive(f[-1])))
   elif section=='*RES':
    if len(f)!=4 or not f[0].isdigit():raise ValueError('invalid SPEF resistance')
    current['resistors'].append(dict(id=f[0],nodes=[resolve(t) for t in f[1:3]],value=positive(f[-1])))
   else:raise ValueError('unrecognized network record')
 if current is not None or not nets or not design or set(units)!={'*C_UNIT','*R_UNIT'}:raise ValueError('incomplete SPEF')
 if len({n['name'] for n in nets})!=len(nets):raise ValueError('duplicate SPEF network')
 for net in nets:
  for kind in ('connections','capacitors','resistors'):
   ids=[x['node'] if kind=='connections' else x['id'] for x in net[kind]]
   if len(set(ids))!=len(ids):raise ValueError('duplicate SPEF section record')
  net['declared_capacitance_F']=str(net.pop('declared_capacitance')*units['*C_UNIT'])
  for element in net['capacitors']:element['farads']=str(element.pop('value')*units['*C_UNIT'])
  for element in net['resistors']:element['ohms']=str(element.pop('value')*units['*R_UNIT'])
 return dict(design=design,pin_capacitance_excluded=pin_caps_excluded,nets=nets)


def run(lineage,output):
 output.mkdir(parents=True,exist_ok=False);receipt=lineage/'assessment.json';a=json.loads(receipt.read_text());paths=[receipt,Path(__file__).resolve()]
 paths.extend(Path(r['source']) for r in a['conventional_interconnect_views']);pins={str(p):sha(p) for p in paths};results=[];artifacts={}
 for row in a['conventional_interconnect_views']:
  source=Path(row['source'])
  if pins[str(source)]!=row['sha256']:raise ValueError('RCX source changed')
  result=parse(source.read_text());file=output/(row['interconnect_corner']+'.json');save(file,result);artifacts[str(file)]=sha(file)
  results.append(dict(corner=row['interconnect_corner'],design=result['design'],nets=len(result['nets']),
    connections=sum(len(n['connections']) for n in result['nets']),resistors=sum(len(n['resistors']) for n in result['nets']),capacitors=sum(len(n['capacitors']) for n in result['nets']),pin_capacitance_excluded=result['pin_capacitance_excluded']))
 verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,exact_SPEF_units_and_values_parsed=True,
    RC_pin_binding_complete=False,capacitance_scope_combination_validated=False,validated_for_prototype=False,release_ready=False))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('lineage','output'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();run(a.lineage.resolve(),a.output.resolve())
