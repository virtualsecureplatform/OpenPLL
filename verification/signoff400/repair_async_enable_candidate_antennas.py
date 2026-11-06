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
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import LIB,LEF,TECH,OPENROAD,ALLOWED
from route_compact_candidate import PHYSICAL,RC_MODEL
sys.path.append(str(ROOT/"verification/signoff400"))
from resources import lease
from compiled_charge_v2 import execute


sys.path.insert(0,str(ROOT/'verification/prototype400'))
from repair_measured_antennas_v2 import violation_targets, tcl_word
from repair_measured_antennas_v3 import repair_tcl


def main():
    import os
    os.sched_setaffinity(0,{28,29,30,31})
    started=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=started+43200
    started_utc=datetime.now(timezone.utc).isoformat()
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--route',required=True,type=Path)
    p.add_argument('--placement',required=True,type=Path)
    p.add_argument('--equivalence',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();source=a.route.resolve();out=a.output.resolve()
    receipt=json.loads((source/'assessment.json').read_text())
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
           ROOT/'verification/signoff400/common_v3.py',
           ROOT/'verification/prototype400/repair_measured_antennas_v2.py',
           ROOT/'verification/prototype400/repair_measured_antennas_v3.py',
           ROOT/'verification/signoff400/resources.py',
           ROOT/'verification/signoff400/compiled_charge_v2.py']
    pins={str(path):sha(path) for path in files}
    save(out/'targets.json',dict(targets=targets,policy='one matched-footprint local diode per measured violating pin; source-specific instance namespace; no cell movement'))
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
global_route -start_incremental
{repair_tcl(targets, 'enable_candidate_diode_'+sha(source/'assessment.json')[:12])}
global_route -end_incremental
foreach name {{{' '.join(tcl_word(n) for n in sorted({t[0] for t in targets}))}}} {{
 set target [$block findNet $name]
 if {{[$target getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$target getWire]}}
}}
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
            execute([OPENROAD,'-exit',str(task)],out/'route.log',deadline,8)
        code=0
    except BaseException as error:
        save(out/'status.json',dict(state='physical_build_nonpass',reason=repr(error)))
        raise
    text=(out/'route.log').read_text()
    if code or 'Error:' in text:
        save(out/'status.json',dict(state='physical_build_nonpass',native_exit=code))
        raise RuntimeError(text[-2500:])
    counts=Counter((out/'masters.txt').read_text().splitlines())
    assert set(counts)<=ALLOWED|PHYSICAL|{'sky130_fd_sc_hs__diode_2'}
    drc_counts=re.findall(r'Number of violations = (\d+)',text)
    if not drc_counts or int(drc_counts[-1]) or (out/'route.drc').stat().st_size:raise ValueError('final router DRC must be clean')
    verify(pins)
    save(out/'assessment.json',dict(input_sha256=pins,
         artifacts={str(path):sha(path) for path in out.iterdir() if path.is_file() and path.name!='status.json'},
         candidate_source_sha256=receipt['candidate_source_sha256'],
         measured_target_pins=len(targets),measured_target_nets=len({t[0] for t in targets}),
         filler_partition_helper='repair_measured_antennas_v3',
         cell_inventory=dict(counts),digital_routing_completed=True,nominal_rc_extracted=True,
         auxiliary_diode_load_is_conditional=True,physical_timing_qualified=False,
         assembled_macro_qualified=False,prototype_handoff_qualified=False))
    save(out/'status.json',dict(state='digital_route_completed_pending_independent_checks',prototype_handoff_qualified=False))


if __name__=='__main__':main()
