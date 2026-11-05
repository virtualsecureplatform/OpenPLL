#!/usr/bin/env python3
"""Restricted compact CTS feasibility with estimated parasitics, not signoff."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

from check_compact_mapping import ALLOWED, LIB, TECH, LEF, OPENROAD, run
from run_dco_qualification import sha, save


def verify(receipt):
    data = json.loads(receipt.read_text())
    for path, digest in {**data['input_sha256'], **data['artifacts']}.items():
        assert sha(Path(path)) == digest, path
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping', required=True, type=Path)
    parser.add_argument('--placement', required=True, type=Path)
    parser.add_argument('--equivalence', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    mapping, placement = args.mapping.resolve(), args.placement.resolve()
    equivalence = args.equivalence.resolve()
    placed = verify(placement/'assessment.json')
    eq = verify(equivalence/'assessment.json')
    assert placed['restricted_master_inventory_passed']
    assert eq['all_transition_and_output_functions_equivalent'] and eq['corrupted_reset_function_rejected']
    assert eq['input_sha256'][str(placement/'placed.v')] == sha(placement/'placed.v')
    assert eq['input_sha256'][str(mapping/'compact/mapped.json')] == sha(mapping/'compact/mapped.json')
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    files = [Path(__file__).resolve(), Path(__file__).with_name('check_compact_mapping.py').resolve(),
             Path(OPENROAD), LIB, TECH, LEF, placement/'placed.odb', placement/'assessment.json',
             equivalence/'assessment.json', mapping/'compact/capacity.tcl', mapping/'compact/mapped.json']
    pins = {str(p):sha(p) for p in files}
    module = json.loads((mapping/'compact/mapped.json').read_text())['modules']['IntegerPLL_AcquiringCore']
    q = module['ports']['CLKDIV_RETIMED']['bits']
    driver = [n for n,c in module['cells'].items() if c['connections'].get('Q') == q]
    assert len(driver) == 1
    constraints = (mapping/'compact/capacity.tcl').read_text().split('create_clock -name REFCLK',1)[1]
    constraints = 'create_clock -name REFCLK' + constraints.split('report_checks -path_delay max')[0]
    excluded = sorted(set(re.findall(r'\bcell\s*\(\s*"?([^"\s)]+)', LIB.read_text())) - ALLOWED)
    script = f'''read_lef {TECH}
read_lef {LEF}
read_liberty {LIB}
read_db {placement}/placed.odb
{constraints}
set_thread_count 4
set_wire_rc -signal -layer met2
set_wire_rc -clock -layer met3
set_dont_use [get_lib_cells {{{' '.join(excluded)}}}]
set block [ord::get_db_block]
set fine_driver [$block findInst {{{driver[0]}}}]
if {{$fine_driver eq {{NULL}}}} {{error "generated-clock driver missing"}}
set fine_net [[$fine_driver findITerm Q] getNet]
set cts_nets [list REFCLK PLLOUT [$fine_net getName]]
foreach port [$block getBTerms] {{
 if {{[string range [$port getName] 0 4] eq {{BBPD[}}}} {{lappend cts_nets [[$port getNet] getName]}}
}}
clock_tree_synthesis -clk_nets [join $cts_nets " "] -root_buf sky130_fd_sc_hs__clkbuf_16 -buf_list {{sky130_fd_sc_hs__clkbuf_2 sky130_fd_sc_hs__clkbuf_4 sky130_fd_sc_hs__clkbuf_8 sky130_fd_sc_hs__clkbuf_16}} -sink_clustering_enable -sink_clustering_size 8 -sink_clustering_max_diameter 30
detailed_placement
set_propagated_clock [all_clocks]
estimate_parasitics -placement
repair_design
estimate_parasitics -placement
repair_timing -setup -setup_margin 0.10 -max_iterations 100
repair_timing -hold -hold_margin 0.05 -max_iterations 100
detailed_placement
estimate_parasitics -placement
check_placement -verbose
report_checks -path_delay max -group_path_count 1 -digits 6
report_checks -path_delay min -group_path_count 1 -digits 6
report_check_types -max_slew -max_capacitance -min_pulse_width
check_setup -verbose
write_db {out}/cts.odb
write_verilog {out}/cts.v
set inventory [open {out}/masters.txt w]
foreach inst [$block getInsts] {{puts $inventory [[$inst getMaster] getName]}}
close $inventory
exit
'''
    task=out/'cts.tcl'; task.write_text(script)
    code=run([OPENROAD,'-exit',task],out/'cts.log')
    log=(out/'cts.log').read_text()
    assert code == 0 and 'Error:' not in log,log[-2500:]
    masters=Counter((out/'masters.txt').read_text().splitlines())
    assert set(masters)<=ALLOWED,set(masters)-ALLOWED
    slacks={}
    for block in log.split('Startpoint:')[1:]:
        group=re.search(r'Path Group: ([^\n]+)',block)
        kind=re.search(r'Path Type: (max|min)',block)
        slack=re.search(r'(-?\d+\.\d+)\s+slack',block)
        if group and kind and slack: slacks[f'{group[1]}:{kind[1]}']=float(slack[1])
    assert 'PLLOUT:max' in slacks and 'PLLOUT:min' in slacks
    for path,digest in pins.items(): assert sha(Path(path))==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        cell_types=len(masters),cells=sum(masters.values()),master_counts=dict(masters),
        diagnostic_slack_ns=slacks,restricted_master_inventory_passed=True,
        adopted=False,physical_timing_qualified=False,release_qualified=False,
        scope='CTS placement-estimate capacity only; supplied TT model and cross-domain exceptions. Post-CTS equivalence, routed RC, nominal15PVT and physical interface qualification remain required.'))
    print(json.dumps(dict(cell_types=len(masters),slacks=slacks)),flush=True)


if __name__ == '__main__':
    main()
