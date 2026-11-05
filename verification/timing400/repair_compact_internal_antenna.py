#!/usr/bin/env python3
"""Add one physical diode for the localized internal via-antenna failure.

Replaces a same-size filler at its exact site. Functional cells, macro ports
and placement remain fixed. Incremental routing updates the affected net;
fresh logic/layout/MOS-only antenna and loaded timing checks remain required.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import time

from check_compact_clock_tree import verify
from check_compact_mapping import ALLOWED,LIB,TECH,LEF,OPENROAD
from route_compact_candidate import PHYSICAL,RC_MODEL
from run_dco_qualification import ROOT,sha,save

DIODE='sky130_fd_sc_hs__diode_2'


def main():
    start=time.monotonic()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    base=ROOT/'build/timing400/release_001'
    source=base/'compact_incremental_headroom_001'
    receipt=verify(source/'assessment.json')
    eq=verify(base/'compact_incremental_headroom_equivalence_001/assessment.json')
    assert eq['all_transition_and_output_functions_equivalent']
    assert eq['input_sha256'][str(source/'route.v')]==sha(source/'route.v')
    localized=verify(base/'candidate_antenna_localization_003/assessment.json')
    assert localized['native_debug_records']==localized['native_debug_records_with_exact_gate_matches']==151
    cts=base/'compact_cts_001'
    load=base/'antenna_diode_load_001'
    diode=verify(load/'assessment.json')
    assert diode['cell']==DIODE and diode['native_model_equivalence_revalidated']
    paths=[Path(__file__).resolve(),Path(OPENROAD),LIB,TECH,LEF,RC_MODEL,
        source/'assessment.json',source/'route.odb',source/'route.v',cts/'cts.tcl',
        base/'compact_incremental_headroom_equivalence_001/assessment.json',
        base/'candidate_antenna_localization_003/assessment.json',
        base/'candidate_antenna_localization_003/debug_records.json',
        base/'internal_antenna_sink_probe_001/probe.tcl',base/'internal_antenna_sink_probe_001/probe.log',
        base/'internal_antenna_diode_site_probe_001/probe.tcl',base/'internal_antenna_diode_site_probe_001/probe.log',
        load/'assessment.json',load/'antenna_diode_load.lib',
        base/'postroute_antenna_source_audit_001/GlobalRouter.cpp']
    pins={str(p):sha(p) for p in paths}
    constraints=(cts/'cts.tcl').read_text().split('create_clock -name REFCLK',1)[1].split('set_thread_count')[0]
    constraints='create_clock -name REFCLK'+constraints
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(),total_budget_s=43200,
        deadline_uptime=time.clock_gettime(time.CLOCK_BOOTTIME)+(43200-(time.monotonic()-start)),
        automatic_identical_retry=False))
    task=out/'repair.tcl'
    task.write_text(f'''read_lef {TECH}
read_lef {LEF}
read_liberty {LIB}
read_liberty {load}/antenna_diode_load.lib
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
set block [ord::get_db_block]
set victim [$block findInst FILLER_19_546]
if {{$victim eq {{NULL}} || [[$victim getMaster] getName] ne {{sky130_fd_sc_hs__fill_2}}}} {{error "unexpected filler site"}}
set target [$block findNet electrical_root_33_out]
set sink [[$block findInst electrical_branch_124] findITerm A]
if {{[$sink getNet] ne $target}} {{error "wrong localized net"}}
set orient [$victim getOrient]
lassign [$victim getLocation] x y
if {{$x != 272160 || $y != 76590 || $orient ne {{MX}}}} {{error "changed filler placement"}}
set bb [$victim getBBox]
set old_box [list [$bb xMin] [$bb yMin] [$bb xMax] [$bb yMax]]
global_route -start_incremental
odb::dbInst_destroy $victim
set added [odb::dbInst_create $block [[ord::get_db] findMaster {DIODE}] core_antenna_tiedown_001]
$added setOrient $orient
$added setLocation $x $y
$added setPlacementStatus PLACED
set bb [$added getBBox]
if {{[list [$bb xMin] [$bb yMin] [$bb xMax] [$bb yMax]] ne $old_box}} {{error "diode footprint mismatch"}}
[$added findITerm DIODE] connect $target
foreach pin {{VPWR VPB}} {{[$added findITerm $pin] connect [$block findNet VDD]}}
foreach pin {{VGND VNB}} {{[$added findITerm $pin] connect [$block findNet VSS]}}
if {{[$target getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$target getWire]}}
write_db {out}/mutated.odb
global_route -end_incremental
# A temporary guide wire is not legal detailed routing of the added endpoint.
if {{[$target getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$target getWire]}}
check_placement -verbose
write_db {out}/repaired_guides.odb
detailed_route -output_drc {out}/route.drc -output_maze {out}/route.maze.log -output_guide_coverage {out}/route.coverage
write_db {out}/route.odb
write_def {out}/route.def
write_verilog {out}/route.v
write_verilog -include_pwr_gnd {out}/powered.v
check_power_grid -net VDD -error_file {out}/vdd_errors.rpt
check_power_grid -net VSS -error_file {out}/vss_errors.rpt
define_process_corner -ext_model_index 0 RCX_NOM
extract_parasitics -ext_model_file {RC_MODEL} -corner 0
write_spef {out}/route.nom.spef
set f [open {out}/masters.txt w]
foreach inst [$block getInsts] {{puts $f [[$inst getMaster] getName]}}
close $f
exit
''')
    pins[str(task)]=sha(task)
    save(out/'input_manifest.json',dict(input_sha256=pins,scope=__doc__))
    with (out/'repair.log').open('x') as log:
        child=subprocess.Popen([OPENROAD,'-no_init','-exit',str(task)],stdout=log,stderr=subprocess.STDOUT)
        save(out/'status.json',dict(state='native_running',native_pid=child.pid,release_qualified=False))
        try:
            code=child.wait(timeout=max(1,43200-(time.monotonic()-start)))
        except subprocess.TimeoutExpired:
            child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()
            save(out/'status.json',dict(state='timeout_inconclusive',release_qualified=False));return
    if code:
        save(out/'status.json',dict(state='native_nonpass',exit_code=code,release_qualified=False));return
    assert 'Error:' not in (out/'repair.log').read_text()
    assert not (out/'route.drc').read_text().strip()
    counts=Counter((out/'masters.txt').read_text().splitlines())
    assert set(counts)<=ALLOWED|PHYSICAL|{DIODE}
    assert counts[DIODE]==receipt['antenna_diodes']+1
    for path,digest in pins.items():assert sha(path)==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name not in ('owner.json','status.json')},
        master_counts=dict(counts),antenna_diodes=counts[DIODE],
        functional_cell_types=len(set(counts)-PHYSICAL-{DIODE}),
        passive_auxiliary_types=[DIODE],conditional_diode_load_model=str(load/'assessment.json'),
        restricted_master_inventory_passed=True,nominal_signal_rc_extracted=True,
        router_drc_violations=0,one_same_size_filler_replaced=True,
        assembled_antenna_qualified=False,physical_timing_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='candidate_routed',release_qualified=False))
    print('Routed one-diode internal antenna candidate; fresh equivalence/layout/antenna/timing remain.')


if __name__=='__main__':
    main()
