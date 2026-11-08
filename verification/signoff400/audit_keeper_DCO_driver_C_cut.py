"""Inventory exact nonrail capacitor crossings for DCO plus full native control drivers."""
import argparse,json,shlex
from collections import Counter
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from audit_keeper_flat_MOS_region_join import Aliases
from native_spice_comments import strip_floating_annotation

def capacitance(value):
    scales={'f':F(1,10**15),'p':F(1,10**12),'n':F(1,10**9),'u':F(1,10**6),'m':F(1,1000)}
    return F(value[:-1])*scales[value[-1].lower()] if value[-1].lower() in scales else F(value)

def run(flat,boundary,drivers,output):
    receipts=[p/'assessment.json' for p in [boundary,drivers]];a,c=[json.loads(p.read_text()) for p in receipts]
    for r in [a,c]:verify(r['input_sha256']);verify(r['artifacts'])
    ext=flat/'IntegerPLL_400MHz_KeeperFlatC.ext';spice=flat/'capacitance.spice'
    for r in [a,c]:
        if r['input_sha256'].get(str(ext))!=sha(ext) or r['input_sha256'].get(str(spice))!=sha(spice):raise ValueError('same native sources required')
    detail=boundary/'boundary.json';chain=drivers/'chains.json'
    files=[*receipts,detail,chain,ext,spice,Path(__file__).resolve(),Path(__file__).with_name('audit_keeper_flat_MOS_region_join.py'),Path(__file__).with_name('native_spice_comments.py')];pins={str(p):sha(p) for p in files}
    aliases=Aliases()
    for line in ext.open():
        if line.startswith('equiv '):
            f=shlex.split(line);aliases.union(f[1],f[2])
    b=json.loads(detail.read_text());chains=json.loads(chain.read_text());selected=set(b['selected_primitives'])|set(chains['retained_MOS_cards']);nodes=set();caps=[];found=set()
    for line in spice.open():
        f=strip_floating_annotation(line).split()
        if not f:continue
        if f[0] in selected:
            j=next((i for i,t in enumerate(f) if '=' in t),len(f))-1;nodes.update(aliases.find(n) for n in f[1:j]);found.add(f[0])
        elif f[0].startswith('C'):
            value=capacitance(f[3])
            if value<0:raise ValueError('nonnegative flat C source required')
            if value:caps.append((f[0],f[1],f[2],f[3]))
    if found!=selected:raise ValueError('missing selected primitive')
    rails={aliases.find(n) for n in ['VPWR','VGND','VPB','VNB','0']};interface={aliases.find(r['digital_port']['port']) for r in chains['records']};counts=Counter();crossing=[];retained_nodes=set();external_nodes=set()
    for name,n1,n2,value in caps:
        x,y=aliases.find(n1),aliases.find(n2)
        if x in rails or y in rails:counts['supply_or_ground_endpoint']+=1;continue
        if x in nodes and y in nodes:counts['both_selected_nonrail']+=1;continue
        if x not in nodes and y not in nodes:counts['both_exterior_nonrail']+=1;continue
        inside,outside=(x,y) if x in nodes else (y,x);kind='at_RTL_control_port' if inside in interface else 'away_from_RTL_control_port';counts[kind]+=1
        retained_nodes.add(inside);external_nodes.add(outside);crossing.append(dict(name=name,node1=n1,node2=n2,value=value,kind=kind))
    verify(pins);output.mkdir(parents=True,exist_ok=False);save(output/'crossing_capacitors.json',crossing)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'crossing_capacitors.json'):sha(output/'crossing_capacitors.json')},selected_primitive_count=len(selected),selected_primitive_node_count=len(nodes),nonzero_C_count=len(caps),C_card_counts=dict(counts),nonrail_crossing_count=len(crossing),nonrail_crossing_selected_node_count=len(retained_nodes),nonrail_crossing_exterior_node_count=len(external_nodes),exact_cut_closed_without_exterior_voltage_ports=not crossing,exterior_capacitors_omitted=False,exterior_nodes_clamped=False,circuit_partitioned=False,boundary_loading_qualified=False,model_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','boundary','drivers','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['flat','boundary','drivers','output']))
