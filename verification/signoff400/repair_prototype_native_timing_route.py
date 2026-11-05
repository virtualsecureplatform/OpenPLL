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
from common_v3 import ROOT, save, sha, verify
sys.path.append(str(ROOT / 'verification/signoff400'))
from compiled_charge_v2 import execute
os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from resources import lease
sys.path.append(str(ROOT / 'verification/timing400'))
from check_compact_mapping import LIB, LEF, TECH, OPENROAD, ALLOWED
from route_compact_candidate import PHYSICAL, RC_MODEL


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('route', 'timing', 'placement', 'output'):
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--phase-timing',required=True,type=Path)
    p.add_argument('--native-views',required=True,type=Path)
    p.add_argument('--parser',required=True,type=Path)
    p.add_argument('--threads', type=int, choices=(1, 2, 4, 8, 16), default=4)
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
        if not report.get('related_fast_and_divided_clock_paths_preserved') or not report.get('constant_clock_ratio_inductively_proved'):
            raise ValueError('expected a related-clock timing/electrical nonpass diagnostic')
        if report['input_sha256'].get(str(source / 'route.odb')) != sha(source / 'route.odb'):
            raise ValueError('timing evidence belongs to another digital route')
        placed = json.loads((placement / 'assessment.json').read_text())
        routed=json.loads((source/'assessment.json').read_text())
        verify(routed['input_sha256']);verify(routed['artifacts'])
        verify(placed['input_sha256']);verify(placed['artifacts'])
        candidate_sources=routed['candidate_source_sha256']
        if placed['candidate_source_sha256']!=candidate_sources:raise ValueError('placement and route candidate sources differ')
        phase=a.phase_timing.resolve();phase_receipt=phase/'assessment.json';ph=json.loads(phase_receipt.read_text());verify(ph['input_sha256']);verify(ph['artifacts'])
        if not ph.get('conditional_experiment_only') or not ph.get('physical_launch_clock_latency_retained') or ph['input_sha256'].get(str(timing/'assessment.json'))!=sha(timing/'assessment.json'):raise ValueError('proved enabled-phase constraints for this baseline required')
        views=a.native_views.resolve();view_receipt=views/'assessment.json';vr=json.loads(view_receipt.read_text());verify(vr['artifacts'])
        parser=a.parser.resolve()/'assessment.json';parsed=json.loads(parser.read_text());verify(parsed['artifacts'])
        if parsed['parser_warnings'] or parsed['input_sha256'].get(str(view_receipt))!=sha(view_receipt):raise ValueError('matching clean native library parser review required')
        sdc, spef = phase/'enabled_phase.sdc', timing/'fixed_divide16/route.nom.normalized.spef'
        for path in (sdc, spef):
            if {**report['input_sha256'],**report['artifacts'],**ph['input_sha256'],**ph['artifacts']}.get(str(path)) != sha(path):
                raise ValueError('unverified diagnostic constraints or routed RC')
        diode = ROOT / 'build/timing400/release_001/antenna_diode_load_001/antenna_diode_load.lib'
        paths = [Path(__file__).resolve(), Path(sys.executable), Path(OPENROAD), LIB, LEF, TECH, RC_MODEL,
                 source / 'route.odb', source / 'route.v', source / 'assessment.json',
                 timing / 'assessment.json', sdc, spef, placement / 'assessment.json', diode,
                 ROOT / 'verification/signoff400/compiled_charge_v2.py', ROOT / 'verification/signoff400/resources.py',
                 Path(__file__).with_name('common_v3.py'), ROOT / 'verification/timing400/check_compact_mapping.py',
                 ROOT / 'verification/timing400/route_compact_candidate.py']
        libraries=[views/(c+'_'+v+'.lib') for c in ('tt','ff','ss','sf','fs') for v in ('early','late')]
        paths.extend([phase_receipt,view_receipt,parser,*libraries])
        pins = dict(candidate_sources, **{str(path): sha(path) for path in paths})
        liberty='define_corners tt ff ss sf fs\n'
        for corner in ('tt','ff','ss','sf','fs'):
            liberty+=f'read_liberty -corner {corner} -min {views}/{corner}_early.lib\nread_liberty -corner {corner} -max {views}/{corner}_late.lib\n'
        save(out / 'input_manifest.json', dict(input_sha256=pins))
        allowed = ' '.join(sorted(routed['cell_inventory']))
        actions='repair_design -slew_margin 20 -cap_margin 25 -verbose\n'
        if a.mode=='all':
            actions+='repair_timing -setup -setup_margin 0.05 -max_iterations 100 -skip_gate_cloning -skip_size_down -skip_buffer_removal -verbose\n'
            actions+='repair_timing -hold -hold_margin 0.05 -setup_margin 0.05 -max_iterations 100 -verbose\n'
        script = out / 'repair.tcl'
        script.write_text(f'''read_lef {TECH}
read_lef {LEF}
{liberty}
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
read_spef {out}/route.nom.spef
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
        if not set(inventory) <= set(routed['cell_inventory']):
            raise ValueError('unsupported master introduced during repair')
        verify(pins)
        save(out / 'assessment.json', dict(input_sha256=pins,
             artifacts={str(path): sha(path) for path in out.iterdir() if path.is_file() and path.name != 'status.json'},
             candidate_source_sha256=candidate_sources,related_fast_and_divided_clock_paths_preserved=True,
             cell_inventory=dict(inventory), digital_routing_completed=True, nominal_rc_extracted=True,
             router_drc_violations=0, database_power_grid_connected=True,
             native_five_corner_early_late_timing_repair_attempted=True,
             continuously_enabled_phase_constraints_used=True,full_startup_reset_disable_timing_qualified=False, repair_mode=a.mode, related_clock_paths_not_excluded=True,
             auxiliary_diode_load_is_conditional=True, final_parent_fill_and_interface_loading_included=False,
             digital_timing_qualified=False, physical_timing_qualified=False, assembled_macro_qualified=False,
             prototype_handoff_qualified=False, release_qualified=False))
        status('digital_route_completed_pending_independent_checks')
    except BaseException as error:
        status('physical_build_nonpass', reason=repr(error)); raise


if __name__ == '__main__':
    main()
