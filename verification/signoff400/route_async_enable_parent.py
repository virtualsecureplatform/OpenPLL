#!/usr/bin/env python3
"""Route measured parent antenna banks with exact original and added pin bindings."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from common_v3 import ROOT, save, sha, verify
from resources import lease,identity
from compiled_charge import execute
sys.path.insert(0,str(ROOT/'verification/prototype400'))
from build_assembly_frame import expected
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import OPENROAD


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--power',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();power=a.power.resolve();out=a.output.resolve()
    receipt=json.loads((power/'assessment.json').read_text())
    assert receipt['main_rail_database_connectivity_pass'];verify(receipt['input_sha256']);verify(receipt['artifacts'])
    out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    pins=dict(receipt['candidate_source_sha256'])
    for path in (Path(__file__).resolve(),ROOT/'verification/prototype400/build_assembly_frame.py',Path(OPENROAD),power/'assessment.json',power/'power.odb'):
        pins[str(path)]=sha(path)
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),started_utc=datetime.now(timezone.utc).isoformat(),wall_limit_s=43200,automatic_identical_retry=False))
    def run(label,text):
        verify(pins);script=out/(label+'.tcl');script.write_text(text)
        save(out/'status.json',dict(state='waiting_for_'+label+'_lease',release_qualified=False))
        with lease(4,16,deadline):
            save(out/'status.json',dict(state=label+'_running',release_qualified=False))
            execute([OPENROAD,'-no_init','-exit',script],out/(label+'.log'),deadline,16)
    try:
        run('global',f'''read_db {{{power/'power.odb'}}}
set_thread_count 4
foreach rail {{VPWR VGND}} {{
 [[ord::get_db_block] findNet $rail] setSpecial
 [[ord::get_db_block] findBTerm $rail] setSigType [[[ord::get_db_block] findNet $rail] getSigType]
}}
set pg_geometry [dict create]
foreach rail {{VPWR VGND}} {{
 set shapes [list]
 set term [[ord::get_db_block] findBTerm $rail]
 foreach pin [$term getBPins] {{
  foreach box [$pin getBoxes] {{
   lappend shapes [list [[$box getTechLayer] getName] [$box xMin] [$box yMin] [$box xMax] [$box yMax]]
  }}
 }}
 if {{[llength $shapes] == 0}} {{error "missing source PG pin geometry"}}
 dict set pg_geometry $rail $shapes
}}
make_tracks
place_pins -hor_layers met3 -ver_layers met2 -corner_avoidance 10 -min_distance 2 -write_pin_placement {{{out/'pin_placement.tcl'}}}
# IO placement also proposes PG pins; restore only the existing rail contacts.
foreach rail {{VPWR VGND}} {{
 set term [[ord::get_db_block] findBTerm $rail]
 foreach pin [$term getBPins] {{odb::dbBPin_destroy $pin}}
 set pin [odb::dbBPin_create $term]
 $pin setPlacementStatus FIRM
 foreach shape [dict get $pg_geometry $rail] {{
  lassign $shape layer x0 y0 x1 y1
  odb::dbBox_create $pin [[ord::get_db_tech] findLayer $layer] $x0 $y0 $x1 $y1
 }}
 set restored [list]
 foreach box [$pin getBoxes] {{lappend restored [list [[$box getTechLayer] getName] [$box xMin] [$box yMin] [$box xMax] [$box yMax]]}}
 if {{[lsort $restored] ne [lsort [dict get $pg_geometry $rail]]}} {{error "PG pin geometry changed"}}
}}
set_routing_layers -signal met1-met4 -clock met2-met4
set_macro_extension 0
global_route -guide_file {{{out/'route.guide'}}} -congestion_iterations 50 -congestion_report_file {{{out/'congestion.rpt'}}} -verbose
write_db {{{out/'guided.odb'}}}
write_def {{{out/'guided.def'}}}
''')
        run('detail',f'''read_db {{{out/'guided.odb'}}}
set_thread_count 4
read_guides {{{out/'route.guide'}}}
set_routing_layers -signal met1-met4 -clock met2-met4
detailed_route -output_drc {{{out/'route.drc'}}} -output_guide_coverage {{{out/'route.coverage'}}}
write_db {{{out/'route.odb'}}}
write_def {{{out/'route.def'}}}
write_verilog -include_pwr_gnd {{{out/'powered.v'}}}
set block [ord::get_db_block]
set f [open {{{out/'connections.tsv'}}} w]
foreach inst [$block getInsts] {{
 foreach pin [$inst getITerms] {{
  set net [$pin getNet]
  if {{$net == "NULL"}} {{error "unconnected macro pin"}}
  puts $f [join [list [$inst getName] [[$pin getMTerm] getName] [$net getName]] "\\t"]
 }}
}}
close $f
set f [open {{{out/'signal_wires.tsv'}}} w]
foreach net [$block getNets] {{
 if {{[$net getSigType] ni {{POWER GROUND}}}} {{
  if {{[$net getWire] == "NULL"}} {{error "signal missing detailed wire"}}
  puts $f [$net getName]
 }}
}}
close $f
check_power_grid -net VPWR -floorplanning -error_file {{{out/'VPWR_errors.rpt'}}}
check_power_grid -net VGND -floorplanning -error_file {{{out/'VGND_errors.rpt'}}}
''')
        log=(out/'detail.log').read_text(); counts=re.findall(r'Number of violations = (\d+)',log)
        assert counts and int(counts[-1])==0 and (out/'route.drc').stat().st_size==0
        assert 'Complete detail routing.' in log and '[ERROR' not in log
        assert all(f'All shapes on net {net} are connected.' in log for net in ('VPWR','VGND'))
        actual={}
        for line in (out/'connections.tsv').read_text().splitlines():
            inst,pin,net=line.split('\t');assert (inst,pin) not in actual;actual[inst,pin]=net
        wanted=expected()
        for inst,pin,net in receipt.get('parent_instance_bindings',[]):
            if (inst,pin) in wanted:raise ValueError('duplicate added bank pin')
            wanted[inst,pin]=net
        assert actual==wanted
        verify(pins)
        save(out/'assessment.json',dict(input_sha256=pins,candidate_source_sha256=receipt['candidate_source_sha256'],DCO_selection_provisional=True,release_ready=False,router_drc_violations=0,macro_pins_checked=len(actual),
             exact_macro_bindings_preserved=True,source_power_pin_rectangles_preserved=True,main_rail_database_connectivity_pass=True,
             signal_nets_routed=len((out/'signal_wires.tsv').read_text().splitlines()),
             assembled_drc_pass=False,assembled_lvs_pass=False,antenna_qualified=False,
             extraction_complete=False,prototype_handoff_qualified=False,release_qualified=False,
             artifacts={str(path):sha(path) for path in out.iterdir() if path.is_file() and path.name!='status.json'}))
        save(out/'status.json',dict(state='parent_route_pass_pending_assembled_checks',completed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False))
    except BaseException as e:
        save(out/'status.json',dict(state='failed',reason=str(e),observed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False));raise


if __name__=='__main__':main()
