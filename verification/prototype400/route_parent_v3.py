#!/usr/bin/env python3
"""Route the exact three-macro parent; retain every macro and PG connection."""
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
from common import ROOT, save, sha, source_pins, verify
from build_assembly_frame import expected
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import OPENROAD


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--power',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();power=a.power.resolve();out=a.output.resolve()
    receipt=json.loads((power/'assessment.json').read_text())
    assert receipt['main_rail_database_connectivity_pass'];verify(receipt['input_sha256']);verify(receipt['artifacts'])
    out.mkdir(parents=True,exist_ok=False);deadline=time.monotonic()+43200
    pins=source_pins()
    for path in (Path(__file__).resolve(),Path(__file__).with_name('build_assembly_frame.py'),Path(OPENROAD),power/'assessment.json',power/'power.odb'):
        pins[str(path)]=sha(path)
    save(out/'owner.json',dict(pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),wall_limit_s=43200,automatic_identical_retry=False))
    def run(label,text):
        verify(pins);script=out/(label+'.tcl');script.write_text(text)
        with (out/(label+'.log')).open('x') as log:
            child=subprocess.Popen([OPENROAD,'-no_init','-exit',str(script)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            save(out/'status.json',dict(state=label+'_running',native_pid=child.pid,observed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False))
            try:code=child.wait(timeout=max(.01,deadline-time.monotonic()))
            except BaseException:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                raise
            if code:raise RuntimeError((label,code,(out/(label+'.log')).read_text()[-2500:]))
    try:
        run('global',f'''read_db {{{power/'power.odb'}}}
set_thread_count 2
foreach rail {{VPWR VGND}} {{
 [[ord::get_db_block] findNet $rail] setSpecial
 [[ord::get_db_block] findBTerm $rail] setSigType [[[ord::get_db_block] findNet $rail] getSigType]
}}
make_tracks
place_pins -hor_layers met3 -ver_layers met2 -corner_avoidance 10 -min_distance 2 -write_pin_placement {{{out/'pin_placement.tcl'}}}
set_routing_layers -signal met1-met4 -clock met2-met4
set_macro_extension 0
global_route -guide_file {{{out/'route.guide'}}} -congestion_iterations 50 -congestion_report_file {{{out/'congestion.rpt'}}} -verbose
write_db {{{out/'guided.odb'}}}
write_def {{{out/'guided.def'}}}
''')
        run('detail',f'''read_db {{{out/'guided.odb'}}}
set_thread_count 2
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
        assert actual==expected()
        verify(pins)
        save(out/'assessment.json',dict(input_sha256=pins,router_drc_violations=0,macro_pins_checked=len(actual),
             exact_macro_bindings_preserved=True,main_rail_database_connectivity_pass=True,
             signal_nets_routed=len((out/'signal_wires.tsv').read_text().splitlines()),
             assembled_drc_pass=False,assembled_lvs_pass=False,antenna_qualified=False,
             extraction_complete=False,prototype_handoff_qualified=False,release_qualified=False,
             artifacts={str(path):sha(path) for path in out.iterdir() if path.is_file() and path.name!='status.json'}))
        save(out/'status.json',dict(state='parent_route_pass_pending_assembled_checks',completed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False))
    except BaseException as e:
        save(out/'status.json',dict(state='failed',reason=str(e),observed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False));raise


if __name__=='__main__':main()
