#!/usr/bin/env python3
"""Add local HD diode protection on REF and CLKDIVR inside the detector.

Two decap12 sites become decap6+decap4+diode2 at the same row footprints.
Functional cells and ports remain fixed. Supply decoupling and input loads
change; fresh physical, formation-layer and analog checks are mandatory.
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
from check_compact_mapping import OPENROAD
from characterize_compact_propagation import PDK
from run_dco_qualification import ROOT,sha,save


def main():
    start=time.monotonic()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    base=ROOT/'build/timing400/release_001'
    sampled=ROOT/'build/timing450/interface_characterization/bbpd_sampled'
    source=sampled/'runs/timing450_sampled_v2/final'
    proof=json.loads((sampled/'physical_assessment.json').read_text())
    assert proof['magic_drc']==0 and proof['lvs_unique']
    gds=source/'mag_gds/IntegerPLL_BBPD.magic.gds'
    assert sha(gds)==proof['sha256']['/work/OpenPLL/'+str(gds.relative_to(ROOT))]
    formation=verify(base/'antenna_port_formation_002/assessment.json')
    assert formation['fully_formed_native_gate_port_bindings_passed']==150
    library=PDK/'libs.ref/sky130_fd_sc_hd'
    lib=library/'lib/sky130_fd_sc_hd__tt_025C_1v80.lib'
    paths=[Path(__file__).resolve(),Path(OPENROAD),lib,
        source/'odb/IntegerPLL_BBPD.odb',source/'def/IntegerPLL_BBPD.def',source/'pnl/IntegerPLL_BBPD.pnl.v',gds,
        sampled/'physical_assessment.json',base/'antenna_port_formation_002/assessment.json',
        base/'candidate_antenna_localization_003/debug_records.json',
        base/'bbpd_antenna_site_probe_003/probe.tcl',base/'bbpd_antenna_site_probe_003/probe.log']
    pins={str(p):sha(p) for p in paths}
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(),total_budget_s=43200,
        deadline_uptime=time.clock_gettime(time.CLOCK_BOOTTIME)+(43200-(time.monotonic()-start)),
        automatic_identical_retry=False))
    script=out/'repair.tcl'
    script.write_text(f'''read_liberty {lib}
read_db {source}/odb/IntegerPLL_BBPD.odb
set_thread_count 4
set_routing_layers -signal met1-met5 -clock met1-met5
set block [ord::get_db_block]
global_route -start_incremental
foreach row {{{{REF FILLER_16_85 44620 54400}} {{CLKDIVR FILLER_18_85 44620 59840}}}} {{
 lassign $row signal old_name x y
 set old [$block findInst $old_name]
 if {{$old eq {{NULL}} || [[$old getMaster] getName] ne {{sky130_fd_sc_hd__decap_12}}}} {{error "unexpected decap site"}}
 if {{[$old getLocation] ne [list $x $y] || [$old getOrient] ne {{R0}}}} {{error "changed decap placement"}}
 set net [$block findNet $signal]
 if {{$net eq {{NULL}}}} {{error "missing detector input"}}
 set bb [$old getBBox]
 if {{[$bb xMax]-[$bb xMin]!=5520 || [$bb yMax]-[$bb yMin]!=2720}} {{error "unexpected site dimensions"}}
 odb::dbInst_destroy $old
 foreach item {{{{decap_6 0}} {{decap_4 2760}} {{diode_2 4600}}}} {{
  lassign $item kind dx
  set name antenna_${{signal}}_${{kind}}
  set inst [odb::dbInst_create $block [[ord::get_db] findMaster sky130_fd_sc_hd__${{kind}}] $name]
  $inst setOrient R0
  $inst setLocation [expr {{$x+$dx}}] $y
  $inst setPlacementStatus PLACED
  foreach pin {{VPWR VPB}} {{[$inst findITerm $pin] connect [$block findNet VPWR]}}
  foreach pin {{VGND VNB}} {{[$inst findITerm $pin] connect [$block findNet VGND]}}
  if {{$kind eq {{diode_2}}}} {{[$inst findITerm DIODE] connect $net}}
 }}
 if {{[$net getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$net getWire]}}
}}
write_db {out}/mutated.odb
global_route -end_incremental
foreach signal {{REF CLKDIVR}} {{
 set net [$block findNet $signal]
 if {{[$net getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$net getWire]}}
}}
check_placement -verbose
write_db {out}/repaired_guides.odb
detailed_route -output_drc {out}/route.drc -output_maze {out}/route.maze.log -output_guide_coverage {out}/route.coverage
write_db {out}/route.odb
write_def {out}/route.def
write_verilog {out}/route.v
write_verilog -include_pwr_gnd {out}/powered.v
check_power_grid -net VPWR -error_file {out}/vpwr_errors.rpt
check_power_grid -net VGND -error_file {out}/vgnd_errors.rpt
set f [open {out}/instances.tsv w]
foreach inst [$block getInsts] {{
 puts $f [join [list INST [$inst getName] [[$inst getMaster] getName] [$inst getOrient] [$inst getLocation]] "\\t"]
 foreach pin [$inst getITerms] {{
  set net [$pin getNet]
  set netname NULL
  if {{$net ne {{NULL}}}} {{set netname [$net getName]}}
  puts $f [join [list PIN [$inst getName] [[$pin getMTerm] getName] $netname] "\\t"]
 }}
}}
close $f
exit
''')
    pins[str(script)]=sha(script)
    save(out/'input_manifest.json',dict(input_sha256=pins,scope=__doc__))
    with (out/'repair.log').open('x') as log:
        child=subprocess.Popen([OPENROAD,'-no_init','-exit',str(script)],stdout=log,stderr=subprocess.STDOUT)
        save(out/'status.json',dict(state='native_running',native_pid=child.pid,release_qualified=False))
        try:code=child.wait(timeout=max(1,43200-(time.monotonic()-start)))
        except subprocess.TimeoutExpired:
            child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()
            save(out/'status.json',dict(state='timeout_inconclusive',release_qualified=False));return
    if code:
        save(out/'status.json',dict(state='native_nonpass',exit_code=code,release_qualified=False));return
    assert not (out/'route.drc').read_text().strip()
    assert 'Error:' not in (out/'repair.log').read_text()
    counts=Counter()
    for line in (out/'instances.tsv').read_text().splitlines():
        row=line.split('\t')
        if row[0]=='INST':counts[row[2]]+=1
    assert counts['sky130_fd_sc_hd__diode_2']==2
    for path,digest in pins.items():assert sha(path)==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name not in ('status.json','owner.json')},
        top='IntegerPLL_BBPD',master_counts=dict(counts),router_drc_violations=0,
        protection_diodes=2,protected_inputs=['REF','CLKDIVR'],
        removed_decap_12_cells=2,added_decap_6_cells=2,added_decap_4_cells=2,
        supply_decoupling_changed=True,physical_signoff_qualified=False,
        analog_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='candidate_routed',release_qualified=False))
    print('Detector protection candidate routed; physical and analog qualification remain open.')


if __name__=='__main__':main()
