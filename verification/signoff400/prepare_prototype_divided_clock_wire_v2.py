"""Bind the actual divided-clock driver, two clock loads and output port to their wire RC."""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import time
from common_v3 import ROOT,save,sha,verify
from prototype_spef_v2 import parse
from bind_prototype_BBPD_receiver_wire import identifier
from build_prototype_DCO_rc import decimal
from resources import lease
from map_prototype_receiver_aggressors import resolve


def build(module,spef):
    bit=module['ports']['CLKDIV_RETIMED']['bits']
    if len(bit)!=1:raise ValueError('scalar divided-clock output required')
    bit=bit[0];driver=[];loads=[]
    for name,cell in module['cells'].items():
        for pin,bits in cell['connections'].items():
            if bits==[bit]:(driver if cell['port_directions'][pin]=='output' else loads).append((name,pin,cell['type']))
    if len(driver)!=1 or driver[0][2]!='sky130_fd_sc_hs__dfrtp_1' or driver[0][1]!='Q':raise ValueError('actual divided-clock source differs')
    if len(loads)!=2 or any((pin,master)!=('A','sky130_fd_sc_hs__clkbuf_16') for name,pin,master in loads):raise ValueError('actual two clock-tree root loads differ')
    roles={(identifier(driver[0][0]),'Q'):'SOURCEQ',**{(identifier(name),pin):'CLKLOAD'+str(i) for i,(name,pin,master) in enumerate(sorted(loads))}}
    chosen=[]
    for net in spef['nets']:
        found={}
        for t in net['connections']:
            if t['kind']=='I':
                name,pin=t['node'].rsplit(':',1);key=(identifier(name),pin)
                if key in roles:found[t['node']]=roles[key]
            elif identifier(t['node'])=='CLKDIV_RETIMED' and t['direction']=='O':found[t['node']]='DIV'
        if 'SOURCEQ' in found.values():chosen.append((net,found))
    if len(chosen)!=1:raise ValueError('unique divided-clock wire network required')
    net,names=chosen[0]
    if set(names.values())!={'SOURCEQ','DIV','CLKLOAD0','CLKLOAD1'}:raise ValueError('all actual divided-clock terminals must be bound')
    owned={t['node'] for t in net['connections']}
    owned.update(n for r in net['resistors'] for n in r['nodes'])
    owned.update(c['nodes'][0] for c in net['capacitors'] if len(c['nodes'])==1)
    tokens=set(owned)
    for c in net['capacitors']:
        if F(c['farads']):tokens.update(c['nodes'])
    outside=sorted(tokens-owned);aggressors=[]
    for i,n in enumerate(outside):names[n]='AGGR'+str(i);aggressors.append(dict(port=names[n],spef_node=n))
    for n in sorted(owned):
        if n not in names:names[n]='wire_'+str(len(names))
    ports=['SOURCEQ','DIV','CLKLOAD0','CLKLOAD1','VGND']+[a['port'] for a in aggressors]
    lines=['.subckt prototype_divided_clock_wire '+' '.join(ports)]
    graph={}
    def root(n):
        graph.setdefault(n,n)
        while graph[n]!=n:graph[n]=graph[graph[n]];n=graph[n]
        return n
    for i,r in enumerate(net['resistors']):
        if F(r['ohms'])<=0:raise ValueError('positive conventional wire resistances required')
        a,b=r['nodes'];graph[root(a)]=root(b)
        lines.append(f'Rwire{i} {names[a]} {names[b]} {decimal(F(r["ohms"]))}')
    if len({root(t['node']) for t in net['connections']})!=1:raise ValueError('divided-clock wire terminals disconnected')
    for i,c in enumerate(net['capacitors']):
        value=F(c['farads'])
        if value<0:raise ValueError('negative conventional wire C')
        if not value:continue
        if not any(n in owned for n in c['nodes']):raise ValueError('wire coupling has no owned endpoint')
        nodes=[names[n] for n in c['nodes']]
        if len(nodes)==1:nodes.append('VGND')
        if len(nodes)!=2:raise ValueError('two-terminal wire capacitor required')
        lines.append(f'Cwire{i} {nodes[0]} {nodes[1]} {decimal(value)}')
    lines.append('.ends prototype_divided_clock_wire')
    return '\n'.join(lines)+'\n',dict(interface=ports,net=net['name'],logical_bit=bit,driver=driver,loads=sorted(loads),
        terminal_binding={t['node']:names[t['node']] for t in net['connections']},off_network_aggressors=aggressors,
        wire_resistors=len(net['resistors']),wire_capacitors=sum(bool(F(c['farads'])) for c in net['capacitors']),
        declared_wire_capacitance_F=net['declared_capacitance_F'],all_actual_terminals_bound=True,all_named_terminals_R_connected=True)


def run(output):
    output.mkdir(parents=True,exist_ok=False);base=ROOT/'build/signoff400';routed=base/'startup_timing_routed_CDC_inventory_001/routed.json';rr=routed.parent/'assessment.json'
    spef=base/'startup_corrected_timing_repair_003/route.nom.spef';sr=spef.parent/'assessment.json'
    for p,rp in ((routed,rr),(spef,sr)):
        r=json.loads(rp.read_text())
        if r['artifacts'].get(str(p))!=sha(p):raise ValueError('divided-clock wire source changed')
    paths=[routed,rr,spef,sr,Path(__file__).resolve(),Path(__file__).with_name('prototype_spef_v2.py'),Path(__file__).with_name('map_prototype_receiver_aggressors.py')];pins={str(p):sha(p) for p in paths}
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+1200):
        module=json.loads(routed.read_text())['modules']['IntegerPLL_ProgrammedCore'];parsed=parse(spef.read_text())
        text,mapping=build(module,parsed)
        net=next(n for n in parsed['nets'] if n['name']==mapping['net'])
        mapping['aggressor_ownership']=resolve(mapping,dict(networks=[dict(net,net=net['name'],logical_bit=mapping['logical_bit'])]),parsed,module)
        mapping['source_driver_signal_bits']=module['cells'][mapping['driver'][0][0]]['connections']
        mapping['clock_buffer_outputs']=[dict(bit=module['cells'][name]['connections']['X'][0],port='BUF'+str(i)) for i,(name,pin,master) in enumerate(mapping['loads'])]
    model=output/'wire.spice';model.write_text(text);detail=output/'wire.json';save(detail,mapping);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (model,detail)},
        all_actual_divided_clock_terminals_bound=True,all_named_terminals_R_connected=True,
        parent_boundary_RC_included=False,alternative_driver_placed_and_routed=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    print('Bound divided-clock wire:',mapping['wire_resistors'],'R,',mapping['wire_capacitors'],'C,',len(mapping['off_network_aggressors']),'aggressor terminals')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
