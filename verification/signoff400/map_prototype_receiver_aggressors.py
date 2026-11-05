"""Resolve exposed receiver coupling terminals to actual routed conductors and drivers."""
import argparse
from collections import defaultdict
from fractions import Fraction
import json
from functools import lru_cache
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from prototype_spef_v2 import parse
from bind_prototype_BBPD_receiver_wire import identifier
from compare_mapped_routed_CDC import clock_roots
from resources import lease


def resolve(model, bound, spef, module):
    wanted={r['spef_node']:r['port'] for r in model['off_network_aggressors']}
    if len(wanted)!=len(model['off_network_aggressors']):
        raise ValueError('duplicate aggressor terminal')
    owners={}; nets={n['name']:n for n in spef['nets']}
    for net in spef['nets']:
        own={t['node'] for t in net['connections']}
        own.update(n for r in net['resistors'] for n in r['nodes'])
        own.update(c['nodes'][0] for c in net['capacitors'] if len(c['nodes'])==1)
        for token in own & wanted.keys():
            if token in owners and owners[token]!=net['name']:
                raise ValueError('ambiguous aggressor conductor')
            owners[token]=net['name']
    if owners.keys()!=wanted.keys():raise ValueError('unbound aggressor terminals')
    selected={n['net'] for n in bound['networks']}
    cells={}
    for name,cell in module['cells'].items():
        key=identifier(name)
        if key in cells:raise ValueError('ambiguous routed instance normalization')
        cells[key]=(name,cell)
    aliases=defaultdict(list)
    for name,row in module['netnames'].items():
        for i,bit in enumerate(row['bits']):aliases[bit].append(dict(name=name,index=i))
    clock=clock_roots(module); result=[]
    drivers_by_bit={}
    for name,cell in module['cells'].items():
        for pin,pinbits in cell['connections'].items():
            if cell['port_directions'][pin]=='output':
                for bit in pinbits:
                    if bit in drivers_by_bit:raise ValueError('multiple logical drivers')
                    drivers_by_bit[bit]=(name,cell)
    primary={bit:(name,index) for name,p in module['ports'].items() if p['direction']=='input'
             for index,bit in enumerate(p['bits'])}
    active=set()
    @lru_cache(None)
    def origins(bit):
        if isinstance(bit,str):return (('constant',bit),)
        if bit in primary:return (('primary',*primary[bit]),)
        if bit in active:raise ValueError('combinational source cycle')
        if bit not in drivers_by_bit:raise ValueError('undriven aggressor source cone')
        name,cell=drivers_by_bit[bit]
        if 'CLK' in cell['connections']:
            return (('sequential',name,*clock(cell['connections']['CLK'][0])),)
        active.add(bit)
        try:
            return tuple(sorted({origin for pin,pinbits in cell['connections'].items()
                                 if cell['port_directions'][pin]=='input'
                                 for incoming in pinbits for origin in origins(incoming)}))
        finally:active.remove(bit)

    for token,port in sorted(wanted.items()):
        owner=owners[token]
        if owner in selected:raise ValueError('exposed aggressor belongs to selected receiver network')
        net=nets[owner];bits=set();drivers=[]
        for term in net['connections']:
            if term['kind']=='I':
                instance,pin=term['node'].rsplit(':',1)
                name,cell=cells[identifier(instance)]
                pinbits=cell['connections'][pin]
                if len(pinbits)!=1:raise ValueError('non-scalar routed terminal')
                bits.add(pinbits[0])
                if term['direction']=='O':
                    row=dict(instance=name,pin=pin,master=cell['type'])
                    if 'CLK' in cell['connections']:
                        row['clock_root']=clock(cell['connections']['CLK'][0])
                    drivers.append(row)
            else:
                name=identifier(term['node'])
                matches=[]
                for pname,p in module['ports'].items():
                    for index,bit in enumerate(p['bits']):
                        spelling=pname if len(p['bits'])==1 else f"{pname}[{index+p.get('offset',0)}]"
                        if identifier(spelling)==name:matches.append((pname,index,bit))
                if len(matches)!=1:raise ValueError('unbound primary SPEF terminal: '+repr(name))
                pname,index,bit=matches[0];bits.add(bit)
                if term['direction']=='I':drivers.append(dict(primary_input=pname,index=index))
        if len(bits)!=1 or len(drivers)!=1:raise ValueError('ambiguous aggressor logical bit/driver')
        bit=next(iter(bits));couplings=[]
        for victim in bound['networks']:
            for c in victim['capacitors']:
                if len(c['nodes'])==2 and token in c['nodes'] and Fraction(c['farads']):
                    couplings.append(dict(victim_bit=victim['logical_bit'],nodes=c['nodes'],farads=c['farads']))
        if not couplings:raise ValueError('aggressor has no nonzero victim coupling')
        result.append(dict(port=port,spef_node=token,owner_net=owner,logical_bit=bit,
                           aliases=aliases[bit],drivers=drivers,source_origins=origins(bit),victim_couplings=couplings))
    return result


def run(output):
    base=ROOT/'build/signoff400'
    paths=[base/'prototype_v3_BBPD_receiver_RC_001/model.json',
           base/'prototype_v3_BBPD_receiver_wire_binding_001/networks.json',
           base/'startup_corrected_timing_repair_003/route.nom.spef',
           base/'startup_timing_routed_CDC_inventory_001/routed.json']
    pins={str(p):sha(p) for p in paths+[Path(__file__).resolve(),Path(__file__).with_name('prototype_spef_v2.py')]}
    output.mkdir(parents=True,exist_ok=False)
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+1200):
        model,bound=json.loads(paths[0].read_text()),json.loads(paths[1].read_text())
        rows=resolve(model,bound,parse(paths[2].read_text()),json.loads(paths[3].read_text())['modules']['IntegerPLL_ProgrammedCore'])
    detail=output/'aggressors.json';save(detail,rows);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         exposed_terminals=len(rows),all_aggressor_owners_and_drivers_bound=True,
         actual_switching_activity_bounded=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    print('Bound aggressor terminals:',len(rows))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    run(p.parse_args().output.resolve())
