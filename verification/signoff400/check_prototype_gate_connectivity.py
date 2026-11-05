"""Screen primitive gate conductors for structural DC support; no bias/stress qualification."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import time
from common_v3 import save,sha,verify
from compare_prototype_analog_devices_v2 import devices
from prepare_prototype_analog_reference import subcircuits
from resources import lease


def screen(cards,ports):
    parent={};gates=Counter();roles=defaultdict(Counter)
    def find(n):
        parent.setdefault(n,n)
        while parent[n]!=n:parent[n]=parent[parent[n]];n=parent[n]
        return n
    def join(a,b):parent[find(a)]=find(b)
    for (model,nodes,params),count in cards.items():
        if 'nfet' in model or 'pfet' in model:
            if len(nodes)!=4:raise ValueError('four-terminal MOS required')
            d,g,s,b=nodes;gates[g]+=count;roles[d]['MOS_drain']+=count;roles[s]['MOS_source']+=count
            join(d,s)
        elif model in ('sky130_fd_pr__res_generic_po','sky130_fd_pr__diode_pw2nd_05v5'):
            if len(nodes)!=2:raise ValueError('two-terminal passive required')
            join(*nodes)
            for n in nodes:roles[n][model]+=count
        else:raise ValueError('unreviewed primitive '+model)
    if not gates:raise ValueError('no transistor gates')
    supported={find(p) for p in ports|{'0','VPWR','VPB','VGND','VNB'}}
    unsupported=[dict(node=n,gate_terminals=count,other_terminal_roles=dict(roles[n]))
                 for n,count in sorted(gates.items()) if find(n) not in supported]
    return dict(gate_conductors=len(gates),MOS_gate_terminals=sum(gates.values()),
        unsupported_gate_conductors=unsupported,all_gate_conductors_have_potential_DC_support=not unsupported,
        interpretation='MOS channels and both diode directions treated as potentially conductive; top ports externally driven.',
        capacitors_treated_as_DC_drivers=False,all_bias_states_and_voltage_stress_qualified=False,
        absence_of_unintended_static_current_qualified=False)


def run(extraction,output):
    output.mkdir(parents=True,exist_ok=False)
    receipt=extraction/'native_assessment.json';source=extraction/'IntegerPLL_400MHz_PrototypeTop/capacitance.spice'
    r=json.loads(receipt.read_text())
    if r['artifacts'].get(str(source))!=sha(source):raise ValueError('assembled extraction changed')
    paths=[receipt,source,Path(__file__).resolve(),Path(__file__).with_name('compare_prototype_analog_devices_v2.py'),Path(__file__).with_name('prepare_prototype_analog_reference.py')]
    pins={str(p):sha(p) for p in paths}
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        blocks=subcircuits(source.read_text());top='IntegerPLL_400MHz_PrototypeTop'
        header=[]
        for line in blocks[top].splitlines():
            if not header:header=line.split()[2:]
            elif line.startswith('+'):header+=line.split()[1:]
            else:break
        result=screen(devices(blocks,top),set(header))
    detail=output/'connectivity.json';save(detail,result);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
        all_gate_conductors_have_potential_DC_support=result['all_gate_conductors_have_potential_DC_support'],
        electrical_rules_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    print('Gate conductors:',result['gate_conductors'],'unsupported:',len(result['unsupported_gate_conductors']))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('extraction','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.extraction.resolve(),a.output.resolve())
