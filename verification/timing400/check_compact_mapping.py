#!/usr/bin/env python3
"""Compare isolated full/compact HS mappings of identical frozen RTL.

No selected design is changed. State-cut SAT compares every external output
and every matched FF's D/clock/asynchronous-control function with arbitrary
paired state. Unrouted supplied-model STA is a feasibility screen only.
"""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import re
import subprocess

from run_dco_qualification import ROOT,sha,save
from prepare_functional_matrix import FROZEN,FILES

YOSYS='/nix/store/4bmfi4470w0i3ixcaidfki18d3fyqvva-yosys-with-plugins-0.62/bin/yosys'
OPENROAD='/nix/store/qqz49dx8dpx4q9i5wriif091n7iaa0ld-openroad-2026-02-17/bin/openroad'
LIB=ROOT/'build/timing450/pdk/sky130A/libs.ref/sky130_fd_sc_hs/lib/sky130_fd_sc_hs__tt_025C_1v80.lib'
TECH=LIB.parent.parent/'techlef/sky130_fd_sc_hs__nom.tlef'
LEF=LIB.parent.parent/'lef/sky130_fd_sc_hs.lef'
TOP='IntegerPLL_AcquiringCore'
BASES={'nand2':[1,2,4,8],'nor2':[1,2,4,8],'inv':[1,2,4,8,16],
       'buf':[1,2,4,8,16],'a21oi':[1,2,4],'o21ai':[1,2,4],
       'xor2':[1,2,4],'xnor2':[1,2,4],'mux2':[1,4],'maj3':[1],
       'clkbuf':[2,4,8,16],'clkinv':[1,2,4,8,16],
       'dfrtp':[1,2,4],'dfstp':[1,2,4],'conb':[1]}
ALLOWED={'sky130_fd_sc_hs__'+family+'_'+str(strength)
         for family,strengths in BASES.items() for strength in strengths}


def run(argv,log):
    with log.open('x') as stream:
        result=subprocess.run(list(map(str,argv)),cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=43200)
    return result.returncode


