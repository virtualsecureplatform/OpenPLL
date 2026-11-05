"""Inventory mapped sequential data/control cones; clock intent and physical CDC remain open."""
import argparse
from collections import Counter,defaultdict
from functools import lru_cache
import json
from pathlib import Path
import re
from common import save,sha,verify


def inventory(module):
    cells=module['cells'];ports=module['ports'];drivers={};aliases=defaultdict(list)
    seq={name:c for name,c in cells.items() if re.fullmatch(r'sky130_fd_sc_hs__df[rs]tp_[124]',c['type'])}
    for name,c in cells.items():
        if re.search(r'__(?:[a-z]*df|[a-z]*dl|[a-z]*latch)',c['type']) and name not in seq:
            raise ValueError('unreviewed sequential cell: '+c['type'])
        for pin,bits in c['connections'].items():
            direction=c['port_directions'][pin]
            if direction not in ('input','output'):raise ValueError('bidirectional cell port requires explicit semantics')
            if direction=='output':
                for bit in bits:
                    if not isinstance(bit,int) or bit in drivers:raise ValueError('unique mapped bit driver required')
                    drivers[bit]=(name,pin)
    primary={}
    for name,p in ports.items():
        if p['direction']=='inout':raise ValueError('bidirectional macro port requires explicit semantics')
        if p['direction']!='input':continue
        for index,bit in enumerate(p['bits']):
            if bit in primary or bit in drivers:raise ValueError('unique mapped primary-input driver required')
            primary[bit]=(name,index)
    for name,net in module.get('netnames',{}).items():
        for index,bit in enumerate(net['bits']):
            if isinstance(bit,int):aliases[bit].append(dict(name=name,index=index,async_reg=net.get('attributes',{}).get('ASYNC_REG')=='TRUE'))
    def scalar(c,pin):
        bits=c['connections'][pin]
        if len(bits)!=1:raise ValueError('scalar mapped sequential pin required')
        return bits[0]
    for c in seq.values():
        if set(c['connections']) not in ({'CLK','D','Q','RESET_B'},{'CLK','D','Q','SET_B'}):
            raise ValueError('reviewed sequential pin set required')
        for p in c['connections']:scalar(c,p)
    active=set()
    @lru_cache(None)
    def sources(bit):
        if isinstance(bit,str):
            if bit not in ('0','1'):raise ValueError('unknown/X/Z mapped source')
            return frozenset()
        if bit in primary:
            name,index=primary[bit];return frozenset([('primary_input',name,index)])
        if bit not in drivers:raise ValueError('undriven mapped bit '+str(bit))
        name,pin=drivers[bit];c=cells[name]
        if name in seq:
            if pin!='Q':raise ValueError('unreviewed sequential output')
            return frozenset([('sequential',name,scalar(c,'CLK'))])
        if re.fullmatch(r'sky130_fd_sc_hs__conb_[124]',c['type']):return frozenset()
        if bit in active:raise ValueError('combinational cycle in mapped cone')
        active.add(bit)
        try:
            result=frozenset(s for p,bits in c['connections'].items() if c['port_directions'][p]=='input' for b in bits for s in sources(b))
        finally:active.remove(bit)
        return result
    def source_records(found):
        return [dict(kind=s[0],name=s[1],**({'clock_bit':s[2]} if s[0]=='sequential' else {'port_index':s[2]})) for s in sorted(found)]
    state=[];crossings=[];control_groups=defaultdict(list);all_clocks=Counter()
    for name,c in sorted(seq.items()):
        clock=scalar(c,'CLK');data=scalar(c,'D');q=scalar(c,'Q');all_clocks[clock]+=1
        # Resolve every cone, including synchronous cones, so omissions/loops fail the complete scan.
        found=sources(data);cross=frozenset(s for s in found if s[0]=='primary_input' or s[2]!=clock)
        control=next(p for p in ('RESET_B','SET_B') if p in c['connections']);reset=scalar(c,control)
        reset_sources=sources(reset);control_groups[clock,control,reset].append(name)
        record=dict(cell=name,master=c['type'],clock_bit=clock,data_bit=data,q_bit=q,
                    asynchronous_control_pin=control,asynchronous_control_bit=reset,
                    output_aliases=aliases[q],data_sources=source_records(found),control_sources=source_records(reset_sources))
        state.append(record)
        if cross:crossings.append(dict(id='mapped-data:'+name,destination_cell=name,destination_clock_bit=clock,
                 q_bit=q,data_bit=data,sources=source_records(cross),marked_ASYNC_REG=any(a['async_reg'] for a in aliases[q])))
    controls=[dict(id='mapped-control:'+str(clock)+':'+pin+':'+str(bit),destination_clock_bit=clock,control_pin=pin,
                   control_bit=bit,destination_cells=names,sources=source_records(sources(bit)))
              for (clock,pin,bit),names in sorted(control_groups.items(),key=lambda p:str(p[0]))]
    chains=[]
    for name,c in sorted(seq.items()):
        q=scalar(c,'Q')
        if not any(a['async_reg'] for a in aliases[q]):continue
        d=scalar(c,'D')
        if d not in drivers:continue
        predecessor,pin=drivers[d]
        if predecessor not in seq or pin!='Q':continue
        before=seq[predecessor]
        if any(a['async_reg'] for a in aliases[d]) and scalar(before,'CLK')==scalar(c,'CLK'):
            chains.append(dict(first_cell=predecessor,second_cell=name,clock_bit=scalar(c,'CLK'),
                 first_q_bit=d,second_q_bit=q,matching_async_control=all(before['connections'].get(p)==c['connections'].get(p) for p in ('RESET_B','SET_B'))))
    return dict(sequential_cells=len(seq),sequential_clock_groups=[dict(clock_bit=k,cells=v,aliases=aliases[k]) for k,v in sorted(all_clocks.items(),key=lambda p:str(p[0]))],
         sequential_state=state,data_crossing_candidates=crossings,asynchronous_control_groups=controls,
         directly_connected_marked_two_stage_chains=chains,
         all_sequential_data_and_control_cones_traced=True,clock_intent_and_exceptions_qualified=False,
         complete_structural_inventory_qualified=False,physical_CDC_qualified=False,release_qualified=False)


def run(mapping,output):
    output.mkdir(parents=True,exist_ok=False);receipt=mapping/'assessment.json';a=json.loads(receipt.read_text());netlist=mapping/'mapped.json'
    if sha(netlist)!=a['artifacts'][str(netlist)]:raise ValueError('mapped netlist receipt mismatch')
    paths=[receipt,netlist,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
    design=json.loads(netlist.read_text());result=inventory(design['modules']['IntegerPLL_ProgrammedCore'])
    if result['sequential_cells']!=sum(v for k,v in a['synthesis']['counts'].items() if re.fullmatch(r'sky130_fd_sc_hs__df[rs]tp_[124]',k)):
        raise ValueError('complete sequential cell inventory mismatch')
    report=output/'inventory.json';save(report,result);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(report):sha(report)},
         all_mapped_sequential_data_and_control_cones_traced=True,sequential_cells=result['sequential_cells'],
         data_crossing_candidates=len(result['data_crossing_candidates']),asynchronous_control_groups=len(result['asynchronous_control_groups']),
         marked_two_stage_chains=len(result['directly_connected_marked_two_stage_chains']),
         complete_structural_inventory_qualified=False,post_route_connectivity_verified=False,
         physical_CDC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('mapping','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();run(a.mapping.resolve(),a.output.resolve())
