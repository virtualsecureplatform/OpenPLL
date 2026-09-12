#!/usr/bin/env python3
"""Check the three intentional, identical parallel drivers in experimental DCO V2.

This narrow structural waiver permits layout experimentation, not production
signoff. Any additional synthesis warning or differing driver input is an error.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

TOP='IntegerPLL_DCO_EINVP_COARSE_V2'
PAIRS=[
    ('osc_gate','osc_gate_parallel','sky130_fd_sc_hd__nand2_8','osc_node'),
    ('gen_mirror_delay[0].gen_turn_from_mirror_input.mirror_turn','mirror_turn_parallel',
     'sky130_fd_sc_hd__nand2b_4','mirror_turn_n[0]'),
    ('gen_mirror_delay[0].gen_merge_pass.mirror_merge','mirror_merge_parallel',
     'sky130_fd_sc_hd__nand2_8','mirror_ret[0]')]


def validate(netlist,report,top=TOP):
    if top not in [TOP,'IntegerPLL_DCO_EINVP_COARSE_V3']:
        raise ValueError('unsupported experimental DCO')
    module=netlist['modules'][top]
    cells=module['cells']
    permitted={}
    groups=[]
    for left,right,kind,net in PAIRS:
        names=[left,right]+([right+'2',right+'3'] if top.endswith('_V3') else [])
        groups.append(names)
        a=cells[left]
        for name in names:
            b=cells[name]
            if a['type']!=kind or b['type']!=kind or a.get('parameters',{})!=b.get('parameters',{}):
                raise ValueError('parallel drivers have different cell types or parameters')
            if a['connections']!=b['connections'] or a['port_directions']!=b['port_directions']:
                raise ValueError('parallel drivers must have identical connections')
        y=a['connections']['Y']
        if len(y)!=1 or not isinstance(y[0],int): raise ValueError('invalid parallel output')
        permitted[y[0]]=set(names)
    drivers=defaultdict(set)
    for name,cell in cells.items():
        for port,direction in cell['port_directions'].items():
            if direction=='output':
                for bit in cell['connections'][port]: drivers[bit].add(name)
    actual={bit:names for bit,names in drivers.items() if len(names)>1}
    if actual!=permitted: raise ValueError('unexpected multiple-driver net')
    warnings=[re.sub(r'\s+','',line) for line in report.splitlines() if 'Warning:' in line]
    expected=[re.sub(r'\s+','',f'Warning: multiple conflicting drivers for {top}.\\{net}:')
              for _,_,_,net in PAIRS]
    if sorted(warnings)!=sorted(expected) or 'Found and reported 3 problems.' not in report or 'ERROR:' in report:
        raise ValueError('synthesis report contains unexpected diagnostics')
    return dict(scope='experimental_layout_only',top=top,parallel_groups=groups,
                expected_synthesis_check_count=3,passed=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('netlist',type=Path);p.add_argument('report',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--top',choices=[TOP,'IntegerPLL_DCO_EINVP_COARSE_V3'],default=TOP)
    a=p.parse_args()
    result=validate(json.loads(a.netlist.read_text()),a.report.read_text(),a.top)
    result['sha256']={str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest()
                      for f in [a.netlist,a.report,Path(__file__)]}
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
