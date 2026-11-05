#!/usr/bin/env python3
"""Build isolated compact routing/nominal RC artifacts; never claim signoff."""
import argparse
from collections import Counter
import json
from pathlib import Path

from check_compact_mapping import ALLOWED, LIB, TECH, LEF, OPENROAD, run
from check_compact_clock_tree import verify
from run_dco_qualification import sha, save

RC_MODEL=LIB.parents[3]/'libs.tech/librelane/rules.openrcx.sky130A.nom.magic'
PHYSICAL={'sky130_fd_sc_hs__'+n for n in ('tapvpwrvgnd_1','decap_4','fill_1','fill_2','fill_4','fill_8')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cts',required=True,type=Path)
    parser.add_argument('--equivalence',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();cts=args.cts.resolve();eqdir=args.equivalence.resolve()
    receipt=verify(cts/'assessment.json');eq=verify(eqdir/'assessment.json')
    assert receipt['restricted_master_inventory_passed']
    assert eq['all_transition_and_output_functions_equivalent'] and eq['corrupted_reset_function_rejected']
    assert eq['input_sha256'][str(cts/'cts.v')]==sha(cts/'cts.v')
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__).resolve(),Path(__file__).with_name('check_compact_clock_tree.py').resolve(),
           Path(__file__).with_name('check_compact_mapping.py').resolve(),Path(OPENROAD),LIB,TECH,LEF,RC_MODEL,
           cts/'cts.odb',cts/'cts.tcl',cts/'assessment.json',eqdir/'assessment.json']
    pins={str(p):sha(p) for p in files}
    constraints=(cts/'cts.tcl').read_text().split('create_clock -name REFCLK',1)[1].split('set_thread_count')[0]
    constraints='create_clock -name REFCLK'+constraints
    task=out/'route.tcl'
    task.write_text(f'''read_lef {TECH}
read_lef {LEF}
read_liberty {LIB}
read_db {cts}/cts.odb
{constraints}
set_thread_count 4
set_propagated_clock [all_clocks]
set_wire_rc -signal -layer met2
set_wire_rc -clock -layer met3
tapcell -tapcell_master sky130_fd_sc_hs__tapvpwrvgnd_1 -endcap_master sky130_fd_sc_hs__decap_4 -distance 10
detailed_placement
filler_placement {{sky130_fd_sc_hs__fill_8 sky130_fd_sc_hs__fill_4 sky130_fd_sc_hs__fill_2 sky130_fd_sc_hs__fill_1}}
check_placement -verbose
add_global_connection -net VDD -inst_pattern {{.*}} -pin_pattern {{^(VPWR|VPB)$}} -power
add_global_connection -net VSS -inst_pattern {{.*}} -pin_pattern {{^(VGND|VNB)$}} -ground
global_connect
set_voltage_domain -name CORE -power VDD -ground VSS
define_pdn_grid -name core_grid -voltage_domains CORE -pins {{met4 met5}}
add_pdn_ring -grid core_grid -layers {{met4 met5}} -widths 2 -spacings 2 -core_offsets 2
add_pdn_stripe -grid core_grid -layer met1 -width 0.48 -followpins -extend_to_core_ring
add_pdn_stripe -grid core_grid -layer met4 -width 2 -pitch 40 -offset 10 -extend_to_core_ring
add_pdn_stripe -grid core_grid -layer met5 -width 2 -pitch 40 -offset 10 -extend_to_core_ring
add_pdn_connect -grid core_grid -layers {{met1 met4}}
add_pdn_connect -grid core_grid -layers {{met4 met5}}
pdngen -failed_via_report {out}/pdn_failed_vias.rpt
set block [ord::get_db_block]
set total 0
set connected 0
foreach inst [$block getInsts] {{
 foreach term [$inst getITerms] {{
  if {{[$term getSigType] in {{POWER GROUND}}}} {{
   incr total
   if {{[$term getNet] ne {{NULL}}}} {{incr connected}}
  }}
 }}
}}
puts "POWER_PIN_AUDIT total=$total connected=$connected"
if {{$connected != $total}} {{error "unconnected power pins"}}
write_db {out}/pdn.odb
check_power_grid -net VDD -error_file {out}/vdd_errors.rpt
check_power_grid -net VSS -error_file {out}/vss_errors.rpt
set_routing_layers -signal met1-met5 -clock met3-met5
set_global_routing_layer_adjustment met2 0.5
set_global_routing_layer_adjustment met3 0.5
global_route -verbose -guide_file {out}/route.guide -congestion_iterations 100
estimate_parasitics -global_routing
report_checks -path_delay max -group_path_count 1 -digits 6
report_checks -path_delay min -group_path_count 1 -digits 6
write_db {out}/global_route.odb
detailed_route -output_drc {out}/route.drc -output_maze {out}/route.maze.log -output_guide_coverage {out}/route.coverage
write_db {out}/route.odb
write_def {out}/route.def
write_verilog {out}/route.v
define_process_corner -ext_model_index 0 RCX_NOM
extract_parasitics -ext_model_file {RC_MODEL} -corner 0
write_spef {out}/route.nom.spef
set inventory [open {out}/masters.txt w]
foreach inst [$block getInsts] {{puts $inventory [[$inst getMaster] getName]}}
close $inventory
exit
''')
    code=run([OPENROAD,'-exit',task],out/'route.log')
    log=(out/'route.log').read_text()
    assert code==0 and 'Error:' not in log,log[-2500:]
    masters=Counter((out/'masters.txt').read_text().splitlines())
    assert set(masters)<=ALLOWED|PHYSICAL,set(masters)-(ALLOWED|PHYSICAL)
    for path,digest in pins.items():assert sha(Path(path))==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        master_counts=dict(masters),functional_cell_types=len(set(masters)-PHYSICAL),
        restricted_master_inventory_passed=True,nominal_signal_rc_extracted=True,
        adopted=False,physical_timing_qualified=False,release_qualified=False,
        scope='Isolated compact routing and nominal RC. Router DRC, connectivity, independent layout LVS/DRC/antenna, min/maxRC and nominal15PVT timing still require explicit assessment.'))


if __name__=='__main__':main()
