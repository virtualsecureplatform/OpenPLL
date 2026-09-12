#!/usr/bin/env python3
"""Narrow structural proof for the experimental strength DCO's shared drivers.

Every active driver must implement the same inversion. The first stage's
tristate drivers must be disabled during reset, when its NAND holds high.
This proof permits experimental layout only; it is not analog/CDC signoff.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

TOP='IntegerPLL_DCO_STRENGTH_DIV'


def validate(netlist,report):
    m=netlist['modules'][TOP];cells=m['cells']
    reset=m['ports']['RESET_N']['bits']
    legal_enables={tuple(reset),('0',)}
    for c in cells.values():
        if c['type']=='sky130_fd_sc_hd__and2_4' and reset in [c['connections']['A'],c['connections']['B']]:
            legal_enables.add(tuple(c['connections']['X']))
    permitted={};groups=[]
    for stage,base,source,output in [
            ('osc','osc_gate','stage2','osc_node'),
            ('stage1','stage1_gate','osc_node','stage1'),
            ('stage2','stage2_gate','stage1','stage2')]:
        a=m['netnames'][source]['bits'];z=m['netnames'][output]['bits']
        if len(a)!=1 or len(z)!=1 or not isinstance(z[0],int):raise ValueError('invalid ring node')
        base_cell=cells[base];kind='nand2_1' if stage=='osc' else 'inv_1'
        if base_cell['type']!='sky130_fd_sc_hd__'+kind or base_cell['connections']['A']!=a or base_cell['connections']['Y']!=z:
            raise ValueError('base inversion does not match ring topology')
        if stage=='osc' and base_cell['connections']['B']!=reset:
            raise ValueError('reset NAND has wrong enable')
        names={base}
        for i in range(63):
            name=f'gen_drive[{i}].{stage}_driver';c=cells[name];pins=c['connections']
            if c['type']!='sky130_fd_sc_hd__einvp_1' or pins['A']!=a or pins['Z']!=z:
                raise ValueError('parallel driver does not implement the same inversion')
            if stage=='osc' and tuple(pins['TE']) not in legal_enables:
                raise ValueError('parallel reset-stage driver is not reset gated')
            names.add(name)
        permitted[z[0]]=names;groups.append(sorted(names))
    drivers=defaultdict(set)
    for name,port in m['ports'].items():
        if port['direction']=='input':
            for bit in port['bits']:drivers[bit].add('input:'+name)
    for name,c in cells.items():
        for port,direction in c['port_directions'].items():
            if direction=='output':
                for bit in c['connections'][port]:drivers[bit].add(name)
    if {bit:names for bit,names in drivers.items() if len(names)>1}!=permitted:
        raise ValueError('unexpected shared output or input short')
    aliases={}
    for name,net in m['netnames'].items():
        for index,bit in enumerate(net['bits']):
            alias=f'{TOP}.{name}'+(f'[{index+net.get("offset",0)}]' if len(net['bits'])>1 else '')
            aliases[alias.replace('\\','')]=bit
    warnings=[line.strip().replace('\\','') for line in report.splitlines() if 'Warning:' in line]
    found=[]
    for line in warnings:
        match=re.fullmatch(r'Warning: multiple conflicting drivers for (.+):',line)
        if not match or match[1] not in aliases:raise ValueError('unexpected synthesis warning')
        found.append(aliases[match[1]])
    if len(found)!=3 or set(found)!=set(permitted) or 'Found and reported 3 problems.' not in report or 'ERROR:' in report:
        raise ValueError('synthesis diagnostics do not match the three shared nodes')
    return dict(passed=True,scope='experimental_layout_only',top=TOP,
                parallel_groups=groups,reset_contention_proof=True,expected_synthesis_check_count=3)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('netlist',type=Path);p.add_argument('report',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=validate(json.loads(a.netlist.read_text()),a.report.read_text())
    result['sha256']={str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest()
                      for f in [a.netlist,a.report,Path(__file__)]}
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print('strength_dco_driver_check=pass experimental_layout_only')


if __name__=='__main__':main()
