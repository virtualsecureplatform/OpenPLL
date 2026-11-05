#!/usr/bin/env python3
"""Isolated output-alias, routed electrical/hold and antenna-jumper repair.

Uses supplied TT25 and maxRC diagnostics; fresh all-RC and independent physical
checks remain necessary. No old route or selected design is changed.
"""
import argparse
from collections import Counter
from pathlib import Path
import re

from check_compact_mapping import ALLOWED, LIB, TECH, LEF, OPENROAD, run
from check_compact_clock_tree import verify
from route_compact_candidate import PHYSICAL, RC_MODEL
from run_dco_qualification import ROOT, sha, save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route',required=True,type=Path)
    parser.add_argument('--timing',required=True,type=Path)
    parser.add_argument('--cts',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();source=args.route.resolve();timing=args.timing.resolve();cts=args.cts.resolve();out=args.output.resolve()
    verify(source/'assessment.json');timing_receipt=verify(timing/'assessment.json')
    assert timing_receipt['input_sha256'][str(source/'route.odb')]==sha(source/'route.odb')
    assert timing_receipt['input_sha256'][str(cts/'cts.tcl')]==sha(cts/'cts.tcl')
    out.mkdir(parents=True,exist_ok=False)
    exports=ROOT/'verification/timing450/exports.tcl'
    files=[Path(__file__).resolve(),Path(__file__).with_name('check_compact_mapping.py').resolve(),
           Path(__file__).with_name('check_compact_clock_tree.py').resolve(),
           Path(__file__).with_name('route_compact_candidate.py').resolve(),Path(OPENROAD),LIB,TECH,LEF,RC_MODEL,
           source/'assessment.json',source/'route.odb',timing/'assessment.json',timing/'route.max.normalized.spef',cts/'cts.tcl',exports]
    pins={str(p):sha(p) for p in files}
    constraints=(cts/'cts.tcl').read_text().split('create_clock -name REFCLK',1)[1].split('set_thread_count')[0]
    constraints='create_clock -name REFCLK'+constraints
    excluded=sorted(set(re.findall(r'\bcell\s*\(\s*"?([^"\s)]+)',LIB.read_text()))-ALLOWED)
    script=f'''read_lef {TECH}
read_lef {LEF}
read_liberty {LIB}
read_db {source}/route.odb
{constraints}
set_clock_transition 0.1 [all_clocks]
set_clock_uncertainty 0.15 [all_clocks]
set_thread_count 4
set_propagated_clock [all_clocks]
set_wire_rc -signal -layer met2
set_wire_rc -clock -layer met3
set_dont_use [get_lib_cells {{{' '.join(excluded)}}}]
read_spef {timing}/route.max.normalized.spef
remove_fillers
'''+exports.read_text().replace('@SCL@','sky130_fd_sc_hs')+f'''
# Retain actual extracted loading for initial electrical repair. New topology
# is then re-routed and re-estimated before timing repair; old SPEF is not
# reused as timing evidence for inserted cells.
repair_design -slew_margin 10 -cap_margin 10
detailed_placement
foreach net [[ord::get_db_block] getNets] {{
 if {{[$net getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$net getWire]}}
}}
set_routing_layers -signal met1-met5 -clock met3-met5
set_global_routing_layer_adjustment met2 0.5
set_global_routing_layer_adjustment met3 0.5
global_route -verbose -guide_file {out}/initial.guide -congestion_iterations 100
estimate_parasitics -global_routing
repair_design -slew_margin 10 -cap_margin 10
estimate_parasitics -global_routing
repair_timing -setup -setup_margin 0.10 -max_iterations 100
repair_timing -hold -hold_margin 0.15 -max_iterations 100
detailed_placement
filler_placement {{sky130_fd_sc_hs__fill_8 sky130_fd_sc_hs__fill_4 sky130_fd_sc_hs__fill_2 sky130_fd_sc_hs__fill_1}}
global_connect
check_placement -verbose
global_route -verbose -guide_file {out}/route.guide -congestion_iterations 100
repair_antennas sky130_fd_sc_hs__diode_2 -iterations 5 -jumper_only
estimate_parasitics -global_routing
report_checks -path_delay max -group_path_count 1 -digits 6
report_checks -path_delay min -group_path_count 1 -digits 6
report_check_types -max_slew -max_capacitance -min_pulse_width
write_db {out}/global_route.odb
detailed_route -output_drc {out}/route.drc -output_maze {out}/route.maze.log -output_guide_coverage {out}/route.coverage
write_db {out}/route.odb
write_def {out}/route.def
write_verilog {out}/route.v
check_antennas -report_file {out}/antenna.rpt
define_process_corner -ext_model_index 0 RCX_NOM
extract_parasitics -ext_model_file {RC_MODEL} -corner 0
write_spef {out}/route.nom.spef
set inventory [open {out}/masters.txt w]
foreach inst [[ord::get_db_block] getInsts] {{puts $inventory [[$inst getMaster] getName]}}
close $inventory
exit
'''
    task=out/'repair.tcl';task.write_text(script)
    code=run([OPENROAD,'-exit',task],out/'repair.log')
    log=(out/'repair.log').read_text()
    assert code==0 and 'Error:' not in log,log[-2500:]
    masters=Counter((out/'masters.txt').read_text().splitlines())
    assert set(masters)<=ALLOWED|PHYSICAL,set(masters)-(ALLOWED|PHYSICAL)
    for path,digest in pins.items():assert sha(Path(path))==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        master_counts=dict(masters),functional_cell_types=len(set(masters)-PHYSICAL),
        restricted_master_inventory_passed=True,nominal_signal_rc_extracted=True,
        adopted=False,physical_timing_qualified=False,release_qualified=False,
        scope=__doc__))


if __name__=='__main__':main()
