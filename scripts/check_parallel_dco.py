#!/usr/bin/env python3
"""Check intentional, identical parallel drivers in experimental DCOs.

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
FOUR_DRIVER_TOPS={'IntegerPLL_DCO_EINVP_COARSE_V3','IntegerPLL_DCO_EINVP_COARSE_V4',
                  'IntegerPLL_DCO_EINVP_COARSE_V5','IntegerPLL_DCO_EINVP_COARSE_V5_TURN6','IntegerPLL_DCO_EINVP_COARSE_V5_TURN10',
                  'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_C3BOOST4',
                  'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_NANDLOAD',
                  'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_MUXLOAD',
                  'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_KEEPER',
                  'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8',
                  'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8',
                  'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_C1BOOST4',
                  'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_C1TURN4',
                  'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8X8',
                  'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALBAND',
                  'IntegerPLL_DCO_EINVP_COARSE_V5_TURN18_NANDLOAD',
                  'IntegerPLL_DCO_EINVP_COARSE_V6',
                  'IntegerPLL_DCO_EINVP_COARSE_V7',
                  'IntegerPLL_DCO_EINVP_COARSE_V8',
                  'IntegerPLL_DCO_EINVP_COARSE_V9',
                  'IntegerPLL_DCO_EINVP_COARSE_V10',
                  'IntegerPLL_DCO_EINVP_COARSE_TURN32',
                  'IntegerPLL_DCO_EINVP_COARSE_TURN14',
                  'IntegerPLL_DCO_EINVP_COARSE_TURN7_SPACED',
                  'IntegerPLL_DCO_EINVP_COARSE_TURN10_SPACED',
                  'IntegerPLL_DCO_EINVP_COARSE_TURN9_SPACED',
                  'IntegerPLL_DCO_EINVP_COARSE_TURN9_TRIM',
                  'IntegerPLL_DCO_EINVP_COARSE_TURN9_TRIM_C4X2',
                  'IntegerPLL_DCO_EINVP_COARSE_TURN9_TRIM_C4X7'}
PAIRS=[
    ('osc_gate','osc_gate_parallel','sky130_fd_sc_hd__nand2_8','osc_node'),
    ('gen_mirror_delay[0].gen_turn_from_mirror_input.mirror_turn','mirror_turn_parallel',
     'sky130_fd_sc_hd__nand2b_4','mirror_turn_n[0]'),
    ('gen_mirror_delay[0].gen_merge_pass.mirror_merge','mirror_merge_parallel',
     'sky130_fd_sc_hd__nand2_8','mirror_ret[0]')]
V5_PAIRS=[
    ('gen_mirror_forward[0].gen_from_mirror_input.mirror_forward',
     'mirror_forward','sky130_fd_sc_hd__nand2_8','mirror_fwd[1]'),
    ('gen_mirror_delay[1].genblk1.gen_turn_controlled.mirror_turn',
     'mirror_turn','sky130_fd_sc_hd__nand2b_4','mirror_turn_n[1]'),
    ('gen_mirror_delay[1].gen_merge_pass.mirror_merge',
     'mirror_merge','sky130_fd_sc_hd__nand2_8','mirror_ret[1]'),
    ('gen_mirror_delay[0].gen_return_pass.mirror_return',
     'mirror_return','sky130_fd_sc_hd__nand2b_4','mirror_pass_n[0]')]


def validate(netlist,report,top=TOP):
    if top not in {TOP,*FOUR_DRIVER_TOPS}:
        raise ValueError('unsupported experimental DCO')
    module=netlist['modules'][top]
    cells=module['cells']
    permitted={}
    groups=[]
    specifications=[]
    for left,right,kind,net in PAIRS:
        names=[left,right]+([right+'2',right+'3'] if top in FOUR_DRIVER_TOPS else [])
        if top.endswith(('_BOOST8_OSC8','_BOOST8_OSC8_C1BOOST4','_BOOST8_OSC8_C1TURN4')) and right=='osc_gate_parallel':
            names.extend(f'gen_osc_boost[{i}].driver' for i in range(4))
        if top.endswith(('_V5_TURN6','_V5_TURN10','_V5_TURN10_C3BOOST4','_V5_TURN10_NANDLOAD',
                         '_V5_TURN10_MUXLOAD',
                         '_V5_TURN10_KEEPER',
                         '_V5_TURN10_BOOST8',
                         '_V5_TURN10_BOOST8_OSC8',
                         '_V5_TURN10_BOOST8_OSC8_C1BOOST4',
                         '_V5_TURN10_BOOST8_OSC8_C1TURN4',
                         '_V5_TURN10_BOOST8X8',
                         '_V5_TURN10_DUALBAND',
                         '_V5_TURN18_NANDLOAD')) and right=='mirror_turn_parallel':
            count = (18 if top.endswith('_V5_TURN18_NANDLOAD')
                     else 10 if top.endswith(('_V5_TURN10','_V5_TURN10_C3BOOST4','_V5_TURN10_NANDLOAD',
                                              '_V5_TURN10_MUXLOAD',
                                              '_V5_TURN10_KEEPER'))
                     else 10 if top.endswith(('_V5_TURN10_BOOST8',
                                              '_V5_TURN10_BOOST8_OSC8',
                                              '_V5_TURN10_BOOST8_OSC8_C1BOOST4',
                                              '_V5_TURN10_BOOST8_OSC8_C1TURN4',
                                              '_V5_TURN10_BOOST8X8',
                                              '_V5_TURN10_DUALBAND'))
                     else 6)
            names.extend([right+str(i) for i in range(4, count)])
        specifications.append((left,names,kind,net))
    if top.endswith(('_V5','_V5_TURN6','_V5_TURN10','_V5_TURN10_C3BOOST4','_V5_TURN10_NANDLOAD','_V5_TURN10_MUXLOAD','_V5_TURN10_KEEPER','_V5_TURN10_BOOST8','_V5_TURN10_BOOST8_OSC8','_V5_TURN10_BOOST8_OSC8_C1BOOST4','_V5_TURN10_BOOST8_OSC8_C1TURN4','_V5_TURN10_BOOST8X8','_V5_TURN10_DUALBAND','_V5_TURN18_NANDLOAD','_V6','_V7','_V8','_V9','_V10','_TURN32','_TURN14','_TURN7_SPACED','_TURN10_SPACED','_TURN9_SPACED','_TURN9_TRIM','_TURN9_TRIM_C4X2','_TURN9_TRIM_C4X7')):
        for left,right,kind,net in V5_PAIRS:
            coarse1_copies = (3 if top.endswith('_V9') and right == 'mirror_forward'
                              else 7 if top.endswith(('_V8','_V9')) else 3)
            prefix = 'gen_forward_copies.' if top.endswith('_V9') and right == 'mirror_forward' else ''
            names = [left]+[f'gen_coarse1_parallel[{i}].{prefix}{right}'
                            for i in range(coarse1_copies)]
            specifications.append((left,names,kind,net))
    for left,names,kind,net in specifications:
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
    expected_nets=[net for _,_,_,net in specifications]
    if top.endswith(('_BOOST8','_BOOST8_OSC8','_BOOST8_OSC8_C1BOOST4','_BOOST8_OSC8_C1TURN4','_BOOST8X8','_DUALBAND')):
        turn_bit=module['netnames']['mirror_turn_n[0]']['bits']
        osc_bit=module['netnames']['osc_node']['bits']
        coarse_bit=module['ports']['COARSETHERMAL_CODE']['bits'][0]
        coarse1_bit=module['ports']['COARSETHERMAL_CODE']['bits'][1]
        if top.endswith('_DUALBAND'):
            coarse_ports=module['ports']['COARSETHERMAL_CODE']['bits']
            effective=[module['netnames'][f'coarse_effective[{index}]']['bits'][0]
                       for index in range(47)]
            for index in range(47):
                branch=('shifted_fast' if index==0 else
                        'genblk1.shifted' if index<46 else 'genblk1.terminal')
                remap=cells[f'gen_coarse_remap[{index}].{branch}.buffer']
                kind=('sky130_fd_sc_hd__buf_8' if index==0
                      else 'sky130_fd_sc_hd__buf_1')
                if (remap['type']!=kind
                        or remap['connections']['A']!=[coarse_ports[min(index+1,46)]]
                        or remap['connections']['X']!=[effective[index]]):
                    raise ValueError(f'dual-band coarse remapping is invalid at {index}')
            decoder=cells['band_one_decode']
            if (decoder['type']!='sky130_fd_sc_hd__nand2b_1'
                    or decoder['connections']['A_N']!=[coarse_ports[1]]
                    or decoder['connections']['B']!=[coarse_ports[0]]):
                raise ValueError('dual-band selector is invalid')
            coarse_bit=decoder['connections']['Y'][0]
        therm_bits=module['ports']['DCO_THERM']['bits']
        for index in range(8):
            prefix=f'gen_turn_boost[{index}].'
            control=cells[prefix+'control']
            driver=cells[prefix+'driver']
            kind=('sky130_fd_sc_hd__einvn_8' if top.endswith('_BOOST8X8')
                  else 'sky130_fd_sc_hd__einvn_4')
            if (control['type']!='sky130_fd_sc_hd__or2_1'
                    or driver['type']!=kind
                    or control['connections']['A']!=[coarse1_bit if top.endswith('_C1BOOST4') and index<4 else coarse_bit]
                    or control['connections']['B']!=[therm_bits[8+32*index]]
                    or driver['connections']!={'A':osc_bit,
                                              'TE_B':control['connections']['X'],
                                              'Z':turn_bit}):
                raise ValueError(f'invalid switched turn driver {index}')
            permitted[turn_bit[0]].add(prefix+'driver')
        groups.append([f'gen_turn_boost[{index}].driver' for index in range(8)])
    if top.endswith('_C3BOOST4'):
        coarse=module['ports']['COARSETHERMAL_CODE']['bits']
        therm=module['ports']['DCO_THERM']['bits']
        selector=cells['select_c3']
        turn=module['netnames']['mirror_turn_n[3]']['bits']
        forward=module['netnames']['mirror_fwd[3]']['bits']
        if (selector['type']!='sky130_fd_sc_hd__and2b_1'
                or selector['connections']['A_N']!=[coarse[3]]
                or selector['connections']['B']!=[coarse[2]]):
            raise ValueError('coarse-3 boost selector is invalid')
        names=[]
        for index in range(4):
            prefix=f'gen_c3_boost[{index}].'
            control=cells[prefix+'control']
            driver=cells[prefix+'driver']
            if (control['type']!='sky130_fd_sc_hd__nand2_1'
                    or control['connections']['A']!=selector['connections']['X']
                    or control['connections']['B']!=[therm[32+64*index]]
                    or driver['type']!='sky130_fd_sc_hd__einvn_4'
                    or driver['connections']!={'A':forward,
                                              'TE_B':control['connections']['Y'],
                                              'Z':turn}):
                raise ValueError(f'invalid coarse-3 boost driver {index}')
            names.append(prefix+'driver')
        permitted.setdefault(turn[0],set()).update(names)
        permitted[turn[0]].add('gen_mirror_delay[3].genblk1.gen_turn_controlled.mirror_turn')
        groups.append(names)
        expected_nets.append('mirror_turn_n[3]')
    if top.endswith('_C1TURN4'):
        coarse_ports=module['ports']['COARSETHERMAL_CODE']['bits']
        therm_bits=module['ports']['DCO_THERM']['bits']
        decode=cells['c1_decode']
        turn_bit=module['netnames']['mirror_turn_n[1]']['bits'][0]
        fwd_bit=module['netnames']['mirror_fwd[1]']['bits']
        if (decode['type']!='sky130_fd_sc_hd__nand2b_1'
                or decode['connections']['A_N']!=[coarse_ports[1]]
                or decode['connections']['B']!=[coarse_ports[0]]):
            raise ValueError('coarse-1 boost decoder is invalid')
        names=[]
        for index in range(4):
            prefix=f'gen_c1_turn_boost[{index}].'
            control=cells[prefix+'control']
            driver=cells[prefix+'driver']
            if (control['type']!='sky130_fd_sc_hd__or2_1'
                    or control['connections']['A']!=decode['connections']['Y']
                    or control['connections']['B']!=[therm_bits[8+64*index]]
                    or driver['type']!='sky130_fd_sc_hd__einvn_4'
                    or driver['connections']!={'A':fwd_bit,
                                              'TE_B':control['connections']['X'],
                                              'Z':[turn_bit]}):
                raise ValueError(f'invalid coarse-1 turn driver {index}')
            names.append(prefix+'driver')
        permitted[turn_bit].update(names)
        groups.append(names)
    if top.endswith('_KEEPER'):
        therm_bits=module['ports']['DCO_THERM']['bits']
        osc_bit=module['netnames']['osc_node']['bits']
        ret_bit=module['netnames']['mirror_ret[0]']['bits']
        tie_hi=module['netnames']['tie_hi']['bits']
        for index in range(255):
            branch=('gen_mirror_input_load' if index%2==0 else 'gen_feedback_load')
            prefix=f'gen_dco_load[{index}].{branch}.'
            tune=cells[prefix+'tune_load']
            keeper=cells[prefix+'idle_keeper']
            bit=module['netnames'][f'load_dummy[{index}]']['bits']
            if (tune['type']!='sky130_fd_sc_hd__einvp_1'
                    or keeper['type']!='sky130_fd_sc_hd__einvn_0'
                    or tune['connections']!={'A':osc_bit if index%2==0 else ret_bit,
                                             'TE':[therm_bits[index]],'Z':bit}
                    or keeper['connections']!={'A':tie_hi,'TE_B':[therm_bits[index]],
                                               'Z':bit}
                    or len(bit)!=1 or not isinstance(bit[0],int)):
                raise ValueError(f'invalid complementary keeper at fine load {index}')
            permitted[bit[0]]={prefix+'tune_load',prefix+'idle_keeper'}
            expected_nets.append(f'load_dummy[{index}]')
    drivers=defaultdict(set)
    for name,cell in cells.items():
        for port,direction in cell['port_directions'].items():
            if direction=='output':
                for bit in cell['connections'][port]: drivers[bit].add(name)
    actual={bit:names for bit,names in drivers.items() if len(names)>1}
    if actual!=permitted: raise ValueError('unexpected multiple-driver net')
    warnings=[re.sub(r'\s+','',line) for line in report.splitlines() if 'Warning:' in line]
    expected=[re.sub(r'\s+','',f'Warning: multiple conflicting drivers for {top}.\\{net}:')
              for net in expected_nets]
    count=len(expected_nets)
    if sorted(warnings)!=sorted(expected) or f'Found and reported {count} problems.' not in report or 'ERROR:' in report:
        raise ValueError('synthesis report contains unexpected diagnostics')
    result=dict(scope='experimental_layout_only',top=top,parallel_groups=groups,
                expected_synthesis_check_count=count,passed=True)
    if top.endswith(('_V4','_V5','_V5_TURN6','_V5_TURN10','_V5_TURN10_C3BOOST4','_V5_TURN10_NANDLOAD','_V5_TURN10_MUXLOAD','_V5_TURN10_KEEPER','_V5_TURN10_BOOST8','_V5_TURN10_BOOST8_OSC8','_V5_TURN10_BOOST8_OSC8_C1BOOST4','_V5_TURN10_BOOST8_OSC8_C1TURN4','_V5_TURN10_BOOST8X8','_V5_TURN18_NANDLOAD','_V6','_V7','_V8','_V9','_V10','_TURN32','_TURN14','_TURN7_SPACED','_TURN10_SPACED','_TURN9_SPACED','_TURN9_TRIM','_TURN9_TRIM_C4X2','_TURN9_TRIM_C4X7')):
        therm_bits=module['ports']['DCO_THERM']['bits']
        loads={}
        for name,cell in cells.items():
            if not name.endswith('.tune_load'):
                continue
            match=re.fullmatch(r'gen_dco_load\[(\d+)\](?:\.[^.]+)?\.tune_load',name)
            if match is None:
                raise ValueError(f'unexpected fine-load name: {name}')
            index=int(match.group(1))
            if index in loads:
                raise ValueError(f'duplicate fine-load index: {index}')
            loads[index]=cell
        if len(therm_bits)!=255 or set(loads)!=set(range(255)):
            raise ValueError('fine loads do not cover all 255 thermometer bits independently')
        osc_bit=module['netnames']['osc_node']['bits']
        ret_bit=module['netnames']['mirror_ret[0]']['bits']
        for index,cell in loads.items():
            fine_kind = ('sky130_fd_sc_hd__nand2_1' if top.endswith('_NANDLOAD')
                         else 'sky130_fd_sc_hd__mux2_1' if top.endswith('_MUXLOAD')
                         else 'sky130_fd_sc_hd__einvp_1')
            enable_port = ('B' if top.endswith('_NANDLOAD') else
                           'S' if top.endswith('_MUXLOAD') else 'TE')
            signal_port = 'A1' if top.endswith('_MUXLOAD') else 'A'
            if (cell['type']!=fine_kind
                    or cell['connections'][enable_port]!=[therm_bits[index]]
                    or cell['connections'][signal_port]!=(osc_bit if index%2==0 else ret_bit)
                    or (top.endswith('_MUXLOAD') and
                        cell['connections']['A0']!=module['netnames']['tie_lo']['bits'])):
                raise ValueError(f'fine load {index} has wrong type or connections')
        result['independent_fine_loads']=255
    if top.endswith(('_V6','_V7','_V8','_V9','_V10','_TURN32','_TURN14','_TURN7_SPACED','_TURN10_SPACED','_TURN9_SPACED','_TURN9_TRIM','_TURN9_TRIM_C4X2','_TURN9_TRIM_C4X7')):
        extras=[(name,cell) for name,cell in cells.items()
                if name.endswith('.tune_load_extra')]
        if top.endswith('_V10'):
            expected_indices={index for index in range(255)
                              if index%4<2 or index%16 in (3,7)}
        elif top.endswith(('_V6','_V8','_V9','_TURN32','_TURN14','_TURN7_SPACED','_TURN10_SPACED','_TURN9_SPACED','_TURN9_TRIM','_TURN9_TRIM_C4X2','_TURN9_TRIM_C4X7')):
            expected_indices={index for index in range(255) if index%4<2}
        else:
            expected_indices={index for index in range(255) if index%16<10}
        found_indices=set()
        for name,cell in extras:
            match=re.fullmatch(r'gen_dco_load\[(\d+)\]\.gen_supplemental_load\.tune_load_extra',name)
            if match is None:
                raise ValueError('unexpected supplemental fine load')
            index=int(match.group(1))
            base=[other for base_name,other in cells.items()
                  if base_name.startswith(f'gen_dco_load[{index}].')
                  and base_name.endswith('.tune_load')]
            if (len(base)!=1 or cell['type']!='sky130_fd_sc_hd__einvp_1'
                    or any(cell['connections'][pin]!=base[0]['connections'][pin]
                           for pin in ('A','TE'))
                    or cell['connections']['Z']==base[0]['connections']['Z']):
                raise ValueError('supplemental fine load differs from its base load')
            found_indices.add(index)
        if len(extras)!=len(expected_indices) or found_indices!=expected_indices:
            raise ValueError('supplemental fine-load pattern is incomplete')
        result['supplemental_fine_loads']=len(expected_indices)
    if top.endswith(('_TURN32','_TURN14','_TURN7_SPACED','_TURN10_SPACED','_TURN9_SPACED','_TURN9_TRIM','_TURN9_TRIM_C4X2','_TURN9_TRIM_C4X7')):
        turn_bit=module['netnames']['mirror_turn_n[0]']['bits']
        if top.endswith('_TURN32'):
            divisor,residue=8,4
        elif top.endswith('_TURN14'):
            divisor,residue=18,10
        elif top.endswith('_TURN7_SPACED'):
            divisor,residue=36,10
        elif top.endswith(('_TURN9_SPACED','_TURN9_TRIM','_TURN9_TRIM_C4X2','_TURN9_TRIM_C4X7')):
            divisor,residue=29,10
        else:
            divisor,residue=25,10
        expected_indices={index for index in range(255) if index%divisor==residue}
        found_indices=set()
        for name,cell in cells.items():
            if not name.endswith('.tune_load_turn_extra'):
                continue
            match=re.fullmatch(r'gen_dco_load\[(\d+)\]\.gen_turn_supplemental_load\.tune_load_turn_extra',name)
            if match is None:
                raise ValueError('unexpected turn-node fine load')
            index=int(match.group(1))
            if (cell['type']!='sky130_fd_sc_hd__einvp_1'
                    or cell['connections']['A']!=turn_bit
                    or cell['connections']['TE']!=[therm_bits[index]]):
                raise ValueError('turn-node fine load has wrong type or connections')
            found_indices.add(index)
        if found_indices!=expected_indices:
            raise ValueError('turn-node fine-load pattern is incomplete')
        result['turn_node_fine_loads']=len(expected_indices)
    if top.endswith(('_TURN9_TRIM','_TURN9_TRIM_C4X2','_TURN9_TRIM_C4X7')):
        cell=cells['turn_trim_load']
        if (cell['type']!='sky130_fd_sc_hd__einvp_1'
                or cell['connections']['A']!=turn_bit
                or cell['connections']['TE']!=module['netnames']['tie_hi']['bits']):
            raise ValueError('fixed turn trim load has wrong type or connections')
        result['fixed_turn_trim_loads']=1
    if top.endswith('_TURN9_TRIM_C4X2'):
        turn4_bit=module['netnames']['mirror_turn_n[4]']['bits']
        for name in ('turn_c4_trim_load0','turn_c4_trim_load1'):
            cell=cells[name]
            if (cell['type']!='sky130_fd_sc_hd__einvp_1'
                    or cell['connections']['A']!=turn4_bit
                    or cell['connections']['TE']!=module['netnames']['tie_hi']['bits']):
                raise ValueError('coarse-4 trim load has wrong type or connections')
        result['fixed_coarse4_trim_loads']=2
    if top.endswith('_TURN9_TRIM_C4X7'):
        turn4_bit=module['netnames']['mirror_turn_n[4]']['bits']
        for index in range(7):
            cell=cells[f'gen_c4_trim[{index}].turn_c4_trim_load']
            if (cell['type']!='sky130_fd_sc_hd__einvp_1'
                    or cell['connections']['A']!=turn4_bit
                    or cell['connections']['TE']!=module['netnames']['tie_hi']['bits']):
                raise ValueError('coarse-4 trim load has wrong type or connections')
        result['fixed_coarse4_trim_loads']=7
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('netlist',type=Path);p.add_argument('report',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--top',choices=[TOP,*sorted(FOUR_DRIVER_TOPS)],default=TOP)
    a=p.parse_args()
    result=validate(json.loads(a.netlist.read_text()),a.report.read_text(),a.top)
    result['sha256']={str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest()
                      for f in [a.netlist,a.report,Path(__file__)]}
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