def cut_pair(gold,gate):
    def sequential(module):
        result={}
        for name,cell in module['cells'].items():
            if not cell['type'].startswith('sky130_fd_sc_hs__'):
                raise ValueError('unmapped/unsupported cell: '+cell['type'])
            if cell['type'].split('__')[1].startswith(('dfrtp_','dfstp_')):
                result[name]=cell
        return result
    ff=[sequential(module) for module in (gold,gate)]
    assert ff[0] and set(ff[0])==set(ff[1]),'state correspondence is not exact'
    assert gold['ports'].keys()==gate['ports'].keys()
    for name in gold['ports']:
        a,b=gold['ports'][name],gate['ports'][name]
        assert a['direction']==b['direction'] and len(a['bits'])==len(b['bits'])
    for index,name in enumerate(sorted(ff[0])):
        a,b=ff[0][name],ff[1][name]
        assert a['type']==b['type'] and a['parameters']==b['parameters']
        assert a['connections'].keys()==b['connections'].keys()
        for cell,module in [(a,gold),(b,gate)]:
            assert cell['port_directions']['Q']=='output' and len(cell['connections']['Q'])==1
            module['ports'][f'state_{index}']=dict(direction='input',bits=cell['connections']['Q'])
            for pin,bits in cell['connections'].items():
                if pin=='Q':continue
                assert cell['port_directions'][pin]=='input' and len(bits)==1
                module['ports'][f'capture_{index}_{pin}']=dict(direction='output',bits=bits)
            del module['cells'][name]
    return len(ff[0])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    pins={str(p):sha(p) for p in [Path(__file__).resolve(),LIB,TECH,LEF,Path(YOSYS),Path(OPENROAD),*[FROZEN/f for f in FILES]]}
    cells=set(re.findall(r'\bcell\s*\(\s*"?([^"\s)]+)',LIB.read_text()))
    assert ALLOWED<=cells,ALLOWED-cells
    modules={};stats={}
    for label in ('full','compact'):
        directory=out/label;directory.mkdir()
        excluded={cell for cell in cells if 'probe' in cell or 'lpflow' in cell}
        if label=='compact':excluded=cells-ALLOWED
        script=f'''read_verilog {' '.join(str(FROZEN/f) for f in FILES)}
hierarchy -check -top {TOP}
flatten
proc
setattr -set keep 1 w:*advance_* %ci
synth -top {TOP} -flatten
dfflibmap -liberty {LIB}
abc -liberty {LIB} -D 2222 {' '.join('-dont_use '+cell for cell in sorted(excluded))}
clean
delete t:$scopeinfo
read_liberty -lib -ignore_miss_func -ignore_miss_dir {LIB}
stat -liberty {LIB}
write_verilog -norename {directory}/mapped.v
write_json {directory}/mapped.json
'''
        task=directory/'synth.ys';task.write_text(script)
        assert run([YOSYS,'-s',task],directory/'synth.log')==0
        module=json.loads((directory/'mapped.json').read_text())['modules'][TOP]
        used=Counter(cell['type'] for cell in module['cells'].values())
        if label=='compact':assert set(used)<=ALLOWED
        modules[label]=module
        stats[label]=dict(cell_types=len(used),cells=sum(used.values()),type_counts=dict(used))
        print(label,'mapped types',len(used),'cells',sum(used.values()),flush=True)

    # Formal equivalence of the combinational transition functions with
    # one-to-one matching state primitives: clocks and reset pins are outputs
    # of this miter too, so no common-clock assumption is introduced.
    gold,gate=copy.deepcopy(modules['full']),copy.deepcopy(modules['compact'])
    state_count=cut_pair(gold,gate)
    for label,module in [('CUT_GOLD',gold),('CUT_GATE',gate)]:
        save(out/(label+'.json'),dict(modules={label:module}))
    task=out/'equivalence.ys'
    task.write_text(f'''read_liberty -ignore_miss_func -ignore_miss_dir {LIB}
read_json {out}/CUT_GOLD.json
read_json {out}/CUT_GATE.json
miter -equiv -make_outputs -flatten CUT_GOLD CUT_GATE miter
hierarchy -top miter
prep -top miter -flatten
sat -verify -prove trigger 0 -show-inputs -show-outputs
''')
    eq=run([YOSYS,'-s',task],out/'equivalence.log')==0
    log=(out/'equivalence.log').read_text()
    assert eq and 'SUCCESS!' in log,log[-1800:]
    # Deliberately corrupt one captured data function; the same proof must fail.
    bad=copy.deepcopy(gate)
    pin=next(name for name in bad['ports'] if name.startswith('capture_') and name.endswith('_D'))
    original=bad['ports'][pin]['bits']
    next_bit=max(bit for cell in bad['cells'].values() for bits in cell['connections'].values() for bit in bits if isinstance(bit,int))+1
    bad['cells']['negative_data_inverter']=dict(type='sky130_fd_sc_hs__clkinv_1',parameters={},attributes={},
        port_directions={'A':'input','Y':'output'},connections={'A':original,'Y':[next_bit]})
    bad['ports'][pin]['bits']=[next_bit]
    save(out/'CUT_BAD.json',dict(modules={'CUT_GATE':bad}))
    negative=out/'negative.ys'
    negative.write_text(task.read_text().replace(str(out/'CUT_GATE.json'),str(out/'CUT_BAD.json')))
    code=run([YOSYS,'-s',negative],out/'negative.log')
    assert code!=0 and 'proof did fail' in (out/'negative.log').read_text()

    for label,module in modules.items():
        directory=out/label
        bit=module['ports']['CLKDIV_RETIMED']['bits'][0]
        clock=[name for name,cell in module['cells'].items() if cell['connections'].get('Q')==[bit]]
        assert len(clock)==1
        # This screen excludes cross-domain paths and has no placement/RC. It
        # cannot qualify CDC, recovery/removal, hold, waveform or PVT behavior.
        script=f'''read_lef {TECH}
read_lef {LEF}
read_liberty {LIB}
read_verilog {directory}/mapped.v
link_design {TOP}
create_clock -name REFCLK -period 40 [get_ports REFCLK]
create_clock -name PLLOUT -period 2.5 [get_ports PLLOUT]
create_generated_clock -name FINECLK -source [get_ports PLLOUT] -divide_by 16 [get_pins {{{clock[0]}/Q}}]
set_clock_transition 0.1 [all_clocks]
set_clock_uncertainty 0.15 [all_clocks]
set_false_path -from [get_ports RESET_N]
set_input_delay 0.5 -clock REFCLK [get_ports {{PLL_ENABLE FEEDBACK_DIVIDER* KI* KP*}}]
set_output_delay 0.5 -clock PLLOUT [get_ports CLKDIV_RETIMED]
set_output_delay 0.5 -clock FINECLK [get_ports {{DCO_CODE* DLF_CODE* DCO_THERM*}}]
set_output_delay 0.5 -clock REFCLK [get_ports {{COARSE_CODE* COARSETHERMAL_CODE* TRACKING CONFIG_BUSY FAILED BBPD_RESET_N}}]
set_load 0.005 [all_outputs]
foreach port [get_ports *] {{
 if {{[string range [get_full_name $port] 0 4] eq {{BBPD[}}}} {{
  set name EVENT_[get_full_name $port]
  create_clock -name $name -period 40 -waveform {{0 1.25}} $port
 }}
}}
foreach left [all_clocks] {{
 foreach right [all_clocks] {{
  if {{[get_full_name $left] ne [get_full_name $right]}} {{set_false_path -from $left -to $right}}
 }}
}}
report_checks -path_delay max -group_path_count 1 -digits 6
exit
'''
        task=directory/'capacity.tcl';task.write_text(script)
        assert run([OPENROAD,'-exit',task],directory/'capacity.log')==0
        text=(directory/'capacity.log').read_text()
        assert 'Error:' not in text and 'STA-0200' not in text,text[-2000:]
        values={}
        for block in text.split('Startpoint:')[1:]:
            group=re.search(r'Path Group: ([^\n]+)',block)
            slack=re.search(r'(-?\d+\.\d+)\s+slack',block)
            if group and slack:values[group[1]]=float(slack[1])
        assert 'PLLOUT' in values and 'FINECLK' in values
        stats[label]['unrouted_tt_setup_slack_ns']=values
    for path,digest in pins.items():assert sha(path)==digest,path
    save(out/'assessment.json',dict(stats=stats,matched_state_primitives=state_count,
        all_transition_and_output_functions_equivalent=True,corrupted_data_function_rejected=True,
        allowed_compact_types=sorted(ALLOWED),sha256=pins,
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file()},
        adopted=False,physical_timing_qualified=False,release_qualified=False,
        scope='Mapping feasibility only. Same frozen RTL and all external interfaces; paired-state transition SAT plus ideal-clock/unrouted TT supplied-model capacity screens. No routing,15PVT, analog/interface/noise or release qualification.'))
    print(json.dumps(stats),flush=True)


if __name__=='__main__':
    main()
