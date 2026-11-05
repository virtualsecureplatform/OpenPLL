#!/usr/bin/env python3
"""Route long trunks on M1/M2, reserving upper layers for macro access.

Macro interiors and placements remain fixed. Diode routing must subsequently
be checked at each formation stage; a routed connection through upper metal
alone does not establish protection. Share the placement owner's 12h deadline.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from check_compact_clock_tree import verify
from check_compact_mapping import OPENROAD
from run_dco_qualification import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();base=ROOT/'build/timing400/release_001'
    power=base/'parent_dco_antenna_pg_minarea_001/assessment.json';proof=verify(power)
    assert proof['openroad_power_connectivity_passed']
    database=Path(proof['physical_db']);original_owner=Path(proof['owner'])
    owner=json.loads(original_owner.read_text());deadline=owner['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__).resolve(),Path(OPENROAD),power,database,original_owner]
    pins={str(p):sha(p) for p in files}
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        deadline_uptime=deadline,original_owner=str(original_owner),total_budget_restarted=False,automatic_identical_retry=False))
    task=out/'route.tcl'
    task.write_text(f'''read_db {database}
set_thread_count 4
set block [ord::get_db_block]
set removed 0
foreach net [$block getNets] {{
 if {{[$net getSigType] ni {{POWER GROUND}} && [$net getWire] ne {{NULL}}}} {{
  odb::dbWire_destroy [$net getWire]
  incr removed
 }}
}}
puts "OLD_SIGNAL_WIRES_REMOVED=$removed"
if {{$removed!=357}} {{error "unexpected source signal inventory"}}
set_routing_layers -signal met1-met4 -clock met1-met4
set_global_routing_layer_adjustment met2 0.5
set_global_routing_layer_adjustment met3 0.99
set_global_routing_layer_adjustment met4 0.9
global_route -verbose -guide_file {out}/route.guide -congestion_iterations 100
write_db {out}/global.odb
detailed_route -output_drc {out}/route.drc -output_maze {out}/route.maze.log -output_guide_coverage {out}/route.coverage
write_db {out}/route.odb
write_def {out}/route.def
write_verilog {out}/route.v
write_verilog -include_pwr_gnd {out}/powered_top.v
check_power_grid -net VPWR -error_file {out}/vpwr_errors.rpt
check_power_grid -net VGND -error_file {out}/vgnd_errors.rpt
set f [open {out}/signal_inventory.tsv w]
foreach net [$block getNets] {{
 if {{[$net getSigType] ni {{POWER GROUND}}}} {{
  if {{[$net getWire] eq {{NULL}}}} {{error "missing signal wire"}}
  puts $f [$net getName]
 }}
}}
close $f
''')
    pins[str(task)]=sha(task);save(out/'input_manifest.json',dict(input_sha256=pins,scope=__doc__))
    with (out/'route.log').open('x') as log:
        child=subprocess.Popen([OPENROAD,'-no_init','-exit',str(task)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        save(out/'status.json',dict(state='native_routing',native_pid=child.pid,observed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False))
        try:code=child.wait(timeout=deadline-time.clock_gettime(time.CLOCK_BOOTTIME))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            save(out/'status.json',dict(state='timeout_inconclusive',release_qualified=False));return
    save(out/'native_completion.json',dict(input_sha256=pins,native_exit=code,release_qualified=False))
    assert code==0
    text=(out/'route.log').read_text();counts=re.findall(r'Number of violations = (\d+)',text)
    assert counts and counts[-1]=='0' and (out/'route.drc').stat().st_size==0
    assert all(f'All shapes on net {n} are connected.' in text for n in ['VPWR','VGND'])
    nets=(out/'signal_inventory.tsv').read_text().splitlines();assert len(nets)==len(set(nets))==357
    for path,digest in pins.items():assert sha(path)==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'},
        detailed_route_completed=True,router_drc_violations=0,signal_nets_with_detailed_wire=357,
        main_rail_connectivity_passed=True,parent_signal_routes_rebuilt=True,
        macro_interiors_unchanged=True,full_assembled_drc_passed=False,assembled_lvs_passed=False,
        formation_stage_protection_verified=False,rc_qualified=False,antenna_qualified=False,
        analog_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='routed_candidate',router_drc_violations=0,release_qualified=False))
    print('Rebuilt all357 parent signal nets; router DRC0 and both power grids connected. Full layout and antenna checks remain mandatory.')

if __name__=='__main__':main()
