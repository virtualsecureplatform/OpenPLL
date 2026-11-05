"""Bind selected receiver terminals to conventional nominal wire RC, retaining omitted loads."""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import re
import time
from common_v3 import ROOT,save,sha,verify
from prototype_spef_v2 import parse
from resources import lease


def identifier(name):return re.sub(r'\\(.)',r'\1',name).lstrip('\\')


def bind(module,selected,spef):
    if not spef['pin_capacitance_excluded']:raise ValueError('PIN_CAP NONE declaration required')
    wanted={};normalized={}
    for name in selected:
        key=identifier(name)
        if key in normalized:raise ValueError('ambiguous receiver instance normalization')
        normalized[key]=name
        cell=module['cells'][name]
        for pin,bits in cell['connections'].items():
            if len(bits)!=1:raise ValueError('scalar receiver terminals required')
            wanted[(key,pin)]=dict(routed_instance=name,pin=pin,bit=bits[0],direction=cell['port_directions'][pin])
    found={};results=[]
    for net in spef['nets']:
        selected_terms=[];outside=[]
        for term in net['connections']:
            if term['kind']=='I':
                instance,pin=term['node'].rsplit(':',1);key=(identifier(instance),pin)
                if key in wanted:
                    if key in found:raise ValueError('receiver terminal belongs to multiple SPEF nets')
                    expected=wanted[key]
                    if term['direction']!=('I' if expected['direction']=='input' else 'O'):raise ValueError('receiver pin direction mismatch')
                    found[key]=net['name'];selected_terms.append(dict(expected,spef_node=term['node']))
                else:outside.append(term)
            else:outside.append(term)
        if not selected_terms:continue
        bits={t['bit'] for t in selected_terms}
        if len(bits)!=1:raise ValueError('distinct receiver logical nets merged in SPEF')
        graph={}
        def root(n):
            graph.setdefault(n,n)
            while graph[n]!=n:graph[n]=graph[graph[n]];n=graph[n]
            return n
        for resistor in net['resistors']:
            a,b=resistor['nodes'];graph[root(a)]=root(b)
        components={root(t['node']) for t in net['connections']}
        if len(components)!=1:raise ValueError('SPEF resistance graph disconnects declared terminals')
        ground=sum((F(c['farads']) for c in net['capacitors'] if len(c['nodes'])==1),F())
        coupling=sum((F(c['farads']) for c in net['capacitors'] if len(c['nodes'])==2),F())
        results.append(dict(logical_bit=next(iter(bits)),net=net['name'],selected_terminals=selected_terms,outside_terminals=outside,
            declared_wire_capacitance_F=net['declared_capacitance_F'],sum_ground_wire_capacitance_F=str(ground),sum_coupling_records_F=str(coupling),
            resistors=net['resistors'],capacitors=net['capacitors'],all_named_terminal_connections=net['connections']))
    if set(found)!=set(wanted):raise ValueError('unbound selected receiver terminals: '+str(sorted(set(wanted)-set(found))))
    bit_nets={}
    for row in results:
        if row['logical_bit'] in bit_nets:raise ValueError('receiver logical net split across SPEF networks')
        bit_nets[row['logical_bit']]=row['net']
    return dict(networks=results,selected_terminals=len(found),selected_networks=len(results),
        all_receiver_terminals_bound=True,all_named_resistance_graphs_connected=True,pin_capacitance_excluded=True,
        outside_receiver_pin_capacitance_bounded=False,parent_and_final_fill_coupling_included=False)


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    receiver=ROOT/'build/signoff400/prototype_v3_BBPD_receiver_002';rr=receiver/'assessment.json';mapping=receiver/'receiver.json'
    inv=ROOT/'build/signoff400/startup_timing_routed_CDC_inventory_001';ir=inv/'assessment.json';routed=inv/'routed.json'
    route=ROOT/'build/signoff400/startup_corrected_timing_repair_003';sr=route/'assessment.json';spef=route/'route.nom.spef'
    receipts=[json.loads(p.read_text()) for p in (rr,ir,sr)]
    for file,r in zip((mapping,routed,spef),receipts):
        if r['artifacts'].get(str(file))!=sha(file):raise ValueError('receiver wire source changed')
    paths=[rr,mapping,ir,routed,sr,spef,Path(__file__).resolve(),Path(__file__).with_name('prototype_spef_v2.py')]
    pins={str(p):sha(p) for p in paths}
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+1200):
        m=json.loads(mapping.read_text());module=json.loads(routed.read_text())['modules']['IntegerPLL_ProgrammedCore']
        result=bind(module,m['cells'],parse(spef.read_text()))
    detail=output/'networks.json';save(detail,result);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
        selected_terminals=result['selected_terminals'],selected_networks=result['selected_networks'],
        all_receiver_terminals_bound=True,all_named_resistance_graphs_connected=True,
        wire_networks_applied_to_native_model=False,outside_receiver_pin_capacitance_bounded=False,parent_and_final_fill_coupling_included=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False))
    print('Receiver terminals:',result['selected_terminals'],'wire networks:',result['selected_networks'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);run(p.parse_args().output.resolve())
