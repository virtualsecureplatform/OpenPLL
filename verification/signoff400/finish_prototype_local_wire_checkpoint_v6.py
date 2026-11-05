"""Finish a branch-ECO checkpoint while retaining unaffected signal routing.

Existing special power wires, taps, placements and logical connections remain.
The original checkpoint deadline is retained. All postroute signoff is separate.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import sys
import time
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge_v2 import execute
from select_prototype_local_ECO_routes import route_records
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import LIB,LEF,TECH,OPENROAD
from route_compact_candidate import RC_MODEL


def run(checkpoint,source,plan,phase,output,selection_reuse=None,eco_namespace=None):
    if not eco_namespace or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',eco_namespace):raise ValueError('safe ECO namespace required')
    manifest=checkpoint/'input_manifest.json';owner=checkpoint/'owner.json'
    m=json.loads(manifest.read_text());verify(m['input_sha256'])
    rr=source/'assessment.json';r=json.loads(rr.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    repair=json.loads(plan.read_text());verify(repair['input_sha256'])
    if repair['targets'] or repair['branches'] or repair.get('short_data_targets'):raise ValueError('upper local guidance supports this buffer/pair-only checkpoint')
    if eco_namespace+'_' in (source/'route.v').read_text():raise ValueError('namespace must be new relative to source')
    upper_nets=[f'{eco_namespace}_source_{i}_net' for i in range(len(repair.get('source_buffers',[])))]
    upper_nets += [f'{eco_namespace}_pair_{i}_{stage}_net' for i in range(len(repair.get('source_inverter_pairs',[]))) for stage in (0,1)]
    if not upper_nets:raise ValueError('nonempty new local nets required')
    db=checkpoint/'pre_antenna.odb';sdc=phase/'enabled_phase.sdc'
    required=(rr,source/'route.odb',plan,sdc)
    if (any(m['input_sha256'].get(str(p))!=sha(p) for p in required)
            or repair['route_sha256']!=sha(source/'route.odb')):
        raise ValueError('checkpoint does not pin the source, plan and phase constraints')
    deadline=json.loads(owner.read_text())['deadline_uptime']
    if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise ValueError('original checkpoint deadline expired')
    inputs=dict(m['input_sha256']);inputs.update({str(p):sha(p) for p in
        (manifest,owner,db,checkpoint/'repair.log',Path(__file__).resolve(),Path(OPENROAD),LIB,LEF,TECH,RC_MODEL,
         Path(__file__).with_name('common_v3.py'),Path(__file__).with_name('resources.py'),Path(__file__).with_name('compiled_charge_v2.py'))})
    output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),deadline_uptime=deadline,original_deadline_preserved=True,
        checkpoint=str(db),cpu_slots=4,memory_GiB=8,automatic_identical_retry=False))
    def status(state,**kw):save(output/'status.json',dict(state=state,release_ready=False,**kw))
    selector=Path(__file__).with_name('select_prototype_fixed_logic_incident_routes.py')
    config=output/'selection_config.json'
    selection=selection_reuse if selection_reuse is not None else output/'local_selection'
    save(config,dict(source=str(source),checkpoint=str(checkpoint),output=str(selection),selection_mode='incident_only_fixed_logic'))
    inputs.update({str(p):sha(p) for p in (selector,config)})
    os.environ['OPENPLL_LOCAL_ECO_CONFIG']=str(config)
    if selection_reuse is None:
        try:
            status('selecting_incident_routes_with_existing_logic_fixed')
            with lease(1,8,deadline):execute([OPENROAD,'-no_init','-python','-exit',selector],output/'selection.log',deadline,8)
        except BaseException as error:
            status('stopped_without_qualification',reason=repr(error));raise
    selected=json.loads((selection/'assessment.json').read_text())
    verify(selected['input_sha256']);verify(selected['artifacts'])
    if (selected.get('selection_mode')!='incident_only_fixed_logic'
            or selected['input_sha256'].get(str(rr))!=sha(rr)
            or selected['input_sha256'].get(str(checkpoint/'assessment.json'))!=sha(checkpoint/'assessment.json')
            or selected['input_sha256'].get(str(db))!=sha(db)):
        raise ValueError('retained selection does not match the same checkpoint and route')
    if selected['retained_signal_wires']<=0 or selected['dirty_signal_nets']<=0:
        raise ValueError('nonempty local repair and retained routes required')
    inputs.update(selected['input_sha256'])
    inputs.update({str(p):sha(p) for p in (selection/'assessment.json',selection/'dirty_nets.tcl',selection/'local_unrouted.odb')})
    upper_names=output/'upper_local_nets.tcl'
    upper_names.write_text('set local_eco_upper_nets [list '+' '.join('{'+n+'}' for n in sorted(upper_nets))+']\n')
    upper_db=output/'upper_local_guides.odb';upper_script=output/'upper_route.tcl'
    upper_script.write_text(f'''read_lef {{{TECH}}}
read_lef {{{LEF}}}
read_liberty {{{LIB}}}
read_db {{{selection/'local_unrouted.odb'}}}
source {{{sdc}}}
set_thread_count 4
set block [ord::get_db_block]
set_routing_layers -signal met3-met4 -clock met3-met4
set_wire_rc -signal -layer met3
set_wire_rc -clock -layer met3
source {{{selection/'dirty_nets.tcl'}}}
source {{{upper_names}}}
foreach name $local_eco_upper_nets {{
 if {{[lsearch -exact $local_eco_dirty_nets $name]<0}} {{error "upper local net is not selected"}}
 set net [$block findNet $name]
 if {{$net eq {{NULL}} || [$net getSigType] in {{POWER GROUND}}}} {{error "invalid upper local net"}}
 grt::add_net_to_route $net
}}
global_route -allow_congestion -guide_file {{{output/'upper.guide'}}} -congestion_iterations 100 -verbose
write_db {{{upper_db}}}
puts "UPPER_LOCAL_GUIDANCE_COMPLETE"
exit
''')
    inputs.update({str(f):sha(f) for f in (upper_names,upper_script)})
    upper_inputs=dict(inputs);save(output/'upper_input_manifest.json',dict(input_sha256=upper_inputs))
    os.environ.update(OMP_NUM_THREADS='4',GOMAXPROCS='4',OPENBLAS_NUM_THREADS='1')
    try:
        status('guiding_new_local_nets_on_upper_layers')
        with lease(4,8,deadline):execute([OPENROAD,'-no_init','-exit',upper_script],output/'upper_route.log',deadline,8)
        if 'UPPER_LOCAL_GUIDANCE_COMPLETE' not in (output/'upper_route.log').read_text():raise ValueError('upper guidance incomplete')
        verify(upper_inputs)
        save(output/'upper_route_assessment.json',dict(input_sha256=upper_inputs,
            artifacts={str(f):sha(f) for f in (upper_db,output/'upper.guide',output/'upper_route.log')},
            requested_upper_local_nets=len(upper_nets),requested_layers=['met3','met4'],digital_routing_completed=False,release_ready=False))
    except BaseException as error:
        status('stopped_without_qualification',reason=repr(error));raise
    inputs.update({str(f):sha(f) for f in (upper_db,output/'upper_route_assessment.json',output/'upper_input_manifest.json')})
    script=output/'route.tcl'
    script.write_text(f'''read_lef {{{TECH}}}
read_lef {{{LEF}}}
read_liberty {{{LIB}}}
read_db {{{upper_db}}}
source {{{sdc}}}
set_thread_count 4
set_propagated_clock [all_clocks]
set block [ord::get_db_block]
source {{{selection/'dirty_nets.tcl'}}}
source {{{upper_names}}}
foreach name $local_eco_dirty_nets {{
 if {{[lsearch -exact $local_eco_upper_nets $name]>=0}} {{continue}}
 set net [$block findNet $name]
 if {{$net eq {{NULL}} || [$net getSigType] in {{POWER GROUND}}}} {{error "invalid local ECO net $name"}}
 grt::add_net_to_route $net
}}
puts "LOCAL_ECO_SELECTED_NETS=[llength $local_eco_dirty_nets]"
set_routing_layers -signal met1-met4 -clock met2-met4
set_wire_rc -signal -layer met2
set_wire_rc -clock -layer met3
add_global_connection -net VDD -inst_pattern {{.*}} -pin_pattern {{^(VPWR|VPB)$}} -power
add_global_connection -net VSS -inst_pattern {{.*}} -pin_pattern {{^(VGND|VNB)$}} -ground
global_connect
check_placement -verbose
global_route -allow_congestion -guide_file {{{output/'global.guide'}}} -congestion_iterations 100 -verbose
write_db {{{output/'global_before_antenna.odb'}}}
# Existing protection and measured local diode repairs are retained.
# Automatic diode insertion would change loads beyond this measured ECO plan.
global_connect
write_db {{{output/'antenna_repaired.odb'}}}
filler_placement {{sky130_fd_sc_hs__fill_8 sky130_fd_sc_hs__fill_4 sky130_fd_sc_hs__fill_2 sky130_fd_sc_hs__fill_1}}
global_connect
check_placement -verbose
detailed_route -drc_report_iter_step 1 -output_drc {{{output/'route.drc'}}} -output_maze {{{output/'route.maze.log'}}} -output_guide_coverage {{{output/'route.coverage'}}}
write_db {{{output/'route.odb'}}}
write_def {{{output/'route.def'}}}
write_verilog {{{output/'route.v'}}}
write_verilog -include_pwr_gnd {{{output/'powered.v'}}}
write_abstract_lef {{{output/'digital.lef'}}}
check_antennas -report_file {{{output/'antenna.rpt'}}}
check_power_grid -net VDD -error_file {{{output/'vdd_errors.rpt'}}}
check_power_grid -net VSS -error_file {{{output/'vss_errors.rpt'}}}
define_process_corner -ext_model_index 0 RCX_NOM
extract_parasitics -ext_model_file {{{RC_MODEL}}} -corner 0
write_spef {{{output/'route.nom.spef'}}}
set f [open {{{output/'masters.txt'}}} w]
foreach inst [$block getInsts] {{puts $f [[$inst getMaster] getName]}}
close $f
puts "CHECKPOINT_SIGNAL_ROUTE_COMPLETE"
exit
''')
    inputs[str(script)]=sha(script);save(output/'input_manifest.json',dict(input_sha256=inputs))
    os.environ.update(OMP_NUM_THREADS='4',GOMAXPROCS='4',OPENBLAS_NUM_THREADS='1')
    try:
        status('local_global_and_detailed_signal_routing_running')
        with lease(4,8,deadline):execute([OPENROAD,'-no_init','-exit',script],output/'route.log',deadline,8)
        text=(output/'route.log').read_text();counts=re.findall(r'Number of violations = (\d+)',text)
        if ('CHECKPOINT_SIGNAL_ROUTE_COMPLETE' not in text or not counts or counts[-1]!='0'
                or (output/'route.drc').stat().st_size):raise ValueError('completed zero-DRC detailed route required')
        if not all(f'All shapes on net {n} are connected.' in text for n in ('VDD','VSS')):
            raise ValueError('PG connectivity failed')
        inventory=Counter((output/'masters.txt').read_text().splitlines())
        allowed=set(r['cell_inventory'])|{t['replacement_master'] for t in repair['targets']}|{'sky130_fd_sc_hs__diode_2'}
        allowed.update(t['buffer_master'] for t in repair.get('source_buffers',[]))
        allowed.update(t[k] for t in repair.get('source_inverter_pairs',[]) for k in ('first_master','second_master'))
        if repair.get('short_data_targets'):allowed.add('sky130_fd_sc_hs__clkbuf_2')
        if not set(inventory)<=allowed:raise ValueError('unreviewed cell master introduced')
        old_routes=route_records((source/'route.def').read_text())
        new_routes=route_records((output/'route.def').read_text())
        unchanged=sum(new_routes.get(name)==record for name,record in old_routes.items())
        if not unchanged:raise ValueError('local route preserved no original DEF routing records')
        verify(inputs)
        save(output/'assessment.json',dict(input_sha256=inputs,
            artifacts={str(p):sha(p) for p in output.iterdir() if p.is_file() and p.name!='status.json'},
            candidate_source_sha256=r['candidate_source_sha256'],cell_inventory=dict(inventory),
            digital_routing_completed=True,nominal_rc_extracted=True,router_drc_violations=0,
            database_power_grid_connected=True,related_fast_and_divided_clock_paths_preserved=True,
            automatic_global_diode_insertion=False,
            coarse_global_congestion_permitted_for_native_detailed_repair=True,
            retained_selection_reused=selection_reuse is not None,
            native_DRC_report_interval=1,
            new_local_nets_guided_on_upper_layers=len(upper_nets),
            requested_upper_local_layers=['met3','met4'],
            local_route_selection_sha256=sha(selection/'assessment.json'),
            retained_signal_wires_before_detailed_route=selected['retained_signal_wires'],
            dirty_signal_nets=selected['dirty_signal_nets'],
            original_DEF_routing_records=len(old_routes),
            final_DEF_routing_records=len(new_routes),
            unchanged_DEF_routing_records=unchanged,
            independent_antenna_recheck_required=True,
            checkpoint_resumed_without_reapplying_logical_ECO=True,original_deadline_preserved=True,
            supplied_library_used_for_physical_routing_only=True,auxiliary_diode_load_is_conditional=True,
            digital_timing_qualified=False,physical_timing_qualified=False,release_ready=False))
        status('route_complete_independent_checks_pending')
    except BaseException as error:
        status('stopped_without_qualification',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('checkpoint','source','plan','phase','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--selection-reuse',type=Path)
    p.add_argument('--eco-namespace',required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ('checkpoint','source','plan','phase','output')),
        selection_reuse=a.selection_reuse.resolve() if a.selection_reuse else None,eco_namespace=a.eco_namespace)
