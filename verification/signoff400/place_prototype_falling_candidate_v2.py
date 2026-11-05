#!/usr/bin/env python3
"""Build placed prototype digital logic with explicitly diagnostic TT timing."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge import execute
import os
import time
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import LIB, LEF, TECH, OPENROAD, ALLOWED


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mapping',required=True,type=Path)
    p.add_argument('--proof',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();mapping=a.mapping.resolve();proof=a.proof.resolve()
    receipt=json.loads((mapping/'assessment.json').read_text());verify(receipt['input_sha256']);verify(receipt['artifacts'])
    checked=json.loads((proof/'assessment.json').read_text());verify(checked['input_sha256']);verify(checked['artifacts'])
    assert checked['all_transition_clock_reset_and_output_functions_equivalent']
    assert checked['corrupted_data_function_rejected']
    assert checked['input_sha256'][str(mapping/'mapped.json')]==sha(mapping/'mapped.json')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    candidate_sources=receipt['candidate_source_sha256'];verify(candidate_sources)
    pins=dict(candidate_sources)
    for path in (Path(__file__).resolve(),Path(OPENROAD),LIB,LEF,TECH,mapping/'mapped.v',mapping/'assessment.json',proof/'assessment.json'):
        pins[str(path)]=sha(path)
    save(out/'owner.json',dict(started_utc=datetime.now(timezone.utc).isoformat(),wall_limit_s=43200))
    m=json.loads((mapping/'mapped.json').read_text())['modules']['IntegerPLL_ProgrammedCore']
    drivers=[name for name,cell in m['cells'].items() if cell['connections'].get('Q')==m['ports']['CLKDIV_RETIMED']['bits']]
    assert len(drivers)==1,drivers
    feedback_master='sky130_fd_sc_hs__dfrtp_4'
    if m['cells'][drivers[0]]['type'] not in ('sky130_fd_sc_hs__dfrtp_1','sky130_fd_sc_hs__dfrtp_2','sky130_fd_sc_hs__dfrtp_4'):raise ValueError('unexpected feedback clock register family')
    clocks=f'''create_clock -name REFCLK -period 40 [get_ports REFCLK]
# 500 MHz is a capacity screen, pending measured startup/tracking bounds.
create_clock -name PLLOUT -period 2.0 [get_ports PLLOUT]
create_generated_clock -name FINECLK -source [get_ports PLLOUT] -divide_by 16 [get_pins {{{drivers[0]}/Q}}]
set_clock_transition 0.1 [all_clocks]
set_clock_uncertainty 0.15 [all_clocks]
set_input_delay 0.5 -clock REFCLK [get_ports {{STARTUP_COARSE* STARTUP_FINE* STARTUP_INCREASING PLL_ENABLE KI* KP*}}]
set_output_delay 0.5 -clock FINECLK [get_ports {{DCO_CODE* DLF_CODE* DCO_THERM*}}]
set_output_delay 0.5 -clock REFCLK [get_ports {{COARSE_CODE* COARSETHERMAL_CODE* OSC_RESET_N CONFIG_READY CONFIG_BUSY FAILED}}]
set_output_delay 0.5 -clock FINECLK [get_ports {{TRACKING BBPD_RESET_N}}]
set_output_delay 0.5 -clock PLLOUT [get_ports CLKDIV_RETIMED]
set_load 0.005 [all_outputs]
# Reset/CDC are excluded only from this capacity screen, and remain open gates.
set_false_path -from [get_ports RESET_N]
foreach port [get_ports *] {{
 if {{[string range [get_full_name $port] 0 4] eq {{BBPD[}}}} {{
  create_clock -name EVENT_[get_full_name $port] -period 40 -waveform {{0 1}} $port
 }}
}}
# Keep PLLOUT/FINECLK related paths visible. Remaining asynchronous
# groups are capacity-screen exceptions, not qualification constraints.
foreach left [all_clocks] {{foreach right [all_clocks] {{
 set a [get_full_name $left]
 set b [get_full_name $right]
 if {{$a ne $b && !(($a eq "PLLOUT" && $b eq "FINECLK") || ($a eq "FINECLK" && $b eq "PLLOUT"))}} {{set_false_path -from $left -to $right}}
}}}}
'''
    (out/'diagnostic.sdc').write_text(clocks)
    script=f'''read_lef {TECH}
read_lef {LEF}
read_liberty {LIB}
read_verilog {mapping}/mapped.v
link_design IntegerPLL_ProgrammedCore
replace_cell {{{drivers[0]}}} {feedback_master}
initialize_floorplan -utilization 35 -aspect_ratio 1 -core_space 10 -site unit
source {out}/diagnostic.sdc
set_thread_count 4
set_wire_rc -signal -layer met2
set_wire_rc -clock -layer met3
set_placement_padding -global -left 1 -right 1
make_tracks
place_pins -hor_layers met3 -ver_layers met4
global_placement -timing_driven -density 0.55
estimate_parasitics -placement
repair_design
replace_cell {{{drivers[0]}}} {feedback_master}
detailed_placement
estimate_parasitics -placement
check_placement -verbose
report_checks -path_delay max -group_path_count 3 -digits 6
report_checks -path_delay min -group_path_count 3 -digits 6
report_check_types -max_slew -max_capacitance -min_pulse_width
check_setup -verbose
write_db {out}/placed.odb
write_verilog {out}/placed.v
exit
'''
    task=out/'placement.tcl';task.write_text(script)
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    with lease(4,4,deadline):execute([OPENROAD,'-exit',task],out/'placement.log',deadline,4)
    code=0
    log=(out/'placement.log').read_text()
    assert code==0 and 'Error:' not in log,log[-3000:]
    verify(pins)
    save(out/'assessment.json',dict(input_sha256=pins,
         artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
         candidate_source_sha256=candidate_sources,feedback_driver_master=feedback_master,related_fast_and_divided_clock_paths_preserved=True,placement_completed=True,screen_clock_mhz=500,library_temperature_c=25,
         actual_parent_loads_applied=False,physical_timing_qualified=False,
         reset_cdc_qualified=False,prototype_handoff_qualified=False,
         scope='Falling-edge candidate placement and supplied-TT capacity only; asynchronous/reset exceptions remain diagnostic.'))
    print('Completed prototype placement capacity screen; physical timing remains open')


if __name__=='__main__':main()
