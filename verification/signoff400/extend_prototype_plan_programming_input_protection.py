"""Protect the bounded static programming interface after measured input-net antenna failures.

Every added diode remains subject to physical, RC, and timing checks. This does
not exempt input nets from antenna checks or qualify a release gate.
"""
import argparse
import json
from pathlib import Path
from common_v3 import PROFILE, save, sha, verify
from audit_prototype_macro_interface_reuse import interface

PORT_WIDTHS = {'STARTUP_COARSE':6, 'STARTUP_FINE':8, 'STARTUP_INCREASING':1, 'KI':8, 'KP':5}


def bit_name(name, port, index):
    width=len(port['bits'])
    logical=index if not port.get('upto',0) else width-1-index
    return name if width==1 else f"{name}[{logical+port.get('offset',0)}]"


def select_targets(module, physical_pins):
    nets={}
    for name,width in PORT_WIDTHS.items():
        port=module['ports'][name]
        if port['direction']!='input' or len(port['bits'])!=width:
            raise ValueError('static programming interface differs')
        for index,bit in enumerate(port['bits']):
            net=bit_name(name,port,index)
            if not isinstance(bit,int) or bit in nets or net not in physical_pins:
                raise ValueError('distinct physically present programming bits required')
            nets[bit]=net
    targets=set()
    for name,cell in module['cells'].items():
        for pin,bits in cell['connections'].items():
            if len(bits)!=1 or bits[0] not in nets or cell['port_directions'].get(pin)!='input':
                continue
            if pin in ('CLK','RESET_B','SET_B') or not cell['type'].startswith('sky130_fd_sc_hs__'):
                raise ValueError('only ordinary programming-data receivers are in scope')
            targets.add((nets[bits[0]],name.lstrip('\\'),pin))
    if not targets:raise ValueError('nonempty static interface required')
    return sorted(targets)


def run(plan, route, inventory, output):
    pp=plan/'plan.json'; p=json.loads(pp.read_text()); verify(p['input_sha256'])
    rr=route/'assessment.json'; r=json.loads(rr.read_text())
    ir=inventory/'assessment.json'; i=json.loads(ir.read_text())
    for record in (r,i):verify(record['input_sha256']);verify(record['artifacts'])
    if p['route_sha256']!=sha(route/'route.odb') or i['input_sha256'].get(str(rr))!=sha(rr):
        raise ValueError('same-route plan and proved inventory required')
    profile=json.loads(PROFILE.read_text())
    if profile['startup']!='externally_programmed_static_until_reset':
        raise ValueError('static programming release contract required')
    graph=inventory/'routed.json'; lef=route/'digital.lef'
    module=json.loads(graph.read_text())['modules']['IntegerPLL_ProgrammedCore']
    targets=select_targets(module,set(interface(lef.read_text())['pins']))
    measured={tuple(t) for t in p.get('antenna_targets',[])}
    if not measured or not measured<=set(targets):
        raise ValueError('measured remaining failures must be on the bounded programming interface')
    inputs=dict(p['input_sha256'])
    inputs.update({str(f):sha(f) for f in (pp,rr,ir,graph,lef,PROFILE,Path(__file__).resolve(),
                  Path(__file__).with_name('audit_prototype_macro_interface_reuse.py'))})
    verify(inputs);output.mkdir(parents=True,exist_ok=False)
    p.update(input_sha256=inputs,antenna_targets=targets,
             static_programming_receiver_pins=len(targets),
             additional_interface_protection_pins=len(set(targets)-measured),
             protected_programming_ports=PORT_WIDTHS,
             all_primary_input_antenna_checks_retained=True,
             independent_postroute_antenna_RC_timing_checks_required=True,
             antenna_closure_claimed=False,release_ready=False)
    save(output/'plan.json',p)
    print(json.dumps(dict(static_programming_receiver_pins=len(targets),
                          additional_interface_protection_pins=len(set(targets)-measured))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','route','inventory','output'):parser.add_argument('--'+name,required=True,type=Path)
    a=parser.parse_args();run(a.plan.resolve(),a.route.resolve(),a.inventory.resolve(),a.output.resolve())
