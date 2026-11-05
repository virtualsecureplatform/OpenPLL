#!/usr/bin/env python3
"""Repair measured local antenna and diode-loaded electrical failures.

No release adoption. Independent layout, logic and actual loaded timing must
be checked afterwards, including the diode load model's stated limitations.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

from check_compact_clock_tree import verify
from check_compact_mapping import ALLOWED,LIB,TECH,LEF,OPENROAD,run
from route_compact_candidate import PHYSICAL,RC_MODEL
from run_dco_qualification import ROOT,sha,save

DIODE='sky130_fd_sc_hs__diode_2'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('route','cts','equivalence','diode-model','output'):
        parser.add_argument('--'+key,required=True,type=Path)
    args=parser.parse_args();source=args.route.resolve();cts=args.cts.resolve();eqdir=args.equivalence.resolve()
    load=args.diode_model.resolve();out=args.output.resolve()
    receipt=verify(source/'assessment.json');eq=verify(eqdir/'assessment.json');diode=verify(load/'assessment.json')
    assert eq['all_transition_and_output_functions_equivalent'] and eq['corrupted_reset_function_rejected']
    assert eq['input_sha256'][str(source/'route.v')]==sha(source/'route.v')
    assert receipt['input_sha256'][str(cts/'cts.tcl')]==sha(cts/'cts.tcl')
    assert diode['cell']==DIODE and diode['native_model_equivalence_revalidated']
    assert 0<diode['input_capacitance_upper_pf']<.01
    audit_path=source/'signoff/assessment.json';audit=json.loads(audit_path.read_text())
    assert audit['lvs_unique_match'] and audit['magic_drc_rectangles']==0
    assert audit['power_pins_total']==audit['power_pins_connected']
    assert audit['antenna_net_violations']>0
    report=source/'signoff/antenna.rpt'
    assert audit['sha256'][str(report)]==sha(report)
    nets=re.findall(r'^Net: (\S+)\s*$',report.read_text(),re.M)
    assert len(set(nets))==len(nets)==audit['antenna_net_violations']
    assert not any(c in ''.join(nets) for c in '{}\n')
    out.mkdir(parents=True,exist_ok=False)
    aux=load/'antenna_diode_load.lib'
    files=[Path(__file__).resolve(),Path(__file__).with_name('check_compact_mapping.py').resolve(),
           Path(__file__).with_name('check_compact_clock_tree.py').resolve(),Path(OPENROAD),LIB,TECH,LEF,RC_MODEL,
           source/'assessment.json',source/'route.odb',source/'route.v',cts/'cts.tcl',eqdir/'assessment.json',
           load/'assessment.json',aux,audit_path,report]
    pins={str(p):sha(p) for p in files}
    strongest={}
    for master in ALLOWED:
        family,strength=master.rsplit('_',1)
        if family not in strongest or int(strength)>int(strongest[family].rsplit('_',1)[1]):strongest[family]=master
    constraints=(cts/'cts.tcl').read_text().split('create_clock -name REFCLK',1)[1].split('set_thread_count')[0]
    constraints='create_clock -name REFCLK'+constraints
    script=f'''read_lef {TECH}
read_lef {LEF}
read_liberty {LIB}
read_liberty {aux}
read_db {source}/route.odb
{constraints}
set_clock_transition 0.1 [all_clocks]
set_clock_uncertainty 0.15 [all_clocks]
set_thread_count 4
set_propagated_clock [all_clocks]
set_wire_rc -signal -layer met2
set_wire_rc -clock -layer met3
remove_fillers
set block [ord::get_db_block]
set strongest [dict create {' '.join(k+' '+v for k,v in sorted(strongest.items()))}]
foreach name {{{' '.join(nets)}}} {{
 set net [$block findNet $name]
 if {{$net eq {{NULL}}}} {{error "missing antenna net $name"}}
 set drivers {{}}
 foreach term [$net getITerms] {{if {{[$term getIoType] eq {{OUTPUT}}}} {{lappend drivers $term}}}}
 if {{[llength $drivers] == 0}} {{continue}}
 if {{[llength $drivers] != 1}} {{error "antenna net has multiple drivers"}}
 set inst [[lindex $drivers 0] getInst]
 set old [[$inst getMaster] getName]
 if {{![regexp {{^(sky130_fd_sc_hs__[a-z0-9]+)_([0-9]+)$}} $old -> family strength]}} {{error "unknown antenna driver"}}
 if {{![dict exists $strongest $family]}} {{error "antenna driver outside allowed set"}}
 set new [dict get $strongest $family]
 if {{$old ne $new}} {{replace_cell [$inst getName] $new;puts "ANTENNA_DRIVER_UPSIZE name=[$inst getName] old=$old new=$new"}}
}}
# Minimum-size FF D gate area is unchanged by output-strength sizing.
# Isolate each observed long met1 attachment with a short local D branch.
set leaf_index 0
foreach name {{$auto$ff.cc:337:slice$16940 $auto$ff.cc:337:slice$16941 $auto$ff.cc:337:slice$16951}} {{
 set inst [$block findInst $name]
 if {{$inst eq {{NULL}} || [[$inst getMaster] getName] ne {{sky130_fd_sc_hs__dfstp_1}}}} {{error "unexpected antenna sink"}}
 set sink [$inst findITerm D]
 set source [$sink getNet]
 set leaf_name antenna_d_leaf_$leaf_index
 if {{[$block findInst $leaf_name] ne {{NULL}}}} {{error "antenna leaf already exists"}}
 set leaf [odb::dbInst_create $block [[ord::get_db] findMaster sky130_fd_sc_hs__buf_8] $leaf_name]
 set output [odb::dbNet_create $block ${{leaf_name}}_out]
 [$leaf findITerm A] connect $source
 [$leaf findITerm X] connect $output
 $sink disconnect
 $sink connect $output
 lassign [$inst getLocation] x y
 $leaf setLocation $x $y
 $leaf setPlacementStatus PLACED
 puts "LOCAL_ANTENNA_D_BUFFER sink=$name buffer=$leaf_name"
 incr leaf_index
}}
# Loaded min/max RC reports identify this a21oi_1 driving clkinv_16.
set name {{$abc$125536$auto$blifparse.cc:397:parse_blif$126150}}
set inst [$block findInst $name]
if {{$inst eq {{NULL}} || [[$inst getMaster] getName] ne {{sky130_fd_sc_hs__a21oi_1}}}} {{error "unexpected loaded driver"}}
replace_cell $name sky130_fd_sc_hs__a21oi_4
puts "DIODE_LOADED_DRIVER_UPSIZE $name"
detailed_placement
foreach net [$block getNets] {{if {{[$net getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$net getWire]}}}}
set_routing_layers -signal met1-met5 -clock met3-met5
set_global_routing_layer_adjustment met2 0.5
set_global_routing_layer_adjustment met3 0.5
global_route -verbose -guide_file {out}/route.guide -congestion_iterations 100
repair_antennas {DIODE} -iterations 5 -ratio_margin 10 -diode_only
filler_placement {{sky130_fd_sc_hs__fill_8 sky130_fd_sc_hs__fill_4 sky130_fd_sc_hs__fill_2 sky130_fd_sc_hs__fill_1}}
unset_dont_touch [get_cells external_reset_leaf_*]
global_connect
set_dont_touch [get_cells external_reset_leaf_*]
set pg_total 0
set pg_connected 0
foreach inst [$block getInsts] {{
 foreach term [$inst getITerms] {{
  if {{[$term getSigType] in {{POWER GROUND}}}} {{
   incr pg_total
   if {{[$term getNet] ne {{NULL}}}} {{incr pg_connected}}
  }}
 }}
}}
puts "POWER_PIN_AUDIT total=$pg_total connected=$pg_connected"
if {{$pg_total != $pg_connected}} {{error "unconnected PG after diode insertion"}}
check_placement -verbose
estimate_parasitics -global_routing
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
foreach inst [$block getInsts] {{puts $inventory [[$inst getMaster] getName]}}
close $inventory
exit
'''
    task=out/'antenna.tcl';task.write_text(script)
    code=run([OPENROAD,'-exit',task],out/'antenna.log')
    log=(out/'antenna.log').read_text();assert code==0 and 'Error:' not in log,log[-2500:]
    masters=Counter((out/'masters.txt').read_text().splitlines())
    assert set(masters)<=ALLOWED|PHYSICAL|{DIODE},set(masters)-(ALLOWED|PHYSICAL|{DIODE})
    assert masters[DIODE]>0
    for path,digest in pins.items():assert sha(Path(path))==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},master_counts=dict(masters),
        functional_cell_types=len(set(masters)-PHYSICAL-{DIODE}),passive_auxiliary_types=[DIODE],
        antenna_diodes=masters[DIODE],conditional_diode_load_model=str(load/'assessment.json'),
        restricted_master_inventory_passed=True,nominal_signal_rc_extracted=True,
        adopted=False,physical_timing_qualified=False,release_qualified=False,scope=__doc__))


if __name__=='__main__':main()
