"""Resolve every routed synchronizer interstage buffer/inverter, without a delay claim."""
import argparse
import json
from pathlib import Path
import re
from common import save,sha,verify


def trace(module,first,second):
    cells=module['cells'];drivers={}
    for name,c in cells.items():
        for pin,bits in c['connections'].items():
            if c['port_directions'][pin]=='output':
                for bit in bits:
                    if bit in drivers:raise ValueError('unique interstage driver required')
                    drivers[bit]=(name,pin)
    def scalar(c,p):
        value=c['connections'][p]
        if len(value)!=1:raise ValueError('scalar interstage pin required')
        return value[0]
    start=scalar(cells[first],'Q');bit=scalar(cells[second],'D');seen=set();back=[];parity=0
    while bit!=start:
        if bit in seen or len(back)>=256:raise ValueError('cyclic or unbounded interstage path')
        seen.add(bit)
        if bit not in drivers:raise ValueError('interstage path does not reach the first-stage Q')
        name,out=drivers[bit];c=cells[name]
        kind=re.fullmatch(r'sky130_fd_sc_hs__(clkbuf|buf|clkinv|inv)_(1|2|4|8|16)',c['type'])
        if not kind:raise ValueError('unreviewed interstage logic: '+c['type'])
        incoming=[p for p,d in c['port_directions'].items() if d=='input']
        outgoing=[p for p,d in c['port_directions'].items() if d=='output']
        if len(incoming)!=1 or outgoing!=[out]:raise ValueError('single-input/output interstage buffer required')
        inversion=kind[1] in ('clkinv','inv');parity^=inversion
        before=scalar(c,incoming[0]);back.append(dict(routed_cell=name,routed_master=c['type'],input_pin=incoming[0],
            output_pin=out,input_bit=before,output_bit=bit,inverts=inversion));bit=before
    if parity:raise ValueError('odd inversion between synchronizer stages')
    return dict(first_cell=first,second_cell=second,first_Q_bit=start,second_D_bit=scalar(cells[second],'D'),
                intermediate_cells=list(reversed(back)),inversion_parity=parity,
                combinational_interstage_logic_limited_to_buffers_and_inverters=True)


def run(obligations,binding,routed,output):
    output.mkdir(parents=True,exist_ok=False);receipts=[p/'assessment.json' for p in (obligations,binding,routed)]
    a,b,c=[json.loads(p.read_text()) for p in receipts]
    data=obligations/'obligations.json';physical=binding/'binding.json';netlist=routed/'routed.json'
    if b.get('all_synchronizer_stages_bound_to_routed_database') is not True:raise ValueError('complete physical stage binding required')
    if b['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]) or b['input_sha256'].get(str(receipts[2]))!=sha(receipts[2]):
        raise ValueError('physical binding uses another obligation or routed netlist receipt')
    paths=[*receipts,data,physical,netlist,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
    expected={str(data):a['artifacts'][str(data)],str(physical):b['artifacts'][str(physical)],str(netlist):c['artifacts'][str(netlist)]}
    if any(pins[p]!=h for p,h in expected.items()):raise ValueError('interstage source artifact changed')
    design=json.loads(netlist.read_text())['modules']['IntegerPLL_ProgrammedCore'];result=[]
    physical_chains={x['id']:x for x in json.loads(physical.read_text())['chains']}
    for chain in json.loads(data.read_text())['synchronizers']:
        first,second=[s['routed_cell'] for s in chain['stages']];path=trace(design,first,second)
        expected_direct=physical_chains[chain['id']]['direct_first_Q_to_second_D_net']
        if bool(path['intermediate_cells'])==expected_direct:raise ValueError('database and routed path directness differ')
        result.append(dict(path,id=chain['id'],role=chain['role'],intermediate_physical_pins_bound=False,
             delay_resolution_or_metastability_bound_qualified=False))
    report=output/'paths.json';save(report,dict(paths=result));verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(report):sha(report)},
         all_routed_synchronizer_interstage_paths_traced=True,chains=len(result),
         chains_with_intermediate_cells=sum(bool(p['intermediate_cells']) for p in result),
         intermediate_cells=sum(len(p['intermediate_cells']) for p in result),all_interstage_paths_noninverting=True,
         intermediate_physical_pins_bound=False,delay_resolution_or_metastability_bound_qualified=False,
         physical_CDC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('obligations','binding','routed','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();run(a.obligations.resolve(),a.binding.resolve(),a.routed.resolve(),a.output.resolve())
