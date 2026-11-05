#!/usr/bin/env python3
"""Prepare a stronger-output variant of the isolated return fine-range candidate.

Use a certified lumped-wire diagnostic to select a nominal library load domain.
The diagnostic fixes other active boundaries and excludes nonlinear pin charge;
it does not establish functional overload or qualify physical timing. Fresh
layout, analog/PVT/range and loaded-interface checks remain mandatory.
"""
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import shutil
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save

OLD='IntegerPLL_DCO_EINVP_C1FINE160_RETURNFINE80'
TOP=OLD+'_BUF8'


def cell_block(text,name):
    match=re.search(r'\bcell\s*\(\s*"?'+re.escape(name)+r'"?\s*\)\s*\{',text)
    assert match,name
    start=at=match.end();depth=1
    while depth:
        if text[at]=='{':depth+=1
        elif text[at]=='}':depth-=1
        at+=1
    return text[start:at]


def main():
    base=ROOT/'build/timing400/release_001'
    reduction=base/'floating_capacitance_reduction_001/assessment.json'
    r=verify(reduction);assert r['all_requested_width_targets_met'] and not r['physical_timing_qualified']
    bound=next(t for t in r['targets'] if t['target']=='PLLOUT')
    assert bound['wire_capacitance_lower_ff']>0 and bound['interval_width_ff']<=1e-4
    lib=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib')
    text=lib.read_text()
    unit=re.search(r'capacitive_load_unit\s*\(\s*([0-9.eE+-]+)\s*,\s*"?(\w+)"?\s*\)',text)
    assert unit and float(unit[1])==1 and unit[2]=='pf'
    cells={}
    for strength in [1,8]:
        name=f'sky130_fd_sc_hd__buf_{strength}'
        block=cell_block(text,name)
        maximum=re.findall(r'\bmax_capacitance\s*:\s*([^;]+)',block)
        functions=re.findall(r'\bfunction\s*:\s*"([^"]+)"',block)
        assert len(maximum)==1 and len(functions)==1,(name,maximum,functions)
        function=functions[0].strip()
        while function.startswith('(') and function.endswith(')'):function=function[1:-1].strip()
        assert function=='A',(name,functions)
        cells[name]=dict(maximum_library_load_pf=float(maximum[0]),output_function='A',library_function=functions[0],
            input_pin_capacitance_pf=[float(v) for v in re.findall(r'\bcapacitance\s*:\s*([^;]+)',block)])
    old_cell='sky130_fd_sc_hd__buf_1';new_cell='sky130_fd_sc_hd__buf_8'
    assert bound['wire_capacitance_lower_ff']/1000>cells[old_cell]['maximum_library_load_pf']
    assert bound['wire_capacitance_upper_ff']/1000<cells[new_cell]['maximum_library_load_pf']
    source=ROOT/'sky130/IntegerPLL_DCO_einvp_c1fine160_returnfine80_sky130.v'
    old_plan=base/'return_fine_range_candidate_001/plan.json'
    p=json.loads(old_plan.read_text());assert sha(source)==p['candidate_source_sha256']
    original=source.read_text();before='    sky130_fd_sc_hd__buf_1 out_buf (';after='    sky130_fd_sc_hd__buf_8 out_buf ('
    assert original.count(before)==1
    changed=original.replace(OLD,TOP).replace(before,after)
    assert changed.replace(TOP,OLD).replace(after,before)==original
    target=ROOT/'sky130/IntegerPLL_DCO_einvp_c1fine160_returnfine80_buf8_sky130.v'
    directory=ROOT/'openlane'/TOP;out=base/'return_fine_output_buffer_candidate_001'
    assert not any(p.exists() for p in [target,directory,out])
    parent=ROOT/'openlane'/OLD
    config=json.loads((parent/'config.json').read_text())
    config.update(DESIGN_NAME=TOP,VERILOG_FILES=['dir::../../sky130/'+target.name])
    target.write_text(changed);directory.mkdir();out.mkdir()
    save(directory/'config.json',config)
    for name in ['pin_order.cfg','no_clock.sdc']:shutil.copyfile(parent/name,directory/name)
    inputs=[Path(__file__).resolve(),source,old_plan,lib,reduction,parent/'config.json',
        ROOT/'sky130/sky130_fd_sc_hd_pll_blackbox.v',ROOT/'verification/release_requirements_400mhz.json',ROOT/'verification/release_plan_400mhz.json']
    save(out/'plan.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),input_sha256={str(p):sha(p) for p in inputs},
        candidate_top=TOP,candidate_source=str(target),candidate_source_sha256=sha(target),
        candidate_config=str(directory/'config.json'),candidate_config_sha256=sha(directory/'config.json'),
        base_candidate_top=OLD,base_candidate_source=str(source),only_existing_cell_type_changed='out_buf',
        old_cell=old_cell,new_cell=new_cell,library_nominal_tt25_load_domain=cells,
        certified_nominal_lumped_wire_diagnostic_bound=bound,
        old_nominal_library_load_domain_exceeded_in_this_diagnostic=True,new_nominal_library_domain_contains_this_diagnostic=True,
        actual_functional_overload_or_timing_failure_proven=False,other_active_boundaries_fixed_in_diagnostic=True,
        nonlinear_device_loading_excluded=True,return_fine_load_bank_and_all_other_cells_preserved=True,
        public_ports_and_encoding_unchanged=True,physical_layout_started=False,native_analog_started=False,
        all_nominal15pvt_and_four_modes_required=True,physical_timing_qualified=False,
        release_qualified=False,adopted=False,
        next='Elaborate and audit the one cell-type change. Await adjacent-band evidence before physical implementation/adoption decisions.',scope=__doc__))
    print('Prepared isolated RF80+buf8 variant from certified wire-only load domain; nominal library comparison only; no physical/analog adoption.')


if __name__=='__main__':main()
