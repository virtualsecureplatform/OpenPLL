#!/usr/bin/env python3
"""Repair routed timing/electrical violations in a fresh diagnostic candidate.

No RTL changes or new timing exceptions. Independent equivalence, DRC, LVS,
antenna and renewed timing checks remain mandatory before route selection.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
from common import ROOT, save, sha, verify, source_pins
sys.path.append(str(ROOT / 'verification/signoff400'))
from compiled_charge_v2 import execute
from resources import lease
sys.path.append(str(ROOT / 'verification/timing400'))
from check_compact_mapping import LIB, LEF, TECH, OPENROAD, ALLOWED
from route_compact_candidate import PHYSICAL, RC_MODEL


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('route', 'timing', 'placement', 'output'):
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--threads', type=int, choices=(1, 2, 4, 8, 16), default=8)
    p.add_argument('--mode', choices=('all','electrical'), default='all')
    a = p.parse_args()
    source, timing, placement, out = (x.resolve() for x in (a.route, a.timing, a.placement, a.output))
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 43200
    save(out / 'owner.json', dict(pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
         deadline_uptime=deadline, wall_limit_s=43200, internal_threads=a.threads, repair_mode=a.mode, automatic_identical_retry=False))

    def status(state, **kw):
        save(out / 'status.json', dict(state=state, observed_utc=datetime.now(timezone.utc).isoformat(),
             physical_timing_qualified=False, release_qualified=False, **kw))

    try:
        status('verifying_supplied_timing_evidence')
        report = json.loads((timing / 'assessment.json').read_text())
        verify(report['input_sha256']); verify(report['artifacts'])
        if not report.get('related_fast_and_divided_clock_paths_timed') or report.get('all_reported_checks_passed'):
            raise ValueError('expected a related-clock timing/electrical nonpass diagnostic')
        if report['input_sha256'].get(str(source / 'route.odb')) != sha(source / 'route.odb'):
            raise ValueError('timing evidence belongs to another digital route')
        placed = json.loads((placement / 'assessment.json').read_text())
        if any(placed['input_sha256'].get(k) != v for k, v in source_pins().items()):
            raise ValueError('placement does not match current RTL')
        sdc, spef = timing / 'diagnostic_400.sdc', timing / 'route.max.normalized.spef'
        for path in (sdc, spef):
            if report['input_sha256'].get(str(path)) != sha(path):
                raise ValueError('unverified diagnostic constraints or routed RC')
        diode = ROOT / 'build/timing400/release_001/antenna_diode_load_001/antenna_diode_load.lib'
        paths = [Path(__file__).resolve(), Path(sys.executable), Path(OPENROAD), LIB, LEF, TECH, RC_MODEL,
                 source / 'route.odb', source / 'route.v', source / 'assessment.json',
                 timing / 'assessment.json', sdc, spef, placement / 'assessment.json', diode,
                 ROOT / 'verification/signoff400/compiled_charge_v2.py', ROOT / 'verification/signoff400/resources.py',
                 Path(__file__).with_name('common.py'), ROOT / 'verification/timing400/check_compact_mapping.py',
                 ROOT / 'verification/timing400/route_compact_candidate.py']
        pins = dict(source_pins(), **{str(path): sha(path) for path in paths})
        save(out / 'input_manifest.json', dict(input_sha256=pins))
        allowed = ' '.join(sorted(ALLOWED))
        actions='repair_design -slew_margin 20 -cap_margin 25 -verbose\n'
        if a.mode=='all':
            actions+='repair_timing -setup -setup_margin 0.15 -max_iterations 100 -skip_gate_cloning -skip_size_down -skip_buffer_removal -verbose\n'
            actions+='repair_timing -hold -hold_margin 0.15 -setup_margin 0.15 -max_iterations 100 -verbose\n'
        script = out / 'repair.tcl'
        script.write_text(f'''read_lef {TECH}
read_lef {LEF}
read_liberty {LIB}
read_liberty {diode}
read_db {source}/route.odb
source {sdc}
set_thread_count {a.threads}
set_propagated_clock [all_clocks]
set_wire_rc -signal -layer met2
set_wire_rc -clock -layer met3
read_spef {spef}
set allowed {{{allowed}}}
foreach cell [get_lib_cells *] {{
 set name [lindex [split [get_full_name $cell] /] end]
 if {{$name ni $allowed}} {{set_dont_use $cell}}
}}
set block [ord::get_db_block]
# Preserve taps/endcaps; free only ordinary spacers for additional buffers.
set removed 0
foreach inst [$block getInsts] {{
 if {{[[$inst getMaster] getName] in {{sky130_fd_sc_hs__fill_1 sky130_fd_sc_hs__fill_2 sky130_fd_sc_hs__fill_4 sky130_fd_sc_hs__fill_8}}}} {{
  odb::dbInst_destroy $inst
  incr removed
 }}
}}
puts "REMOVED_SPACERS=$removed"
global_route -start_incremental
{actions}
detailed_placement
filler_placement {{sky130_fd_sc_hs__fill_8 sky130_fd_sc_hs__fill_4 sky130_fd_sc_hs__fill_2 sky130_fd_sc_hs__fill_1}}
add_global_connection -net VDD -inst_pattern {{.*}} -pin_pattern {{^(VPWR|VPB)$}} -power
add_global_connection -net VSS -inst_pattern {{.*}} -pin_pattern {{^(VGND|VNB)$}} -ground
global_connect
check_placement -verbose
global_route -end_incremental -congestion_iterations 100
detailed_route -output_drc {out}/route.drc -output_maze {out}/route.maze.log -output_guide_coverage {out}/route.coverage
write_db {out}/route.odb
write_def {out}/route.def
write_verilog {out}/route.v
write_verilog -include_pwr_gnd {out}/powered.v
write_abstract_lef {out}/digital.lef
check_power_grid -net VDD -error_file {out}/vdd_errors.rpt
check_power_grid -net VSS -error_file {out}/vss_errors.rpt
define_process_corner -ext_model_index 0 RCX_NOM
extract_parasitics -ext_model_file {RC_MODEL} -corner 0
write_spef {out}/route.nom.spef
report_checks -path_delay max -group_path_count 5 -digits 6
report_checks -path_delay min -group_path_count 5 -digits 6
report_check_types -max_slew -max_capacitance -min_pulse_width
set inventory [open {out}/masters.txt w]
foreach inst [$block getInsts] {{puts $inventory [[$inst getMaster] getName]}}
close $inventory
puts "POST_ROUTE_TIMING_REPAIR_COMPLETE"
exit
''')
        status('post_route_timing_repair_running')
        with lease(a.threads, 8, deadline):
            execute([OPENROAD, '-no_init', '-exit', script], out / 'repair.log', deadline, 8)
        text = (out / 'repair.log').read_text()
        if 'POST_ROUTE_TIMING_REPAIR_COMPLETE' not in text:
            raise ValueError('timing repair incomplete')
        counts = re.findall(r'Number of violations = (\d+)', text)
        if not counts or counts[-1] != '0' or (out / 'route.drc').stat().st_size:
            raise ValueError('repaired detailed route has DRC violations')
        for net in ('VDD', 'VSS'):
            if f'All shapes on net {net} are connected.' not in text:
                raise ValueError('repaired power-grid database connectivity nonpass')
        inventory = Counter((out / 'masters.txt').read_text().splitlines())
        if not set(inventory) <= ALLOWED | PHYSICAL | {'sky130_fd_sc_hs__diode_2'}:
            raise ValueError('unsupported master introduced during repair')
        verify(pins)
        save(out / 'assessment.json', dict(input_sha256=pins,
             artifacts={str(path): sha(path) for path in out.iterdir() if path.is_file() and path.name != 'status.json'},
             cell_inventory=dict(inventory), digital_routing_completed=True, nominal_rc_extracted=True,
             router_drc_violations=0, database_power_grid_connected=True,
             supplied_view_timing_repair_attempted=True, repair_mode=a.mode, related_clock_paths_not_excluded=True,
             auxiliary_diode_load_is_conditional=True, final_parent_fill_and_interface_loading_included=False,
             digital_timing_qualified=False, physical_timing_qualified=False, assembled_macro_qualified=False,
             prototype_handoff_qualified=False, release_qualified=False))
        status('digital_route_completed_pending_independent_checks')
    except BaseException as error:
        status('physical_build_nonpass', reason=repr(error)); raise


if __name__ == '__main__':
    main()
