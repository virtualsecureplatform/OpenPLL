#!/usr/bin/env python3
"""Reroute the last localized parent antenna failure on the lower metal stack.

Keep all356 other signal routes, every instance and every logical binding.
A successful route is only a candidate: full GDS DRC/LVS and forming-stage
antenna checks must independently validate the changed physical geometry.
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
from check_bbpd_repair_identity import design,section
from check_compact_clock_tree import verify
from check_compact_mapping import OPENROAD,TECH,LEF
from run_dco_qualification import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();base=ROOT/'build/timing400/release_001';source=base/'parent_dco_antenna_targeted_008'
    proof=verify(source/'assessment.json');verify(base/'parent_dco_antenna_layout_audit_008/assessment.json')
    loc=base/'parent_dco_antenna_localization_008';verify(loc/'assessment.json')
    bad=json.loads((loc/'records.json').read_text());assert len(bad)==1
    target=bad[0]['logical_nets'];assert target==['DCO_THERM[53]'];target=target[0]
    assert bad[0]['stage']=='m3' and bad[0]['ratio']>bad[0]['allowed_ratio']
    deadline=json.loads((source/'owner.json').read_text())['deadline_uptime'];assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    dco='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    lefs=[base/'digital_macro_abstract_001/IntegerPLL_AcquiringCore.lef',
        ROOT/f'openlane/{dco}/runs/c1fine_range_001/final/lef/{dco}.lef',
        ROOT/'build/timing450/interface_characterization/bbpd_sampled/runs/timing450_sampled_v2/final/lef/IntegerPLL_BBPD.lef']
    files=[Path(__file__).resolve(),Path(OPENROAD),TECH,LEF,*lefs,source/'assessment.json',source/'route.def',source/'owner.json',
        base/'parent_dco_antenna_layout_audit_008/assessment.json',loc/'assessment.json',loc/'records.json',Path(proof['extra_placement_plan'])]
    pins={str(p):sha(p) for p in files};out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,
        original_owner=str(source/'owner.json'),total_budget_restarted=False,automatic_identical_retry=False))
    text=(source/'route.def').read_text();old=section(source/'route.def','NETS')
    def fixed(match):
        name,body=match.group(1),match.group(2)
        return '- '+name+' '+re.sub(r'\b(?:FIXED|ROUTED)\b','ROUTED' if name==target else 'FIXED',body)+';'
    new=re.sub(r'^\s*-\s+(\S+)\s+(.*?);',fixed,old,flags=re.M|re.S)
    fixed_def=out/'fixed_background.def';fixed_def.write_text(text.replace(old,new))
    pins[str(fixed_def)]=sha(fixed_def)
    task=out/'route.tcl'
    task.write_text(f'''read_lef {TECH}
read_lef {LEF}
'''+''.join(f'read_lef {p}\n' for p in lefs)+f'''read_def {fixed_def}
set_thread_count 4
set block [ord::get_db_block]
set target {{{target}}}
set decoder [odb::dbWireDecoder]
set fixed 0
foreach net [$block getNets] {{
 if {{[$net getSigType] in {{POWER GROUND}}}} {{continue}}
 if {{[$net getName] eq $target}} {{
  if {{[$net getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$net getWire]}}
 }} else {{
  $decoder begin [$net getWire]
  $decoder next
  if {{[$decoder getWireType] ne {{FIXED}}}} {{error "unfixed background route"}}
  incr fixed
 }}
}}
if {{$fixed!=356}} {{error "wrong background count"}}
set_routing_layers -signal met1-met2 -clock met1-met2
set_global_routing_layer_adjustment met2 0.5
global_route -verbose -guide_file {out}/route.guide -congestion_iterations 100
detailed_route -output_drc {out}/route.drc -output_maze {out}/route.maze.log -output_guide_coverage {out}/route.coverage
write_db {out}/route.odb
write_def {out}/route.def
write_verilog {out}/route.v
write_verilog -include_pwr_gnd {out}/powered_top.v
check_power_grid -net VPWR -error_file {out}/vpwr_errors.rpt
check_power_grid -net VGND -error_file {out}/vgnd_errors.rpt
''')
    pins[str(task)]=sha(task);save(out/'input_manifest.json',dict(input_sha256=pins,scope=__doc__))
    with (out/'route.log').open('x') as log:
        child=subprocess.Popen([OPENROAD,'-no_init','-exit',str(task)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        save(out/'status.json',dict(state='native_routing',native_pid=child.pid,release_qualified=False))
        try:code=child.wait(timeout=deadline-time.clock_gettime(time.CLOCK_BOOTTIME))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            save(out/'status.json',dict(state='timeout_inconclusive',release_qualified=False));return
    save(out/'native_completion.json',dict(input_sha256=pins,exit_code=code,release_qualified=False))
    if code!=0:
        save(out/'status.json',dict(state='native_nonpass',exit_code=code,release_qualified=False));return
    log=(out/'route.log').read_text();counts=re.findall(r'Number of violations = (\d+)',log)
    assert counts and counts[-1]=='0' and (out/'route.drc').stat().st_size==0
    assert all(f'All shapes on net {n} are connected.' in log for n in ['VPWR','VGND'])
    oldcells,oldpins,oldnets=design(source/'route.def');newcells,newpins,newnets=design(out/'route.def')
    assert newcells==oldcells and newpins==oldpins
    assert section(source/'route.def','PINS')==section(out/'route.def','PINS')
    def normalized(body):return re.sub(r'\bFIXED\b','ROUTED',body)
    frozen=[n for n,row in oldnets.items() if n!=target and re.search(r'\b(?:ROUTED|FIXED)\b',row)]
    assert len(frozen)==356 and all(normalized(newnets[n])==normalized(oldnets[n]) for n in frozen)
    for path,digest in pins.items():assert sha(path)==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'},
        detailed_route_completed=True,router_drc_violations=0,main_rail_connectivity_passed=True,parent_signal_routes_rebuilt=True,
        extra_placement_plan=proof['extra_placement_plan'],added_diode_instances=0,added_well_tap_instances=0,
        target_nets=[target],unchanged_background_signal_routes=356,retained_macro_and_cell_placements_identical=True,
        all_old_pin_bindings_preserved=True,all_macro_ports_preserved=True,no_new_power_straps_or_vias=True,
        full_assembled_drc_passed=False,assembled_lvs_passed=False,antenna_qualified=False,rc_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='routed_candidate',router_drc_violations=0,background_fixed_routes=356,release_qualified=False))
    print('Last localized net rerouted; all356 background routes, placements and logical bindings unchanged.')

if __name__=='__main__':main()
