#!/usr/bin/env python3
"""Incremental repair of actual routed slew/capacitance failures.

Selects the next larger allowed driver or isolates strongest complex gates, preserving
other placements/routes and adding no diodes. Fresh logic/layout/STA required.
"""
import argparse
from collections import Counter
import json
import re
from pathlib import Path

from check_compact_clock_tree import verify
from check_compact_mapping import ALLOWED, LIB, TECH, LEF, OPENROAD, run
from route_compact_candidate import PHYSICAL, RC_MODEL
from run_dco_qualification import ROOT, sha, save

DIODE = 'sky130_fd_sc_hs__diode_2'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('route', 'cts', 'equivalence', 'timing', 'diode-model', 'output'):
        parser.add_argument('--'+key, required=True, type=Path)
    args = parser.parse_args()
    source, cts, eqdir = args.route.resolve(), args.cts.resolve(), args.equivalence.resolve()
    timing, load, out = args.timing.resolve(), args.diode_model.resolve(), args.output.resolve()
    receipt = verify(source/'assessment.json')
    eq, sta, diode = verify(eqdir/'assessment.json'), verify(timing/'assessment.json'), verify(load/'assessment.json')
    assert eq['all_transition_and_output_functions_equivalent'] and eq['corrupted_reset_function_rejected']
    assert eq['input_sha256'][str(source/'route.v')] == sha(source/'route.v')
    assert sta['input_sha256'][str(source/'route.odb')] == sha(source/'route.odb')
    assert receipt['input_sha256'][str(cts/'cts.tcl')] == sha(cts/'cts.tcl')
    audit_path = source/'signoff/assessment.json'
    audit = json.loads(audit_path.read_text())
    assert audit['lvs_unique_match'] and audit['magic_drc_rectangles'] == 0
    assert audit['power_pins_connected'] == audit['power_pins_total']
    assert audit['antenna_net_violations'] == 0
    assert diode['cell'] == DIODE and diode['native_model_equivalence_revalidated']
    violations = sorted({line.split()[0] for result in sta['results'].values()
                         for line in result['reported_constraint_violations']})
    assert violations, 'requires measured violations'
    assert not any(c in ''.join(violations) for c in '{}\n')
    pairs = ['{'+name.rsplit('/',1)[0]+' '+name.rsplit('/',1)[1]+'}' for name in violations]
    size_choices = {}
    for master in ALLOWED:
        family = master.rsplit('_',1)[0]
        size_choices.setdefault(family,[]).append(master)
    for choices in size_choices.values():
        choices.sort(key=lambda name:int(name.rsplit('_',1)[1]))
    aux = load/'antenna_diode_load.lib'
    assert re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',out.name), 'output basename must be a Tcl-safe identifier'
    out.mkdir(parents=True, exist_ok=False)
    evidence = ROOT/'build/timing400/release_001/postroute_antenna_source_audit_001'
    files = [Path(__file__).resolve(), Path(__file__).with_name('check_compact_mapping.py').resolve(),
             Path(__file__).with_name('check_compact_clock_tree.py').resolve(), Path(OPENROAD),
             LIB, TECH, LEF, RC_MODEL, source/'assessment.json', source/'route.odb', source/'route.v',
             cts/'cts.tcl', eqdir/'assessment.json', timing/'assessment.json', load/'assessment.json', aux,
             audit_path, evidence/'assessment.json', evidence/'GlobalRouter.cpp', evidence/'RepairAntennas.cpp']
    pins = {str(p): sha(p) for p in files}
    constraints = (cts/'cts.tcl').read_text().split('create_clock -name REFCLK', 1)[1].split('set_thread_count')[0]
    constraints = 'create_clock -name REFCLK'+constraints
    script = f'''read_lef {TECH}
read_lef {LEF}
read_liberty {LIB}
read_liberty {aux}
read_db {source}/route.odb
{constraints}
set_clock_transition 0.1 [all_clocks]
set_clock_uncertainty 0.15 [all_clocks]
set_propagated_clock [all_clocks]
set_thread_count 4
set_wire_rc -signal -layer met2
set_wire_rc -clock -layer met3
set_routing_layers -signal met1-met5 -clock met3-met5
set_global_routing_layer_adjustment met2 0.5
set_global_routing_layer_adjustment met3 0.5
remove_fillers
set block [ord::get_db_block]
global_route -start_incremental
set targets [dict create]
foreach pair {{{' '.join(pairs)}}} {{
 lassign $pair name pin
 set cell [$block findInst $name]
 if {{$cell eq {{NULL}}}} {{error "missing electrical instance $name"}}
 set term [$cell findITerm $pin]
 if {{$term eq {{NULL}} || [$term getNet] eq {{NULL}}}} {{error "missing electrical pin $name/$pin"}}
 set net [$term getNet]
 dict set targets [$net getName] $net
}}
set size_choices [dict create {' '.join(k+' {'+' '.join(v)+'}' for k,v in sorted(size_choices.items()))}]
set movable [dict create]
set root_index 0
foreach name [lsort [dict keys $targets]] {{
 set net [dict get $targets $name]
 set drivers {{}}
 foreach term [$net getITerms] {{if {{[$term getIoType] eq {{OUTPUT}}}} {{lappend drivers $term}}}}
 if {{[llength $drivers] != 1}} {{error "expected one driver for $name"}}
 set output [lindex $drivers 0]
 set cell [$output getInst]
 set old [[$cell getMaster] getName]
 if {{![regexp {{^(sky130_fd_sc_hs__[a-z0-9]+)_([0-9]+)$}} $old -> family strength] || ![dict exists $size_choices $family]}} {{error "unexpected electrical driver"}}
 set new $old
 foreach candidate [dict get $size_choices $family] {{
  if {{[lindex [split $candidate _] end] > $strength}} {{set new $candidate;break}}
 }}
 if {{$old ne $new}} {{
  dict set movable $cell 1
  replace_cell [$cell getName] $new
  puts "MEASURED_DRIVER_UPSIZE net=$name old=$old new=$new"
 }} else {{
  if {{$family in {{sky130_fd_sc_hs__buf sky130_fd_sc_hs__clkbuf}}}} {{error "strongest buffer needs fanout partition: $name"}}
  set leaf_name electrical_${{root_index}}_{out.name}
  if {{[$block findInst $leaf_name] ne {{NULL}}}} {{error "buffer name collision"}}
  set leaf [odb::dbInst_create $block [[ord::get_db] findMaster sky130_fd_sc_hs__buf_16] $leaf_name]
  set input [odb::dbNet_create $block ${{leaf_name}}_input]
  $output disconnect
  $output connect $input
  [$leaf findITerm A] connect $input
  [$leaf findITerm X] connect $net
  lassign [$cell getLocation] x y
  $leaf setLocation $x $y
  $leaf setPlacementStatus PLACED
  dict set movable $leaf 1
  puts "MEASURED_DRIVER_ISOLATION net=$name driver=[$cell getName] buffer=$leaf_name"
  incr root_index
 }}
}}
set saved_status {{}}
foreach cell [$block getInsts] {{
 if {{![dict exists $movable $cell] && ![$cell isFixed]}} {{
  lappend saved_status [list $cell [$cell getPlacementStatus]]
  $cell setPlacementStatus FIRM
 }}
}}
detailed_placement
foreach item $saved_status {{lassign $item cell status; $cell setPlacementStatus $status}}
# Clear every detailed wire incident to the changed/moved cells. All other
# routed wires remain available to DRT. No antenna check is run on this mixed
# state, so no temporary guide wires can leak into detailed routing.
set dirty [dict create]
foreach cell [dict keys $movable] {{
 foreach term [$cell getITerms] {{
  set net [$term getNet]
  if {{$net ne {{NULL}} && [$term getSigType] ni {{POWER GROUND}}}} {{dict set dirty [$net getName] $net}}
 }}
}}
foreach name [dict keys $dirty] {{
 set net [dict get $dirty $name]
 if {{[$net getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$net getWire]}}
 puts "INVALIDATED_CHANGED_CELL_WIRE $name"
}}
global_route -end_incremental
filler_placement {{sky130_fd_sc_hs__fill_8 sky130_fd_sc_hs__fill_4 sky130_fd_sc_hs__fill_2 sky130_fd_sc_hs__fill_1}}
unset_dont_touch [get_cells external_reset_leaf_*]
global_connect
set_dont_touch [get_cells external_reset_leaf_*]
set pg_total 0
set pg_connected 0
foreach cell [$block getInsts] {{foreach term [$cell getITerms] {{
 if {{[$term getSigType] in {{POWER GROUND}}}} {{
  incr pg_total
  if {{[$term getNet] ne {{NULL}}}} {{incr pg_connected}}
 }}
}}}}
puts "POWER_PIN_AUDIT total=$pg_total connected=$pg_connected"
if {{$pg_total != $pg_connected}} {{error "unconnected power pin"}}
check_placement -verbose
write_db {out}/repaired_guides.odb
detailed_route -output_drc {out}/route.drc -output_maze {out}/route.maze.log -output_guide_coverage {out}/route.coverage
write_db {out}/route.odb
write_def {out}/route.def
write_verilog {out}/route.v
check_antennas -report_file {out}/antenna.rpt
define_process_corner -ext_model_index 0 RCX_NOM
extract_parasitics -ext_model_file {RC_MODEL} -corner 0
write_spef {out}/route.nom.spef
set inventory [open {out}/masters.txt w]
foreach cell [$block getInsts] {{puts $inventory [[$cell getMaster] getName]}}
close $inventory
exit
'''
    task = out/'repair.tcl'
    task.write_text(script)
    code = run([OPENROAD, '-exit', task], out/'repair.log')
    log = (out/'repair.log').read_text()
    assert code == 0 and 'Error:' not in log, log[-2500:]
    masters = Counter((out/'masters.txt').read_text().splitlines())
    assert set(masters) <= ALLOWED | PHYSICAL | {DIODE}
    assert masters[DIODE] == receipt['antenna_diodes']
    for path, digest in pins.items():
        assert sha(Path(path)) == digest, path
    save(out/'assessment.json', dict(input_sha256=pins,
        artifacts={str(p): sha(p) for p in out.iterdir() if p.is_file()}, master_counts=dict(masters),
        functional_cell_types=len(set(masters)-PHYSICAL-{DIODE}), passive_auxiliary_types=[DIODE],
        antenna_diodes=masters[DIODE], conditional_diode_load_model=str(load/'assessment.json'),
        restricted_master_inventory_passed=True, nominal_signal_rc_extracted=True,
        measured_violating_pins=violations,added_antenna_diodes=0,
        adopted=False, physical_timing_qualified=False, release_qualified=False, scope=__doc__))


if __name__ == '__main__':
    main()
