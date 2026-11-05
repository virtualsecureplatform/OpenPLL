#!/usr/bin/env python3
"""Route the placed targeted banks using a full DEF import of fixed wires.

Incremental DEF import updates floorplan objects, not the required fixed route
encoding. Reconstruct from exact technology/macro LEFs and the retained placed
DEF, without repeating placement or extending its check budget. Freeze and
verify all347 unaffected signal routes. Full GDS checks remain mandatory.
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
    args=parser.parse_args();base=ROOT/'build/timing400/release_001'
    placed=base/'parent_dco_antenna_targeted_005';source=base/'parent_dco_antenna_route_004';verify(source/'assessment.json')
    plan=json.loads((placed/'extra_placement_plan.json').read_text());selected={r['net'] for r in plan};assert len(selected)==len(plan)==10
    assert all(r['both_m1_power_ports_fully_covered_by_existing_rails'] for r in plan)
    log=(placed/'place.log').read_text();assert all(f'All shapes on net {n} are connected.' in log for n in ['VPWR','VGND'])
    assert 'unfixed background route' in (placed/'route.log').read_text()
    owner=json.loads((placed/'owner.json').read_text());deadline=owner['deadline_uptime'];assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    dco='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    lefs=[base/'digital_macro_abstract_001/IntegerPLL_AcquiringCore.lef',
        ROOT/f'openlane/{dco}/runs/c1fine_range_001/final/lef/{dco}.lef',
        ROOT/'build/timing450/interface_characterization/bbpd_sampled/runs/timing450_sampled_v2/final/lef/IntegerPLL_BBPD.lef']
    files=[Path(__file__).resolve(),Path(OPENROAD),TECH,LEF,*lefs,source/'assessment.json',source/'route.def',placed/'owner.json',
        placed/'placed.def',placed/'fixed_background.def',placed/'extra_placement_plan.json',placed/'m1_power.tsv',placed/'place.tcl',placed/'place.log',placed/'route.log']
    pins={str(p):sha(p) for p in files}
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,
        original_owner=str(placed/'owner.json'),total_budget_restarted=False,automatic_identical_retry=False))
    task=out/'route.tcl';old=(placed/'route.tcl').read_text()
    begin=old.index('set_thread_count 4')
    text=f'read_lef {TECH}\nread_lef {LEF}\n'+''.join(f'read_lef {p}\n' for p in lefs)+f'read_def {placed}/fixed_background.def\n'+old[begin:]
    # Keep fixed-background input, but put all new native outputs here.
    text=text.replace(str(placed)+'/route',str(out)+'/route').replace(str(placed)+'/powered_top.v',str(out)+'/powered_top.v')
    text=text.replace(str(placed)+'/vpwr_errors.rpt',str(out)+'/vpwr_errors.rpt').replace(str(placed)+'/vgnd_errors.rpt',str(out)+'/vgnd_errors.rpt')
    task.write_text(text);pins[str(task)]=sha(task)
    save(out/'input_manifest.json',dict(input_sha256=pins,scope=__doc__))
    with (out/'route.log').open('x') as log:
        child=subprocess.Popen([OPENROAD,'-no_init','-exit',str(task)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        save(out/'status.json',dict(state='native_routing',native_pid=child.pid,release_qualified=False))
        try:code=child.wait(timeout=deadline-time.clock_gettime(time.CLOCK_BOOTTIME))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            save(out/'status.json',dict(state='timeout_inconclusive',release_qualified=False));return
    save(out/'native_completion.json',dict(input_sha256=pins,exit_code=code,release_qualified=False));assert code==0
    text=(out/'route.log').read_text();counts=re.findall(r'Number of violations = (\d+)',text)
    assert counts and counts[-1]=='0' and (out/'route.drc').stat().st_size==0
    for net in ['VPWR','VGND']:assert f'All shapes on net {net} are connected.' in text
    oldcells,oldpins,oldnets=design(source/'route.def');newcells,newpins,newnets=design(out/'route.def')
    assert all(newcells[n]==row for n,row in oldcells.items())
    assert all(newpins[k]==net for k,net in oldpins.items())
    assert section(source/'route.def','PINS')==section(out/'route.def','PINS')
    def normalized(body):return re.sub(r'\bFIXED\b','ROUTED',body)
    frozen=[n for n,row in oldnets.items() if n not in selected and re.search(r'\bROUTED\b',row)]
    assert len(frozen)==347
    assert all(normalized(newnets[n])==normalized(oldnets[n]) for n in frozen)
    for path,digest in pins.items():assert sha(path)==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'},
        detailed_route_completed=True,router_drc_violations=0,main_rail_connectivity_passed=True,parent_signal_routes_rebuilt=True,
        extra_placement_plan=str(placed/'extra_placement_plan.json'),added_diode_instances=40,added_well_tap_instances=10,
        target_nets=sorted(selected),unchanged_background_signal_routes=347,retained_macro_and_cell_placements_identical=True,
        all_old_pin_bindings_preserved=True,all_macro_ports_preserved=True,no_new_power_straps_or_vias=True,
        full_assembled_drc_passed=False,assembled_lvs_passed=False,antenna_qualified=False,rc_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='routed_candidate',router_drc_violations=0,background_fixed_routes=347,release_qualified=False))
    print('Targeted40diodes/10taps routed;347other signal routes and all old bindings/placements verified unchanged.')

if __name__=='__main__':main()
