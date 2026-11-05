#!/usr/bin/env python3
"""Incremental repair of measured preset loading and actual routed antennas.

Uses one detailed-route antenna iteration, preserving routed geometry until
the router updates affected nets. Fresh equivalence/layout/loaded STA required.
"""
import argparse
from collections import Counter
import json
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
    assert audit['antenna_net_violations'] > 0
    assert diode['cell'] == DIODE and diode['native_model_equivalence_revalidated']
    aux = load/'antenna_diode_load.lib'
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
set inst [$block findInst place165]
if {{$inst eq {{NULL}} || [[$inst getMaster] getName] ne {{sky130_fd_sc_hs__clkbuf_8}}}} {{error "unexpected preset driver"}}
global_route -start_incremental
# Keep the existing placement stable while legalizing the one larger driver.
set saved_status {{}}
foreach other [$block getInsts] {{
 if {{$other ne $inst && ![$other isFixed]}} {{
  lappend saved_status [list $other [$other getPlacementStatus]]
  $other setPlacementStatus FIRM
 }}
}}
replace_cell place165 sky130_fd_sc_hs__clkbuf_16
detailed_placement
foreach item $saved_status {{lassign $item other status; $other setPlacementStatus $status}}
global_route -end_incremental
puts "PRESET_DRIVER_UPSIZE place165 clkbuf_8 clkbuf_16"
# Existing dbWires are essential: this selects DetailedRouting in the pinned
# repair implementation. Do not clear wires or run a fresh global route.
repair_antennas {DIODE} -iterations 1 -ratio_margin 10 -diode_only
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
    assert masters[DIODE] >= receipt['antenna_diodes']
    for path, digest in pins.items():
        assert sha(Path(path)) == digest, path
    save(out/'assessment.json', dict(input_sha256=pins,
        artifacts={str(p): sha(p) for p in out.iterdir() if p.is_file()}, master_counts=dict(masters),
        functional_cell_types=len(set(masters)-PHYSICAL-{DIODE}), passive_auxiliary_types=[DIODE],
        antenna_diodes=masters[DIODE], conditional_diode_load_model=str(load/'assessment.json'),
        restricted_master_inventory_passed=True, nominal_signal_rc_extracted=True,
        adopted=False, physical_timing_qualified=False, release_qualified=False, scope=__doc__))


if __name__ == '__main__':
    main()
