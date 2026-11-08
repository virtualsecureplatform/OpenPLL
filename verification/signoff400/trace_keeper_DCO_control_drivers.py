"""Trace native inverter chains from DCO controls to actual digital macro ports."""
import argparse,json,shlex
from collections import Counter,defaultdict
from pathlib import Path
from common_v3 import save,sha,verify
from audit_keeper_flat_MOS_region_join import Aliases
from native_spice_comments import strip_floating_annotation

def run(flat,roles,output):
    receipt=roles/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    ext=flat/'IntegerPLL_400MHz_KeeperFlatC.ext';spice=flat/'capacitance.spice';detail=roles/'roles.json'
    if a['input_sha256'].get(str(spice))!=sha(spice):raise ValueError('same native SPICE required')
    pins={**a['input_sha256'],**{str(p):sha(p) for p in [receipt,detail,ext,spice,Path(__file__).resolve(),Path(__file__).with_name('audit_keeper_flat_MOS_region_join.py')]}}
    aliases=Aliases()
    for line in ext.open():
        if line.startswith('equiv '):
            f=shlex.split(line);aliases.union(f[1],f[2])
    stops={}
    for bus,count in [('COARSETHERMAL_CODE',47),('DCO_THERM',255)]:
        for i in range(count):
            name=f'IntegerPLL_ProgrammedCore_0.{bus}[{i}]';node=aliases.find(name)
            if node in stops:raise ValueError('digital control ports aliased together')
            stops[node]=dict(bus=bus,bit=i,port=name)
    rails={aliases.find(n) for n in ['VPWR','VGND']};mos={};diffusions=defaultdict(set)
    for line in spice.open():
        f=strip_floating_annotation(line).split()
        if not f or not f[0].startswith('X'):continue
        j=next((i for i,t in enumerate(f) if '=' in t),len(f))-1;model=f[j]
        if 'nfet' not in model and 'pfet' not in model:continue
        if j!=5:raise ValueError('four-terminal MOS required')
        nodes=[aliases.find(n) for n in f[1:5]];mos[f[0]]=dict(model=model,nodes=nodes,card=strip_floating_annotation(line).strip())
        for n in {nodes[0],nodes[2]}-rails:diffusions[n].add(f[0])
    r=json.loads(detail.read_text());records=[];retained=set()
    for output_node,kind in r['classifications'].items():
        if kind!='exterior_inverter_output':continue
        node=aliases.find(output_node);seen=set();stages=[]
        while node not in stops:
            if node in seen:raise ValueError('inverter cycle')
            seen.add(node);ids=diffusions[node];gates=set();types=set()
            if not ids:raise ValueError('driver absent')
            for name in ids:
                device=mos[name];d,g,s,b=device['nodes'];nfet='nfet' in device['model'];rail=aliases.find('VGND' if nfet else 'VPWR')
                if {d,s}!={node,rail} or b!=rail:raise ValueError('non-inverter diffusion or body at '+output_node)
                gates.add(g);types.add(nfet)
            if len(gates)!=1 or types!={True,False}:raise ValueError('not a complementary single-input inverter')
            previous=next(iter(gates));stages.append(dict(output=node,input=previous,devices=sorted(ids)));retained.update(ids);node=previous
            if len(stages)>20:raise ValueError('unexpectedly long control chain')
        records.append(dict(DCO_boundary_node=output_node,digital_port=stops[node],inverting_stages=len(stages),polarity=-1 if len(stages)%2 else 1,stages=stages))
    if len(records)!=302 or len({r['digital_port']['port'] for r in records})!=302:raise ValueError('one-to-one 302 control ports required')
    verify(pins);output.mkdir(parents=True,exist_ok=False)
    save(output/'chains.json',dict(records=records,retained_MOS_cards={n:mos[n]['card'] for n in sorted(retained)}))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'chains.json'):sha(output/'chains.json')},all_302_controls_reach_unique_actual_digital_macro_ports=True,stage_count_histogram=dict(Counter(r['inverting_stages'] for r in records)),polarity_histogram=dict(Counter(r['polarity'] for r in records)),retained_driver_MOS_count=len(retained),capacitive_loading_preserved=False,reset_and_receiver_partitioned=False,circuit_partitioned=False,model_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','roles','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['flat','roles','output']))
