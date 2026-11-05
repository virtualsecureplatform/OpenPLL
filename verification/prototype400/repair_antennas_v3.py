#!/usr/bin/env python3
"""Insert diodes for measured digital antenna violations, retaining provenance."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
from common import ROOT, save, sha, verify
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import LIB,LEF,TECH,OPENROAD,ALLOWED
from route_compact_candidate import PHYSICAL,RC_MODEL


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--route',required=True,type=Path)
    p.add_argument('--placement',required=True,type=Path)
    p.add_argument('--equivalence',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();source=a.route.resolve();out=a.output.resolve()
    receipt=json.loads((source/'assessment.json').read_text())
    verify(receipt['input_sha256']);verify(receipt['artifacts'])
    eq=json.loads((a.equivalence/'assessment.json').read_text())
    verify(eq['input_sha256']);verify(eq['artifacts'])
    assert eq['all_transition_and_output_functions_equivalent'] and eq['corrupted_reset_function_rejected']
    assert eq['input_sha256'][str(source/'route.v')]==sha(source/'route.v')
    audit=json.loads((source/'signoff/assessment.json').read_text());verify(audit['sha256'])
    assert audit['magic_drc_rectangles']==0
    assert 'Final result: Netlists do not match.' in (source/'signoff/compare.log').read_text()
    assert audit['power_pins_total']==audit['power_pins_connected']
    assert audit['antenna_net_violations']>0
    model=ROOT/'build/timing400/release_001/antenna_diode_load_001'
    diode=json.loads((model/'assessment.json').read_text())
    verify(diode['input_sha256']);verify(diode['artifacts'])
    assert diode['native_model_equivalence_revalidated']
    assert diode['cell']=='sky130_fd_sc_hs__diode_2'
    out.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__).resolve(),Path(OPENROAD),LIB,LEF,TECH,RC_MODEL,
           source/'assessment.json',source/'signoff/assessment.json',source/'route.odb',
           a.placement.resolve()/'diagnostic.sdc',a.equivalence.resolve()/'assessment.json',
           model/'assessment.json',model/'antenna_diode_load.lib']
    pins={str(path):sha(path) for path in files}
    script=f'''read_lef {TECH}
read_lef {LEF}
read_liberty {LIB}
read_liberty {model}/antenna_diode_load.lib
read_db {source}/route.odb
source {a.placement.resolve()}/diagnostic.sdc
set_thread_count 4
set_propagated_clock [all_clocks]
set_wire_rc -signal -layer met2
set_wire_rc -clock -layer met3
remove_fillers
set block [ord::get_db_block]
set track [$block findBTerm TRACKING]
set detector [$block findBTerm BBPD_RESET_N]
set buffer [$block findInst prototype_detector_reset_buffer]
if {{$track eq {{NULL}} || $detector eq {{NULL}} || $buffer eq {{NULL}}}} {{error "missing expected isolated reset path"}}
set track_net [$track getNet]
if {{[[$buffer findITerm A] getNet] ne $track_net || [[$buffer findITerm X] getNet] ne [$detector getNet]}} {{error "reset buffer connectivity differs"}}
if {{[$track_net getName] ne {{BBPD_RESET_N}}}} {{error "unexpected alias net name"}}
# A net with the output port's old name makes the Verilog writer emit a
# conflicting alias after moving that port. Rename the internal net explicitly.
$track_net rename prototype_tracking_internal
set victim [$block findInst {{$abc$74255$auto$blifparse.cc:397:parse_blif$75252}}]
if {{$victim eq {{NULL}} || [[$victim getMaster] getName] ne {{sky130_fd_sc_hs__a21oi_1}}}} {{error "unexpected antenna receiver"}}
if {{[[[$victim findITerm A2] getNet] getName] ne {{net93}}}} {{error "antenna receiver net changed"}}
replace_cell [$victim getName] sky130_fd_sc_hs__a21oi_4
detailed_placement
foreach net [[ord::get_db_block] getNets] {{
 if {{[$net getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$net getWire]}}
}}
set_routing_layers -signal met1-met5 -clock met3-met5
set_global_routing_layer_adjustment met2 0.5
set_global_routing_layer_adjustment met3 0.5
global_route -verbose -guide_file {out}/route.guide -congestion_iterations 100
repair_antennas sky130_fd_sc_hs__diode_2 -iterations 5 -ratio_margin 10 -diode_only
filler_placement {{sky130_fd_sc_hs__fill_8 sky130_fd_sc_hs__fill_4 sky130_fd_sc_hs__fill_2 sky130_fd_sc_hs__fill_1}}
add_global_connection -net VDD -inst_pattern {{.*}} -pin_pattern {{^(VPWR|VPB)$}} -power
add_global_connection -net VSS -inst_pattern {{.*}} -pin_pattern {{^(VGND|VNB)$}} -ground
global_connect
check_placement -verbose
write_db {out}/global_route.odb
detailed_route -output_drc {out}/route.drc -output_maze {out}/route.maze.log -output_guide_coverage {out}/route.coverage
write_db {out}/route.odb
write_def {out}/route.def
write_verilog {out}/route.v
write_verilog -include_pwr_gnd {out}/powered.v
write_abstract_lef {out}/digital.lef
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
    save(out/'status.json',dict(state='antenna_repair_running',prototype_handoff_qualified=False))
    with (out/'repair.log').open('x') as log:
        code=subprocess.run([OPENROAD,'-exit',str(task)],stdout=log,stderr=subprocess.STDOUT,timeout=43200).returncode
    text=(out/'repair.log').read_text()
    if code or 'Error:' in text:
        save(out/'status.json',dict(state='physical_build_nonpass',native_exit=code))
        raise RuntimeError(text[-2500:])
    counts=Counter((out/'masters.txt').read_text().splitlines())
    assert set(counts)<=ALLOWED|PHYSICAL|{'sky130_fd_sc_hs__diode_2'}
    verify(pins)
    save(out/'assessment.json',dict(input_sha256=pins,
         artifacts={str(path):sha(path) for path in out.iterdir() if path.is_file() and path.name!='status.json'},
         cell_inventory=dict(counts),digital_routing_completed=True,nominal_rc_extracted=True,
         auxiliary_diode_load_is_conditional=True,physical_timing_qualified=False,
         assembled_macro_qualified=False,prototype_handoff_qualified=False))
    save(out/'status.json',dict(state='digital_route_completed_pending_independent_checks',prototype_handoff_qualified=False))


if __name__=='__main__':main()
