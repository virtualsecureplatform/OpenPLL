#!/usr/bin/env python3
"""Repair measured electrical driver sizes and fanout branches in a fresh candidate.

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
    p.add_argument('--repair-plan', required=True, type=Path)
    p.add_argument('--phase-timing',required=True,type=Path)
    p.add_argument('--native-views',required=True,type=Path)
    p.add_argument('--parser',required=True,type=Path)
    p.add_argument('--threads', type=int, choices=(1, 2, 4, 8, 16), default=4)
    p.add_argument('--mode', choices=('selective_data_pins',), default='selective_data_pins')
    a = p.parse_args()
    source, timing, placement, out = (x.resolve() for x in (a.route, a.timing, a.placement, a.output))
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 86400
    save(out / 'owner.json', dict(pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
         deadline_uptime=deadline, wall_limit_s=86400, internal_threads=a.threads, repair_mode=a.mode, automatic_identical_retry=False))

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
        from prototype_electrical_branch_eco_v7 import actions_for_plan
        plan_path=a.repair_plan.resolve()
        plan=json.loads(plan_path.read_text())
        verify(plan['input_sha256'])
        if plan['route_sha256'] != sha(source/'route.odb'):
            raise ValueError('interstage plan route mismatch')
        pins[str(plan_path)]=sha(plan_path)
        helper=Path(__file__).with_name('prototype_electrical_branch_eco_v7.py')
        pins[str(helper)]=sha(helper)
        planned_sizes={t['replacement_master'] for t in plan['targets']}
        for library in libraries:
            characterized=set(re.findall(r'cell \(([^)]+)\)',library.read_text()))
            if not planned_sizes<=characterized:raise ValueError('planned size lacks native early/late tables')
        allowed=' '.join(sorted(set(routed['cell_inventory'])|planned_sizes))
        for dependency in ('prototype_electrical_branch_eco.py','prototype_measured_path_eco.py'):
            dep=Path(__file__).with_name(dependency);pins[str(dep)]=sha(dep)
        actions=actions_for_plan(plan)
        save(out / 'input_manifest.json', dict(input_sha256=pins))
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
# Preserve taps/endcaps while allowing measured diode-only antenna repair.
foreach inst [$block getInsts] {{
 if {{[[$inst getMaster] getName] in {{sky130_fd_sc_hs__fill_1 sky130_fd_sc_hs__fill_2 sky130_fd_sc_hs__fill_4 sky130_fd_sc_hs__fill_8}}}} {{odb::dbInst_destroy $inst}}
}}
write_db {out}/pre_antenna.odb
repair_antennas sky130_fd_sc_hs__diode_2 -iterations 5 -ratio_margin 10 -diode_only
filler_placement {{sky130_fd_sc_hs__fill_8 sky130_fd_sc_hs__fill_4 sky130_fd_sc_hs__fill_2 sky130_fd_sc_hs__fill_1}}
global_connect
check_placement -verbose
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
# Fresh extracted SPEF is screened independently after NAME_MAP normalization.
# Do not report timing from the raw escaped SPEF here.
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
        if not set(inventory) <= (set(routed['cell_inventory'])|planned_sizes):
            raise ValueError('unsupported master introduced during repair')
        verify(pins)
        save(out / 'assessment.json', dict(input_sha256=pins,
             artifacts={str(path): sha(path) for path in out.iterdir() if path.is_file() and path.name != 'status.json'},
             candidate_source_sha256=candidate_sources,related_fast_and_divided_clock_paths_preserved=True,
             cell_inventory=dict(inventory), digital_routing_completed=True, nominal_rc_extracted=True,
             router_drc_violations=0, database_power_grid_connected=True,
             native_five_corner_early_late_timing_repair_attempted=False,
             measured_electrical_driver_and_branch_ECO_attempted=True,
             placement_parasitics_reestimated_after_electrical_and_setup_changes=False,
             final_extracted_timing_reported_by_this_run=False,
             continuously_enabled_phase_constraints_used=False,full_startup_reset_disable_timing_qualified=False, repair_mode=a.mode, related_clock_paths_not_excluded=True,
             auxiliary_diode_load_is_conditional=True, final_parent_fill_and_interface_loading_included=False,
             digital_timing_qualified=False, physical_timing_qualified=False, assembled_macro_qualified=False,
             prototype_handoff_qualified=False, release_qualified=False))
        status('digital_route_completed_pending_independent_checks')
    except BaseException as error:
        status('physical_build_nonpass', reason=repr(error)); raise


if __name__ == '__main__':
    main()
