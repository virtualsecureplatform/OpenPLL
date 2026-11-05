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
    assert audit['magic_drc_rectangles']==0 and audit['lvs_unique_match']
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
set block [ord::get_db_block]
set target [$block findNet {{DLF_CODE[8]}}]
set sink_inst [$block findInst {{$auto$ff.cc:337:slice$19307}}]
if {{$target eq {{NULL}} || $sink_inst eq {{NULL}}}} {{error "missing measured antenna target"}}
if {{[[$sink_inst findITerm D] getNet] ne $target}} {{error "antenna sink connectivity changed"}}
lassign [$sink_inst getLocation] sx sy
set victim {{}}
set best 2147483647
foreach inst [$block getInsts] {{
 if {{[[$inst getMaster] getName] ne {{sky130_fd_sc_hs__fill_2}}}} {{continue}}
 lassign [$inst getLocation] x y
 set distance [expr {{abs($x-$sx)+abs($y-$sy)}}]
 if {{$distance < $best}} {{set victim $inst;set best $distance}}
}}
if {{$victim eq {{}} || $best>20000}} {{error "no local same-footprint filler within 20um"}}
set orient [$victim getOrient]
lassign [$victim getLocation] x y
set box [$victim getBBox]
set old_box [list [$box xMin] [$box yMin] [$box xMax] [$box yMax]]
puts "LOCAL_DIODE_REPLACEMENT filler=[$victim getName] location=$x,$y distance_dbu=$best sink=[$sink_inst getName]"
global_route -start_incremental
odb::dbInst_destroy $victim
set diode [odb::dbInst_create $block [[ord::get_db] findMaster sky130_fd_sc_hs__diode_2] prototype_dlf8_local_diode]
$diode setOrient $orient
$diode setLocation $x $y
$diode setPlacementStatus PLACED
set box [$diode getBBox]
if {{[list [$box xMin] [$box yMin] [$box xMax] [$box yMax]] ne $old_box}} {{error "diode footprint differs"}}
[$diode findITerm DIODE] connect $target
foreach pin {{VPWR VPB}} {{[$diode findITerm $pin] connect [$block findNet VDD]}}
foreach pin {{VGND VNB}} {{[$diode findITerm $pin] connect [$block findNet VSS]}}
if {{[$target getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$target getWire]}}
write_db {out}/mutated.odb
global_route -end_incremental
if {{[$target getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$target getWire]}}
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
