#!/usr/bin/env python3
"""Clock-tree, routing and extracted-RC build of prototype digital logic."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import subprocess
import sys
from common_v3 import ROOT,save,sha,verify
import os
import time
from resources import lease
from compiled_charge import execute
sys.path.insert(0,str(ROOT/'verification/prototype400'))
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import LIB,LEF,TECH,OPENROAD,ALLOWED
from route_compact_candidate import PHYSICAL,RC_MODEL


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--placement',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();placed=a.placement.resolve();out=a.output.resolve()
    receipt=json.loads((placed/'assessment.json').read_text())
    verify(receipt['input_sha256']);verify(receipt['artifacts'])
    assert receipt['placement_completed']
    if not receipt.get('related_fast_and_divided_clock_paths_preserved'):raise ValueError('related clock paths must remain visible')
    verify(receipt['candidate_source_sha256'])
    out.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__).resolve(),Path(OPENROAD),LIB,LEF,TECH,RC_MODEL,
           placed/'assessment.json',placed/'placed.odb',placed/'diagnostic.sdc']
    pins={str(path):sha(path) for path in files}
    save(out/'owner.json',dict(started_utc=datetime.now(timezone.utc).isoformat(),wall_limit_s=43200))
    excluded=set(re.findall(r'cell\s*\(\s*"?([^\s"\)]+)',LIB.read_text()))-ALLOWED
    script=f"""read_lef {TECH}
read_lef {LEF}
read_liberty {LIB}
read_db {placed}/placed.odb
source {placed}/diagnostic.sdc
set_thread_count 4
set_dont_use [get_lib_cells {{{' '.join(sorted(excluded))}}}]
set_wire_rc -signal -layer met2
set_wire_rc -clock -layer met3
repair_tie_fanout -separation 0 sky130_fd_sc_hs__conb_1/HI
repair_tie_fanout -separation 0 sky130_fd_sc_hs__conb_1/LO
clock_tree_synthesis -root_buf sky130_fd_sc_hs__clkbuf_16 -buf_list {{sky130_fd_sc_hs__clkbuf_2 sky130_fd_sc_hs__clkbuf_4 sky130_fd_sc_hs__clkbuf_8 sky130_fd_sc_hs__clkbuf_16}} -sink_clustering_enable -sink_clustering_size 8 -sink_clustering_max_diameter 30
detailed_placement
set_propagated_clock [all_clocks]
estimate_parasitics -placement
repair_design
estimate_parasitics -placement
repair_timing -setup -setup_margin 0.10 -max_iterations 100
repair_timing -hold -hold_margin 0.05 -max_iterations 100
# Resizing may introduce fresh constant nets after the original tie mapping.
set block [ord::get_db_block]
foreach {{name pin}} {{zero_ LO one_ HI}} {{
 set net [$block findNet $name]
 if {{$net eq {{NULL}}}} {{continue}}
 set terms [$net getITerms]
 if {{[llength $terms]==0 && [llength [$net getBTerms]]==0}} {{
  odb::dbNet_destroy $net
  continue
 }}
 set driver 0
 foreach term $terms {{if {{[$term getIoType] eq {{OUTPUT}}}} {{incr driver}}}}
 if {{$driver==0}} {{
  set master [[ord::get_db] findMaster sky130_fd_sc_hs__conb_1]
  set inst [odb::dbInst_create $block $master prototype_constant_$pin]
  $inst setLocation {{*}}[[[lindex $terms 0] getInst] getLocation]
  $inst setPlacementStatus PLACED
  [$inst findITerm $pin] connect $net
 }}
 $net setSigType SIGNAL
}}
repair_tie_fanout -separation 0 sky130_fd_sc_hs__conb_1/HI
repair_tie_fanout -separation 0 sky130_fd_sc_hs__conb_1/LO
detailed_placement
check_placement -verbose
write_db {out}/cts.odb
write_verilog {out}/cts.v
tapcell -tapcell_master sky130_fd_sc_hs__tapvpwrvgnd_1 -endcap_master sky130_fd_sc_hs__decap_4 -distance 10
detailed_placement
filler_placement {{sky130_fd_sc_hs__fill_8 sky130_fd_sc_hs__fill_4 sky130_fd_sc_hs__fill_2 sky130_fd_sc_hs__fill_1}}
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
check_power_grid -net VDD -error_file {out}/vdd_errors.rpt
check_power_grid -net VSS -error_file {out}/vss_errors.rpt
set_routing_layers -signal met1-met5 -clock met3-met5
set_global_routing_layer_adjustment met2 0.5
set_global_routing_layer_adjustment met3 0.5
global_route -verbose -guide_file {out}/route.guide -congestion_iterations 100
write_db {out}/global_route.odb
detailed_route -output_drc {out}/route.drc -output_maze {out}/route.maze.log -output_guide_coverage {out}/route.coverage
write_db {out}/route.odb
write_def {out}/route.def
write_verilog {out}/route.v
write_verilog -include_pwr_gnd {out}/powered.v
write_abstract_lef {out}/digital.lef
define_process_corner -ext_model_index 0 RCX_NOM
extract_parasitics -ext_model_file {RC_MODEL} -corner 0
write_spef {out}/route.nom.spef
report_checks -path_delay max -group_path_count 3 -digits 6
report_checks -path_delay min -group_path_count 3 -digits 6
report_check_types -max_slew -max_capacitance -min_pulse_width
set inventory [open {out}/masters.txt w]
foreach inst [[ord::get_db_block] getInsts] {{puts $inventory [[$inst getMaster] getName]}}
close $inventory
exit
"""
    task=out/'route.tcl';task.write_text(script)
    save(out/'status.json',dict(state='native_physical_build_running',physical_timing_qualified=False))
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='4',OMP_THREAD_LIMIT='4',OPENBLAS_NUM_THREADS='1')
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    try:
        with lease(4,4,deadline):execute([OPENROAD,'-exit',str(task)],out/'route.log',deadline,4)
    except BaseException as exc:
        save(out/'status.json',dict(state='physical_build_nonpass',reason=repr(exc),physical_timing_qualified=False))
        raise
    code=0
    text=(out/'route.log').read_text()
    if code or 'Error:' in text:
        save(out/'status.json',dict(state='physical_build_nonpass',native_exit=code,physical_timing_qualified=False))
        raise RuntimeError(text[-3000:])
    counts=Counter((out/'masters.txt').read_text().splitlines())
    assert set(counts)<=ALLOWED|PHYSICAL,set(counts)-(ALLOWED|PHYSICAL)
    verify(pins)
    save(out/'assessment.json',dict(input_sha256=pins,
         artifacts={str(path):sha(path) for path in out.iterdir() if path.is_file() and path.name!='status.json'},
         candidate_source_sha256=receipt['candidate_source_sha256'],
         related_fast_and_divided_clock_paths_preserved=True,
         cell_inventory=dict(counts),digital_routing_completed=True,nominal_rc_extracted=True,
         physical_timing_qualified=False,assembled_macro_qualified=False,
         prototype_handoff_qualified=False))
    save(out/'status.json',dict(state='digital_route_completed_pending_independent_checks',physical_timing_qualified=False))
    print('Digital route and nominal RC completed; independent checks remain open')


if __name__=='__main__':main()
