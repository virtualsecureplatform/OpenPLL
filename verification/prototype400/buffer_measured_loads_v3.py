#!/usr/bin/env python3
"""Repair routed timing/electrical violations in a fresh diagnostic candidate.

No RTL changes or new timing exceptions. Independent equivalence, DRC, LVS,
antenna and renewed timing checks remain mandatory before route selection.
"""
import argparse
import ast
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
from audit_timing_annotation import block
from repair_measured_antennas import tcl_word


def noninverting_identity(expression):
    try:tree=ast.parse(expression.strip(),mode='eval').body
    except SyntaxError:return False
    return isinstance(tree,ast.Name) and tree.id=='A'


def measured_electrical_targets(text):
    kind=None;rows=[]
    for line in text.splitlines():
        words=line.split()
        if words[:2]==['Pin','Limit']:
            kind={'Cap':'capacitance_pf','Slew':'slew_ns'}.get(words[2]) if len(words)>2 else None
            continue
        if words[:1]==['Pin'] or line.startswith('Startpoint:'):kind=None
        match=re.fullmatch(r'\s*(\S+)\s+([0-9.]+)\s+([0-9.]+)\s+(-[0-9.]+)\s+\(VIOLATED\)\s*',line)
        if kind and match:
            rows.append(dict(pin=match[1],kind=kind,limit=float(match[2]),actual=float(match[3])))
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('route', 'timing', 'placement', 'output'):
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--threads', type=int, choices=(1, 2, 4, 8, 16), default=8)
    p.add_argument('--buffer-strength', type=int, choices=(4,8,16), default=16)
    a = p.parse_args()
    source, timing, placement, out = (x.resolve() for x in (a.route, a.timing, a.placement, a.output))
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 43200
    save(out / 'owner.json', dict(pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
         deadline_uptime=deadline, wall_limit_s=43200, internal_threads=a.threads, repair_mode='measured_buffer_isolation', routing_strategy='fresh_all_signal_routes', automatic_identical_retry=False))

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
        observed=[]
        for label in report['results']:
            if label.startswith('tt_25C_1v80_'):
                observed+=measured_electrical_targets((timing/(label+'.log')).read_text())
        cap=[row['actual'] for row in observed if row['kind']=='capacitance_pf']
        if not cap:raise ValueError('no measured nominal-voltage capacitance violation')
        master='sky130_fd_sc_hs__buf_'+str(a.buffer_strength)
        cell=block(LIB.read_text(),'cell',master);output_pin=block(cell,'pin','X')
        function=re.search(r'\bfunction\s*:\s*"([^"\n]+)"\s*;',output_pin)
        if not function or not noninverting_identity(function[1]):raise ValueError('buffer is not noninverting')
        maximum=re.search(r'max_capacitance\s*:\s*([0-9.]+)',output_pin)
        if not maximum or float(maximum[1])<max(cap)*1.25:raise ValueError('buffer capacity does not enclose measured load')
        pins[str(Path(__file__).with_name('audit_timing_annotation.py'))]=sha(Path(__file__).with_name('audit_timing_annotation.py'))
        pins[str(Path(__file__).with_name('repair_measured_antennas.py'))]=sha(Path(__file__).with_name('repair_measured_antennas.py'))
        save(out/'input_manifest.json',dict(input_sha256=pins))
        save(out/'measured_targets.json',dict(rows=observed,buffer_master=master,buffer_max_capacitance_pf=float(maximum[1])))
        labels=sorted({row['pin'] for row in observed});targets=' '.join(tcl_word(name) for name in labels)
        prefix='measured_load_'+sha(source/'assessment.json')[:12]
        actions=f'''set targets {{}}
foreach label {{{targets}}} {{
 set slash [string last / $label]
 set inst [$block findInst [string range $label 0 [expr {{$slash-1}}]]]
 if {{$inst eq {{NULL}}}} {{error {{measured instance missing}}}}
 set term [$inst findITerm [string range $label [expr {{$slash+1}}] end]]
 if {{$term eq {{NULL}} || [$term getNet] eq {{NULL}}}} {{error {{measured net missing}}}}
 set net [$term getNet]
 if {{$net ni $targets}} {{lappend targets $net}}
}}
set index 0
set plan [open {out}/buffer_plan.tsv w]
foreach net $targets {{
 if {{[$net getSigType] ne {{SIGNAL}} || [llength [$net getBTerms]]!=0}} {{error {{only internal data nets are supported}}}}
 set drivers {{}};set sinks {{}}
 foreach term [$net getITerms] {{
  if {{[$term getIoType] eq {{OUTPUT}}}} {{lappend drivers $term}} elseif {{[$term getIoType] eq {{INPUT}}}} {{lappend sinks $term}} else {{error {{unexpected bidirectional data terminal}}}}
 }}
 if {{[llength $drivers]!=1 || [llength $sinks]==0}} {{error {{measured net lacks a unique driver and sinks}}}}
 set driver [lindex $drivers 0];set origin [$driver getInst]
 set master [[ord::get_db] findMaster {master}]
 if {{$master eq {{NULL}} || [$master getHeight]!=[[$origin getMaster] getHeight]}} {{error {{buffer row height mismatch}}}}
 set name {prefix}_$index
 if {{[$block findInst $name] ne {{NULL}} || [$block findNet ${{name}}_out] ne {{NULL}}}} {{error {{buffer ECO names already exist}}}}
 set buffer [odb::dbInst_create $block $master $name]
 set branch [odb::dbNet_create $block ${{name}}_out]
 $branch setSigType SIGNAL
 [$buffer findITerm A] connect $net
 [$buffer findITerm X] connect $branch
 foreach term $sinks {{$term disconnect;$term connect $branch}}
 if {{[llength [$net getITerms]]!=2 || [llength [$branch getITerms]]!=[llength $sinks]+1}} {{error {{fanout transfer mismatch}}}}
 $buffer setOrient [$origin getOrient]
 lassign [$origin getLocation] x y
 set die [$block getDieArea]
 set x [expr {{max([$die xMin],min($x,[$die xMax]-[$master getWidth]))}}]
 $buffer setLocation $x $y
 $buffer setPlacementStatus PLACED
 puts $plan [join [list [$net getName] [$origin getName] [[$driver getMTerm] getName] $name [llength $sinks]] [format %c 9]]
 if {{[$net getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$net getWire]}}
 incr index
}}
close $plan
puts "MEASURED_BUFFER_NETS=$index"
'''
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
# Apply the measured ECO before rebuilding all signal routing.
{actions}
detailed_placement
filler_placement {{sky130_fd_sc_hs__fill_8 sky130_fd_sc_hs__fill_4 sky130_fd_sc_hs__fill_2 sky130_fd_sc_hs__fill_1}}
add_global_connection -net VDD -inst_pattern {{.*}} -pin_pattern {{^(VPWR|VPB)$}} -power
add_global_connection -net VSS -inst_pattern {{.*}} -pin_pattern {{^(VGND|VNB)$}} -ground
global_connect
check_placement -verbose
foreach net [$block getNets] {{
 if {{[$net getSigType] ni {{POWER GROUND}} && [$net getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$net getWire]}}
}}
set_routing_layers -signal met1-met5 -clock met3-met5
set_global_routing_layer_adjustment met2 0.5
set_global_routing_layer_adjustment met3 0.5
global_route -verbose -guide_file {out}/route.guide -congestion_iterations 100
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
             supplied_view_timing_repair_attempted=True, repair_mode='measured_buffer_isolation', routing_strategy='fresh_all_signal_routes', related_clock_paths_not_excluded=True,
             auxiliary_diode_load_is_conditional=True, final_parent_fill_and_interface_loading_included=False,
             digital_timing_qualified=False, physical_timing_qualified=False, assembled_macro_qualified=False,
             prototype_handoff_qualified=False, release_qualified=False))
        status('digital_route_completed_pending_independent_checks')
    except BaseException as error:
        status('physical_build_nonpass', reason=repr(error)); raise


if __name__ == '__main__':
    main()
