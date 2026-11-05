#!/usr/bin/env python3
"""Insert diodes for measured digital antenna violations, retaining provenance."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import re
from pathlib import Path
import subprocess
import sys
import time
from common_v3 import ROOT, save, sha, verify
import os
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import LIB,LEF,TECH,OPENROAD,ALLOWED
from route_compact_candidate import PHYSICAL,RC_MODEL
sys.path.append(str(ROOT/"verification/signoff400"))
from resources import lease
from compiled_charge_v2 import execute


def violation_targets(text):
    result=set(); net=None; pin=None
    for line in text.splitlines():
        if line.startswith('Net: '):
            net=line[5:].strip();pin=None
        elif line.lstrip().startswith('Pin:'):
            field=line.strip()[4:].strip().split()[0]
            if '/' not in field:
                raise ValueError('antenna report pin lacks instance/terminal')
            pin=field.rsplit('/',1)
        elif '(VIOLATED)' in line:
            if not net or pin is None:
                raise ValueError('antenna violation lacks net/pin context')
            result.add((net,*pin))
    return sorted(result)


def tcl_word(name):
    if any(c in name for c in '{}\\\r\n'):
        raise ValueError('unsupported Tcl name in measured antenna target')
    return '{'+name+'}'


def repair_tcl(targets, prefix="prototype_m1_repair"):
    expected={('STARTUP_INCREASING','$abc$73649$auto$blifparse.cc:397:parse_blif$76254','A1'),('net74','$auto$ff.cc:337:slice$18957','D')}
    if set(map(tuple,targets))!=expected:raise ValueError('measured metal-1 repair source differs')
    return r"""global_route -start_incremental
