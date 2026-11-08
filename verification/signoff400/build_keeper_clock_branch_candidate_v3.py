"""One isolated digital clock/data ECO; no promotion or timing qualification."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute
from bind_CDC_physical_instances import word
sys.path.append(str(ROOT / 'verification/timing400'))
from check_compact_mapping import TECH, LEF, OPENROAD
from route_compact_candidate import RC_MODEL

STAGES = ['clkbuf_regs_0_FINECLK', 'clkbuf_0_core.feedback_divider.CLKDIV_RETIMED_regs', 'clkbuf_3_7__f_core.feedback_divider.CLKDIV_RETIMED_regs', 'clkbuf_leaf_53_core.feedback_divider.CLKDIV_RETIMED_regs']
REMOVED = {0: ['hold133', 'hold145', 'hold148', 'hold155'], 1: ['hold141', 'hold182']}
DIVIDER = '$auto$ff.cc:337:slice$18687'
INVERTERS = {0:'$abc$73649$auto$blifparse.cc:397:parse_blif$73752',1:'$abc$73649$auto$blifparse.cc:397:parse_blif$76477'}


def projection(reports):
    records = []
    for corner in ['tt', 'ff', 'ss', 'sf', 'fs']:
        text = (reports / corner / 'native.log').read_text()
        for pair, removed in REMOVED.items():
            for kind in ['min', 'max']:
                begin, end = f'OPENPLL_PAIR_{pair}_{kind}_BEGIN', f'OPENPLL_PAIR_{pair}_{kind}_END'
                if text.count(begin) != 1 or text.count(end) != 1:
                    raise ValueError('complete full-clock report required')
                block = text.split(begin)[1].split(end)[0]
                data, clock = block.split('data arrival time', 1)
                def cells(section):
                    return {m[3]: (float(m[1]), m[4]) for m in re.finditer(r'^\s*([-+\d.eE]+)\s+([-+\d.eE]+)\s+[\^v]\s+(\S+)/\S+\s+\((sky130[^)]+)\)', section, re.M)}
                d, c = cells(data), cells(clock)
                if any(d[h][1] != 'sky130_fd_sc_hs__clkbuf_2' for h in removed) or any(c[h][1] != 'sky130_fd_sc_hs__clkbuf_16' for h in STAGES):
                    raise ValueError('expected non-inverting buffer topology required')
                if c[DIVIDER][1] != 'sky130_fd_sc_hs__dfrtp_4' or c[INVERTERS[pair]][1] != 'sky130_fd_sc_hs__clkinv_1':
                    raise ValueError('same divider and decision-clock inverter required')
                slack = float(re.search(r'([-+\d.eE]+)\s+slack \(', block)[1])
                advance = sum(c[h][0] for h in STAGES)
                reduction = sum(d[h][0] for h in removed)
                predicted = slack + (advance - reduction) * (1 if kind == 'min' else -1)
                records.append(dict(corner=corner, pair=pair, type=kind, baseline_slack_ns=slack, unchanged_arc_delta_estimate_ns=predicted))
    if len(records) != 20 or min(r['unchanged_arc_delta_estimate_ns'] for r in records) <= 0:
        raise ValueError('predeclared candidate has no positive conditional timing-delta screen')
    return records


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {28, 29})
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    b = ROOT / 'build/signoff400'
    source = b / 'prototype_v3_selected_route_019'
    reports = b / 'selected_keeper_critical_full_clock_paths_1449'
    views = b / 'prototype_v3_observed_reset_load_liberty_001'
    baseline = b / 'prototype_v3_selected_402p1_timing_tt_019/fixed_divide16/screen.sdc'
    try:
        evidence = reports / 'assessment.json'
        er = json.loads(evidence.read_text())
        verify(er['input_sha256'])
        verify(er['artifacts'])
        estimates = projection(reports)
        save(output / 'plan.json', dict(clock_tap=DIVIDER + '/Q', existing_inverters=INVERTERS, bypassed_clock_buffer_stages=STAGES, removed_noninverting_data_buffers=REMOVED, projected_checks=estimates, changed_loads_and_wires_ignored_in_projection=True, projected_margin_is_not_signoff=True, RTL_changed=False, timing_exceptions_added=False, release_ready=False))
        rules = {corner: Path(str(RC_MODEL).replace('.nom.', '.' + corner + '.')) for corner in ['min', 'nom', 'max']}
        paths = [source / 'route.odb', source / 'route.def', source / 'assessment.json', evidence, reports / 'paths.json', baseline, TECH, LEF, Path(OPENROAD), Path(__file__).resolve(), output / 'plan.json', *rules.values()]
        libraries = [views / (corner + '_' + edge + '.lib') for corner in ['tt','ff','ss','sf','fs'] for edge in ['early','late']]
        paths.extend(libraries)
        pins = {str(p): sha(p) for p in paths}
        libraries_tcl = 'define_corners tt ff ss sf fs\n'
        for corner in ['tt','ff','ss','sf','fs']:
            libraries_tcl += f'read_liberty -corner {corner} -min {views}/{corner}_early.lib\nread_liberty -corner {corner} -max {views}/{corner}_late.lib\n'
        remove_tcl = '\n'.join('bypass_buffer ' + word(name) for name in sum(REMOVED.values(), []))
        extract_tcl = f'define_process_corner -ext_model_index 0 RCX_NOM\nextract_parasitics -ext_model_file {rules["nom"]} -corner 0\nwrite_spef {output}/route.nom.spef'
        script = output / 'eco.tcl'
        script.write_text(f'''read_lef {TECH}
read_lef {LEF}
{libraries_tcl}
read_db {source}/route.odb
source {baseline}
set_thread_count 2
set block [ord::get_db_block]
write_verilog -include_pwr_gnd {output}/before.v
proc clear_wire {{net}} {{
 if {{[$net getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$net getWire]}}
}}
proc bypass_buffer {{name}} {{
 set block [ord::get_db_block]
 set inst [$block findInst $name]
 if {{$inst eq {{NULL}} || [[$inst getMaster] getName] ne {{sky130_fd_sc_hs__clkbuf_2}}}} {{error "expected data buffer missing"}}
 set in [[$inst findITerm A] getNet]
 set out [[$inst findITerm X] getNet]
 if {{$in eq $out || [llength [$out getBTerms]]!=0}} {{error "unsafe buffer boundary"}}
 clear_wire $in
 clear_wire $out
 foreach term [$out getITerms] {{
  if {{[$term getInst] ne $inst}} {{$term disconnect; $term connect $in}}
 }}
 odb::dbInst_destroy $inst
 odb::dbNet_destroy $out
 puts "BYPASSED_BUFFER $name"
}}
set divider [$block findInst {word(DIVIDER)}]
set leaf [$block findInst {word(STAGES[-1])}]
if {{$divider eq {{NULL}} || $leaf eq {{NULL}}}} {{error "clock topology missing"}}
if {{[[$divider getMaster] getName] ne {{sky130_fd_sc_hs__dfrtp_4}}}} {{error "divider master differs"}}
set old_clock [[$leaf findITerm X] getNet]
set new_clock [[$divider findITerm Q] getNet]
if {{$new_clock eq $old_clock}} {{error "clock tap did not change"}}
set inv_inputs {{}}
foreach name {{{' '.join(word(v) for v in INVERTERS.values())}}} {{
 set inv [$block findInst $name]
 if {{$inv eq {{NULL}} || [[$inv getMaster] getName] ne {{sky130_fd_sc_hs__clkinv_1}}}} {{error "decision clock inverter differs"}}
 set input [$inv findITerm A]
 if {{[$input getNet] ne $old_clock}} {{error "clock leaf attachment differs"}}
 lappend inv_inputs $input
}}
global_route -start_incremental
clear_wire $old_clock
clear_wire $new_clock
foreach input $inv_inputs {{$input disconnect; $input connect $new_clock}}
{remove_tcl}
filler_placement {{sky130_fd_sc_hs__fill_8 sky130_fd_sc_hs__fill_4 sky130_fd_sc_hs__fill_2 sky130_fd_sc_hs__fill_1}}
add_global_connection -net VDD -inst_pattern {{.*}} -pin_pattern {{^(VPWR|VPB)$}} -power
add_global_connection -net VSS -inst_pattern {{.*}} -pin_pattern {{^(VGND|VNB)$}} -ground
global_connect
check_placement -verbose
global_route -end_incremental -congestion_iterations 100
detailed_route -output_drc {output}/route.drc -output_maze {output}/route.maze.log -output_guide_coverage {output}/route.coverage
write_db {output}/route.odb
write_def {output}/route.def
write_verilog -include_pwr_gnd {output}/powered.v
write_abstract_lef {output}/digital.lef
{extract_tcl}
puts KEEPER_CLOCK_BRANCH_CANDIDATE_COMPLETE
exit
''')
        pins[str(script)] = sha(script)
        save(output / 'inputs.json', dict(input_sha256=pins, CPUs=[28,29], memory_GiB=8, native_cap_s=3600, resource_queue_cap_s=86400,maximum_routing_cases=1,maximum_native_tool_invocations=3, automatic_identical_retry=False, selected=False, release_ready=False))
        os.environ.update(OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1', GOMAXPROCS='2')
        save(output / 'status.json', dict(state='waiting_for_candidate_resource_budget', release_ready=False))
        queue_deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 86400
        extraction_scripts = {}
        for corner in ['min','max']:
            target=output/('extract_'+corner+'.tcl')
            target.write_text(f'read_db {output}/route.odb\nset_thread_count 2\ndefine_process_corner -ext_model_index 0 RCX_{corner.upper()}\nextract_parasitics -ext_model_file {rules[corner]} -corner 0\nwrite_spef {output}/route.{corner}.spef\nexit\n')
            extraction_scripts[corner]=target
            pins[str(target)]=sha(target)
        save(output/'inputs.json',dict(input_sha256=pins,CPUs=[28,29],memory_GiB=8,resource_queue_cap_s=86400,native_and_RC_export_cap_s=3600,maximum_routing_cases=1,maximum_native_tool_invocations=3,automatic_identical_retry=False,selected=False,release_ready=False))
        with lease(2,8,queue_deadline):
            deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
            save(output/'status.json',dict(state='routing_isolated_clock_branch_candidate',release_ready=False))
            execute([OPENROAD,'-no_init','-exit',script],output/'native.log',deadline,8)
            for corner,target in extraction_scripts.items():
                save(output/'status.json',dict(state='extracting_fresh_candidate_wire_RC',corner=corner,release_ready=False))
                execute([OPENROAD,'-no_init','-exit',target],output/('extract_'+corner+'.log'),deadline,8)
        verify(pins)
        log = (output / 'native.log').read_text()
        if 'KEEPER_CLOCK_BRANCH_CANDIDATE_COMPLETE' not in log or '[ERROR' in log:
            raise ValueError('native candidate route incomplete')
        targets = [output/name for name in ['before.v','powered.v','route.odb','route.def','digital.lef','route.drc','route.min.spef','route.nom.spef','route.max.spef','native.log']]
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in targets},native_candidate_route_completed=True,selected=False,logical_equivalence_verified=False,DRC_LVS_qualified=False,post_route_timing_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='candidate_route_complete_verification_pending',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False))
        raise


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    run(a.output.resolve())
