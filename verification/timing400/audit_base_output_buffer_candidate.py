#!/usr/bin/env python3
"""Elaborate and prove the intended isolated output-buffer cell substitution."""
from datetime import datetime,timezone
import copy
import json
from pathlib import Path
import subprocess
from prepare_base_output_buffer_candidate import OLD,TOP
from run_dco_qualification import ROOT,sha,save

YOSYS='/nix/store/4bmfi4470w0i3ixcaidfki18d3fyqvva-yosys-with-plugins-0.62/bin/yosys'


def validate(old,new):
    mapping={}
    for name in old['netnames'].keys()&new['netnames'].keys():
        a,b=old['netnames'][name]['bits'],new['netnames'][name]['bits']
        assert len(a)==len(b)
        for x,y in zip(a,b):assert mapping.setdefault(x,y)==y
    assert old['ports'].keys()==new['ports'].keys()
    for name,p in old['ports'].items():
        q=new['ports'][name]
        assert p['direction']==q['direction'] and [mapping[b] for b in p['bits']]==q['bits']
    assert old['cells'].keys()==new['cells'].keys() and len(old['cells'])==691
    changes=[]
    for name,cell in old['cells'].items():
        other=new['cells'][name]
        assert cell['parameters']==other['parameters']
        assert cell['port_directions']==other['port_directions']
        assert {p:[mapping[b] for b in bits] for p,bits in cell['connections'].items()}==other['connections'],name
        if cell['type']!=other['type']:
            assert name=='out_buf' and cell['type']=='sky130_fd_sc_hd__buf_1' and other['type']=='sky130_fd_sc_hd__buf_8'
            changes.append(name)
        for attr in ['keep','dont_touch']:
            assert cell['attributes'].get(attr)==other['attributes'].get(attr)
    assert changes==['out_buf']


def main():
    base=ROOT/'build/timing400/release_001'
    plan_path=base/'base_output_buffer_candidate_001/plan.json'
    plan=json.loads(plan_path.read_text())
    old_source=Path(plan['base_candidate_source']);source=Path(plan['candidate_source'])
    assert sha(source)==plan['candidate_source_sha256']
    assert plan['library_nominal_tt25_load_domain']['sky130_fd_sc_hd__buf_1']['output_function']=='A'
    assert plan['library_nominal_tt25_load_domain']['sky130_fd_sc_hd__buf_8']['output_function']=='A'
    bb=ROOT/'sky130/sky130_fd_sc_hd_pll_blackbox.v'
    out=base/'base_output_buffer_connectivity_001';out.mkdir(exist_ok=False)
    designs=[]
    for label,top,path in [('base',OLD,old_source),('candidate',TOP,source)]:
        script=out/f'{label}.ys'
        script.write_text(f'read_verilog -lib {bb}\nread_verilog -D USE_POWER_PINS {path}\nhierarchy -check -top {top}\nproc\nflatten\nwrite_json {out}/{label}.json\n')
        with (out/f'{label}.log').open('x') as log:
            subprocess.run([YOSYS,'-s',str(script)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
        designs.append(json.loads((out/f'{label}.json').read_text())['modules'][top])
    old,new=designs;validate(old,new)
    bad=copy.deepcopy(new)
    bad['cells']['out_buf']['connections']['A']=new['ports']['RESET_N']['bits']
    try:validate(old,bad)
    except AssertionError:wrong_input=True
    else:raise AssertionError('wrong output-buffer input accepted')
    bad=copy.deepcopy(new)
    another=next(name for name in bad['cells'] if name!='out_buf')
    bad['cells'][another]['type']='sky130_fd_sc_hd__buf_8'
    try:validate(old,bad)
    except AssertionError:extra_change=True
    else:raise AssertionError('unintended extra cell change accepted')
    paths=[Path(__file__).resolve(),Path(YOSYS),plan_path,old_source,source,bb]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        elaborated_cells=691,only_changed_cell='out_buf',old_cell='sky130_fd_sc_hd__buf_1',new_cell='sky130_fd_sc_hd__buf_8',
        all691_instance_connections_preserved=True,other690_cell_types_preserved=True,original_C1_fine_load_bank_preserved=160,return_fine_bank_added=False,
        public_ports_and_encoding_preserved=True,both_library_logic_functions='A',
        wrong_output_buffer_input_control_rejected=wrong_input,extra_cell_change_control_rejected=extra_change,
        physical_layout_started=False,native_analog_started=False,power_pin_insertion_not_validated=True,
        analog_input_load_frequency_and_output_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('691 connections and690 cell types preserved; only out_buf1->8; both corruption controls rejected. Physical/analog checks still required.')


if __name__=='__main__':main()