set mux [$block findInst {$abc$73649$auto$blifparse.cc:397:parse_blif$76254}]
set sink [$block findInst {$auto$ff.cc:337:slice$18957}]
if {$mux eq {NULL} || $sink eq {NULL}} {error "missing measured receivers"}
if {[[$mux getMaster] getName] ne {sky130_fd_sc_hs__mux2_1} || [[$sink getMaster] getName] ne {sky130_fd_sc_hs__dfrtp_1}} {error "measured receiver master differs"}
if {[[[$mux findITerm A1] getNet] getName] ne {STARTUP_INCREASING}} {error "mux antenna source differs"}
set target [[$sink findITerm D] getNet]
if {[$target getName] ne {net74}} {error "fine-code antenna source differs"}
lassign [$sink getLocation] sx sy
set victim {};set best 2147483647
foreach inst [$block getInsts] {
 if {[[$inst getMaster] getName] ne {sky130_fd_sc_hs__fill_4}} {continue}
 lassign [$inst getLocation] x y
 set distance [expr {abs($x-$sx)+abs($y-$sy)}]
 if {$distance<$best} {set victim $inst;set best $distance}
}
if {$victim eq {} || $best>20000} {error "no same-footprint local buffer site within 20um"}
set orient [$victim getOrient];lassign [$victim getLocation] x y
set box [$victim getBBox];set old_box [list [$box xMin] [$box yMin] [$box xMax] [$box yMax]]
odb::dbInst_destroy $victim
set buffer [odb::dbInst_create $block [[ord::get_db] findMaster sky130_fd_sc_hs__buf_1] prototype_fine1_antenna_buffer]
$buffer setOrient $orient;$buffer setLocation $x $y;$buffer setPlacementStatus PLACED
set box [$buffer getBBox]
if {[list [$box xMin] [$box yMin] [$box xMax] [$box yMax]] ne $old_box} {error "buffer footprint changed"}
set local [odb::dbNet_create $block prototype_fine1_antenna_local]
[$buffer findITerm A] connect $target
[$buffer findITerm X] connect $local
[$sink findITerm D] connect $local
foreach pin {VPWR VPB} {[$buffer findITerm $pin] connect [$block findNet VDD]}
foreach pin {VGND VNB} {[$buffer findITerm $pin] connect [$block findNet VSS]}
if {[$target getWire] ne {NULL}} {odb::dbWire_destroy [$target getWire]}
foreach term [$mux getITerms] {set net [$term getNet];if {$net ne {NULL} && [$net getWire] ne {NULL}} {odb::dbWire_destroy [$net getWire]}}
remove_fillers
replace_cell [$mux getName] sky130_fd_sc_hs__mux2_4
detailed_placement
filler_placement {sky130_fd_sc_hs__fill_8 sky130_fd_sc_hs__fill_4 sky130_fd_sc_hs__fill_2 sky130_fd_sc_hs__fill_1}
add_global_connection -net VDD -inst_pattern {.*} -pin_pattern {^(VPWR|VPB)$} -power
add_global_connection -net VSS -inst_pattern {.*} -pin_pattern {^(VGND|VNB)$} -ground
global_connect
check_placement -verbose
global_route -end_incremental -congestion_iterations 100
"""


def main():
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    started=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=started+43200
    started_utc=datetime.now(timezone.utc).isoformat()
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--route',required=True,type=Path)
    p.add_argument('--placement',required=True,type=Path)
    p.add_argument('--equivalence',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();source=a.route.resolve();out=a.output.resolve()
    receipt=json.loads((source/'assessment.json').read_text())
    candidate_sources=receipt['candidate_source_sha256'];verify(candidate_sources)
    verify(receipt['input_sha256']);verify(receipt['artifacts'])
    eq=json.loads((a.equivalence/'assessment.json').read_text())
    verify(eq['input_sha256']);verify(eq['artifacts'])
    assert eq['all_transition_and_output_functions_equivalent'] and eq['corrupted_reset_function_rejected']
    assert eq['input_sha256'][str(source/'route.v')]==sha(source/'route.v')
    audit=json.loads((source/'signoff/assessment.json').read_text());verify(audit['sha256'])
    assert audit['magic_drc_rectangles']==0 and audit['lvs_unique_match']
    assert audit['power_pins_total']==audit['power_pins_connected']
    assert audit['antenna_net_violations']>0
    report=source/'signoff/antenna.rpt'
    targets=violation_targets(report.read_text())
    assert len(targets)==audit['antenna_pin_violations'], 'measured pin count mismatch'
    assert len({t[0] for t in targets})==audit['antenna_net_violations'], 'measured net count mismatch'
    model=ROOT/'build/timing400/release_001/antenna_diode_load_001'
    diode=json.loads((model/'assessment.json').read_text())
    verify(diode['input_sha256']);verify(diode['artifacts'])
    assert diode['native_model_equivalence_revalidated']
    assert diode['cell']=='sky130_fd_sc_hs__diode_2'
    out.mkdir(parents=True,exist_ok=False)
    save(out/'owner.json',dict(started_utc=started_utc,wall_limit_s=43200,automatic_identical_retry=False))
    files=[Path(__file__).resolve(),Path(OPENROAD),LIB,LEF,TECH,RC_MODEL,
           source/'assessment.json',source/'signoff/assessment.json',source/'route.odb',
           a.placement.resolve()/'diagnostic.sdc',a.equivalence.resolve()/'assessment.json',
           model/'assessment.json',model/'antenna_diode_load.lib',report,
           Path(__file__).with_name('common_v3.py'),
           ROOT/'verification/signoff400/resources.py',
           ROOT/'verification/signoff400/compiled_charge_v2.py']
    pins={**candidate_sources,**{str(path):sha(path) for path in files}}
    save(out/'targets.json',dict(targets=targets,policy='larger mux input gate area and one matched-footprint local data buffer; original FF family retained'))
    script=f'''read_lef {TECH}
read_lef {LEF}
read_liberty {LIB}
read_liberty {model}/antenna_diode_load.lib
read_db {source}/route.odb
source {a.placement.resolve()}/diagnostic.sdc
set_thread_count 4
set_propagated_clock [all_clocks]
set_wire_rc -signal -layer met2
set_wire_rc -clock -layer met3
set block [ord::get_db_block]
{repair_tcl(targets, 'measured_diode_'+sha(source/'assessment.json')[:12])}
check_placement -verbose
write_db {out}/global_route.odb
detailed_route -output_drc {out}/route.drc -output_maze {out}/route.maze.log -output_guide_coverage {out}/route.coverage
write_db {out}/route.odb
write_def {out}/route.def
write_verilog {out}/route.v
write_verilog -include_pwr_gnd {out}/powered.v
write_abstract_lef {out}/digital.lef
check_antennas -report_file {out}/antenna.rpt
define_process_corner -ext_model_index 0 RCX_NOM
extract_parasitics -ext_model_file {RC_MODEL} -corner 0
write_spef {out}/route.nom.spef
set inventory [open {out}/masters.txt w]
foreach inst [[ord::get_db_block] getInsts] {{puts $inventory [[$inst getMaster] getName]}}
close $inventory
exit
'''
    task=out/'repair.tcl';task.write_text(script)
    save(out/'status.json',dict(state='antenna_repair_running',prototype_handoff_qualified=False))
    try:
        with lease(4, 8, deadline):
            execute([OPENROAD,'-exit',str(task)],out/'repair.log',deadline,8)
        code=0
    except BaseException as error:
        save(out/'status.json',dict(state='physical_build_nonpass',reason=repr(error)))
        raise
    text=(out/'repair.log').read_text()
    if code or 'Error:' in text:
        save(out/'status.json',dict(state='physical_build_nonpass',native_exit=code))
        raise RuntimeError(text[-2500:])
    counts=Counter((out/'masters.txt').read_text().splitlines())
    assert set(counts)<=ALLOWED|PHYSICAL|{'sky130_fd_sc_hs__diode_2'}
    verify(pins)
    save(out/'assessment.json',dict(input_sha256=pins,
         artifacts={str(path):sha(path) for path in out.iterdir() if path.is_file() and path.name!='status.json'},
         candidate_source_sha256=candidate_sources,related_fast_and_divided_clock_paths_preserved=True,
         cell_inventory=dict(counts),digital_routing_completed=True,nominal_rc_extracted=True,
         auxiliary_diode_load_is_conditional=True,physical_timing_qualified=False,
         assembled_macro_qualified=False,prototype_handoff_qualified=False))
    save(out/'status.json',dict(state='digital_route_completed_pending_independent_checks',prototype_handoff_qualified=False))


if __name__=='__main__':main()
