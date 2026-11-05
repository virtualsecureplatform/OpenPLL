"""Build a provisional cell-internal-C plus SPEF-wire-RC hierarchy without duplicate couplings."""
import argparse,json,re
from collections import defaultdict
from decimal import Decimal,localcontext
from fractions import Fraction as F
from pathlib import Path
from common import ROOT,save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from bind_prototype_spef_pins_v2 import hierarchy,bind
from audit_hierarchical_capacitance import flatten
from check_prototype_capacitance_paths import certify


def decimal(value):
 with localcontext() as c:
  c.prec=80;return str(Decimal(value.numerator)/Decimal(value.denominator))

def build(text,top,spef,mapping):
 if not spef['pin_capacitance_excluded']:raise ValueError('SPEF must exclude cell pin capacitance')
 checked=bind(spef,text,top,mapping)
 if not checked['all_RC_terminals_bound_and_connected']:raise ValueError('incomplete RC terminal binding')
 blocks=subcircuits(text);ports,instances,_=hierarchy(text,top)
 for name in blocks:
  if name!=top and not certify(flatten(blocks,name)[0])['passivity_certified']:raise ValueError('unvalidated cell capacitor network')
 root=[]
 for line in blocks[top].splitlines():
  if line.startswith('+'):root[-1]+=' '+line[1:]
  elif line.strip():root.append(line)
 roots=root[0].split()[2:];primary={};pin_nodes={};tokens=set();couplings=defaultdict(list)
 for net in spef['nets']:
  for term in net['connections']:
   token=term['node'];tokens.add(token)
   if term['kind']=='P':primary[token]=token
   else:
    inst,pin=token.rsplit(':',1);inst=re.sub(r'\\(.)',r'\1',inst);key=(mapping[inst],pin)
    if key in pin_nodes:raise ValueError('cell pin assigned to multiple RC networks')
    pin_nodes[key]=token
  for r in net['resistors']:
   if F(r['ohms'])<=0:raise ValueError('zero/negative wire resistance requires explicit alias handling')
   tokens.update(r['nodes'])
  for cap in net['capacitors']:
   tokens.update(cap['nodes'])
   if len(cap['nodes'])==2:couplings[tuple(sorted(cap['nodes']))].append((net['name'],F(cap['farads'])))
 names={token:primary.get(token,'__openpll_rcx_'+str(i)) for i,token in enumerate(sorted(tokens))}
 if any('__openpll_rcx_' in line for line in root):raise ValueError('reserved RC node prefix collision')
 result=[root[0]];rewired=0;omitted=0
 for line in root[1:-1]:
  f=line.split()
  if not f or f[0].startswith('*'):continue
  if f[0][0].upper()=='C':omitted+=1;continue
  if f[0][0].upper()!='X':raise ValueError('unreviewed macro-level element')
  model=f[-1]
  if model not in blocks:raise ValueError('parameterized or primitive macro-level card requires review')
  interface=blocks[model].splitlines()[0].split()[2:]
  # Cell interfaces may span continuation records.
  header=[]
  for h in blocks[model].splitlines():
   if not header:header=h.split()[2:]
   elif h.startswith('+'):header.extend(h.split()[1:])
   else:break
  if len(f[1:-1])!=len(header):raise ValueError('cell pin arity changed')
  for index,pin in enumerate(header,1):
   key=(f[0][1:],pin)
   if key in pin_nodes:f[index]=names[pin_nodes[key]];rewired+=1
  result.append(' '.join(f))
 if rewired!=len(pin_nodes):raise ValueError('not every bound cell pin was rewired')
 nr=nc=0
 for net in spef['nets']:
  for r in net['resistors']:
   nr+=1;result.append(f'R__rcx{nr} {names[r["nodes"][0]]} {names[r["nodes"][1]]} {decimal(F(r["ohms"]))}')
  for cap in net['capacitors']:
   if len(cap['nodes'])==1 and F(cap['farads']):
    nc+=1;result.append(f'C__rcx{nc} {names[cap["nodes"][0]]} VGND {decimal(F(cap["farads"]))}')
 for pair,entries in sorted(couplings.items()):
  if len(entries)!=2 or entries[0][0]==entries[1][0] or entries[0][1]!=entries[1][1]:raise ValueError('unreviewed mirrored SPEF coupling convention')
  if entries[0][1]:
   nc+=1;result.append(f'C__rcx{nc} {names[pair[0]]} {names[pair[1]]} {decimal(entries[0][1])}')
 result.append('.ends '+top)
 return '* Provisional hierarchical RC: cell-local C plus routed wire RC; parent loading excluded.\n'+''.join(blocks[n] for n in sorted(blocks) if n!=top)+'\n'.join(result)+'\n',dict(rewired_cell_pins=rewired,wire_resistors=nr,wire_capacitors=nc,macro_Magic_capacitors_replaced=omitted,mirrored_coupling_pairs=len(couplings))


def run(output):
 output.mkdir(parents=True,exist_ok=False);base=ROOT/'build/signoff400';capbase=base/'prototype_v3_analog_capacitance_002';top='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
 source=capbase/top/'capacitance.spice';cr=capbase/'native_assessment.json';ca=json.loads(cr.read_text())
 sd=base/'prototype_v3_DCO_spef_002';sr=sd/'assessment.json';sa=json.loads(sr.read_text());join=base/'prototype_v3_DCO_instance_join_001/join.json'
 grid=base/'prototype_v3_DCO_instance_grid_validation_001/assessment.json';g=json.loads(grid.read_text())
 if not g['exact_primitive_length_width_grid_match'] or not g['all_instance_placements_match'] or g['input_sha256'].get(str(join.resolve()))!=sha(join):raise ValueError('independently validated placement grid required')
 mapping={}
 for row in json.loads(join.read_text())['mapping']:
  key=re.sub(r'\\(.)',r'\1',row['routed_instance'])
  if key in mapping:raise ValueError('ambiguous routed instance')
  mapping[key]=row['extracted_instance']
 files=[sd/(n+'.json') for n in ('nom','min','max')];paths=[source,cr,sr,join,grid,*files,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
 if pins[str(source)]!=ca['artifacts'][str(source)]:raise ValueError('cell capacitance source changed')
 artifacts={};results=[]
 for file in files:
  if pins[str(file)]!=sa['artifacts'][str(file)]:raise ValueError('parsed RCX changed')
  model,counts=build(source.read_text(),top,json.loads(file.read_text()),mapping);target=output/(file.stem+'.spice');target.write_text(model);artifacts[str(target)]=sha(target);results.append(dict(interconnect_corner=file.stem,model=str(target),**counts))
 verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,cell_internal_and_wire_capacitance_scopes_separated=True,mirrored_couplings_counted_once=True,wire_ground_reference='VGND',parent_loading_complete=False,full_capacitance_correlation_complete=False,validated_for_prototype=False,release_ready=False))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
 a=p.parse_args();run(a.output.resolve())
