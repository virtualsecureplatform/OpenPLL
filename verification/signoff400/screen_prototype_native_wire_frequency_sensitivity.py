"""Screen the routed fixed-divider candidate with its inductively proved clock ratio."""
import argparse,json,os,time,re,sys
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_routed_timing import normalize_spef
from resources import lease
from compiled_charge import execute

OPENROAD='/nix/store/qqz49dx8dpx4q9i5wriif091n7iaa0ld-openroad-2026-02-17/bin/openroad'


def run(route,placement,proof,output,candidate,divider_proof,divider_negative,native_views,parser,corner,wire_views,clock_mhz):
    receipts=[p/'assessment.json' for p in (route,placement,proof)]
    extra=[p/'assessment.json' for p in (candidate,divider_proof,divider_negative)]
    cr,dr,nr=[json.loads(p.read_text()) for p in extra]
    for r in (cr,dr,nr):verify(r['input_sha256']);verify(r['artifacts'])
    if not dr.get('inductive_constant_divider_output_equivalence') or dr['ratio']!=16 or not nr.get('incorrect_ratio15_rejected'):raise ValueError('inductive divider proof and negative control required')
    if nr['input_sha256'].get(str(extra[1]))!=sha(extra[1]):raise ValueError('divider negative control mismatch')
    sources=cr['candidate_source_sha256']
    programmed=next(Path(p) for p in sources if p.endswith('/IntegerPLL_ProgrammedCore.v'))
    mmd=next(Path(p) for p in sources if p.endswith('/IntegerPLL_MMD_Retimer.v'))
    if not any(p.endswith('/IntegerPLL_MMD_Retimer.v') and digest==sha(mmd) for p,digest in dr['input_sha256'].items()):raise ValueError('divider source proof mismatch')
    text=programmed.read_text()
    for token in ('.MMD_REGISTER_CONFIG(0)','.MMD_CONFIG_PIPELINE(0)',".MMDCLKDIV_RATIO({3'b000,FEEDBACK_DIVIDER})","localparam [4:0] FEEDBACK_DIVIDER = 5'd16;",'.MMD_RATIO_WIDTH(5)','.MMD_COUNTDOWN(1)'):
        if text.count(token)!=1:raise ValueError('constant-divider integration differs from proved configuration')
    records=[json.loads(p.read_text()) for p in receipts]
    for r in records:verify(r['input_sha256']);verify(r['artifacts'])
    if records[0]['candidate_source_sha256']!=sources:raise ValueError('route candidate identity mismatch')
    if not records[0]['digital_routing_completed'] or not records[2]['all_transition_and_output_functions_equivalent']:raise ValueError('proved routed candidate required')
    if records[2]['input_sha256'].get(str(route/'route.v'))!=sha(route/'route.v'):raise ValueError('equivalence route mismatch')
    vr=native_views/'assessment.json';pr=parser/'assessment.json'
    v,parsed=[json.loads(p.read_text()) for p in (vr,pr)]
    verify(v['artifacts']);verify(parsed['artifacts'])
    if not v['all_native_capture_constraint_sets_included'] or not parsed['every_library_cell_inventory_and_FF_functional_pin_verified'] or parsed['parser_warnings']:
        raise ValueError('complete parsed native timing and constraint views required')
    if parsed['input_sha256'].get(str(vr))!=sha(vr):raise ValueError('native library parser lineage differs')
    wr=wire_views/'assessment.json';w=json.loads(wr.read_text())
    verify(w['input_sha256']);verify(w['artifacts'])
    if (w['input_sha256'].get(str(route/'route.odb'))!=sha(route/'route.odb')
            or w['wire_views']!=['min','nom','max']
            or not w['all_terminal_inventories_match_routed_nominal']
            or not w['all_wire_terminals_resistively_connected']
            or not w['cell_pin_capacitance_excluded']):
        raise ValueError('same-route checked min/nom/max wire views required')
    lib=native_views/(corner+'_late.lib');early=native_views/(corner+'_early.lib')
    if any(v['artifacts'].get(str(p))!=sha(p) for p in (lib,early)):raise ValueError('native corner library changed')
    extra_libraries=[]
    image=ROOT/'build/apptainer/openpll-release-modern.sif';sdc=placement/'diagnostic.sdc'
    text=sdc.read_text()
    if text.count('-divide_by 16')!=1 or 'set_false_path -from $left -to $right' not in text:raise ValueError('expected explicit capacity-screen clock constraints')
    if not 400 <= clock_mhz <= 500:raise ValueError('frequency sensitivity must remain within 400–500 MHz')
    if text.count('create_clock -name PLLOUT -period 2.0 [get_ports PLLOUT]')!=1:raise ValueError('unique fast-clock definition required')
    text=text.replace('create_clock -name PLLOUT -period 2.0 [get_ports PLLOUT]',f'create_clock -name PLLOUT -period {1000/clock_mhz:.12g} [get_ports PLLOUT]')
    output.mkdir(parents=True,exist_ok=False);pins={str(p):sha(p) for p in (*receipts,*extra,vr,pr,early,*extra_libraries,route/'route.odb',route/'route.nom.spef',sdc,lib,Path(__file__).resolve())}
    # Called within the pinned image so all native tool/library inputs can be verified.
    pins[OPENROAD]=sha(OPENROAD)
    pins[str(wr)]=sha(wr)
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    artifacts={}
    for mode,divide in [('fixed_divide16',16)]:
        folder=output/mode;folder.mkdir();constraints=folder/'screen.sdc';constraints.write_text(text.replace('-divide_by 16',f'-divide_by {divide}'))
        normalized,count=normalize_spef((route/'route.nom.spef').read_text())
        normalized_spef=folder/'route.nom.normalized.spef';normalized_spef.write_text(normalized)
        pins[str(normalized_spef)]=sha(normalized_spef)
        normalizer=ROOT/'verification/timing400/check_compact_routed_timing.py';pins[str(normalizer)]=sha(normalizer)
        wires={}
        for rc_corner in ('min','max'):
            raw=wire_views/(rc_corner+'.spef');pins[str(raw)]=sha(raw)
            fixed,number=normalize_spef(raw.read_text())
            target=folder/('route.'+rc_corner+'.normalized.spef');target.write_text(fixed)
            pins[str(target)]=sha(target);wires[rc_corner]=target
        script=folder/'screen.tcl'
        extra_liberty='read_liberty -min '+str(early)
        script.write_text(f'''read_liberty -max {lib}
{extra_liberty}
read_db {route}/route.odb
source {constraints}
set_thread_count 1
set_propagated_clock [all_clocks]
read_spef -min {wires['min']}
read_spef -max {wires['max']}
report_parasitic_annotation -report_unannotated
report_worst_slack -max
report_worst_slack -min
report_checks -path_delay max -group_path_count 5 -digits 6
report_checks -path_delay min -group_path_count 5 -digits 6
foreach pair {{{{PLLOUT FINECLK}} {{FINECLK PLLOUT}} {{FINECLK FINECLK}}}} {{
 lassign $pair source target
 puts "RELATED_CLOCK_PAIR $source $target"
 report_checks -from [get_clocks $source] -to [get_clocks $target] -path_delay min_max -group_path_count 5 -digits 6
}}
report_check_types -max_slew -max_capacitance -min_pulse_width -recovery -removal -violators -digits 6
check_setup -verbose
exit
''')
        with lease(1,4,deadline):execute([OPENROAD,'-exit',script],folder/'screen.log',deadline,4)
        log=(folder/'screen.log').read_text()
        if re.search(r'STA-(1648|1650)',log):raise ValueError('unresolved SPEF node or instance binding')
        worst={kind:float(value) for kind,value in re.findall(r'worst slack (max|min) ([-+0-9.eE]+)',log)}
        if set(worst)!={'max','min'}:raise ValueError('missing setup/hold worst-slack result')
        reported_pass=all(value>=0 for value in worst.values()) and 'VIOLATED' not in log
        artifacts.update({str(p):sha(p) for p in (constraints,script,normalized_spef,folder/'screen.log',*wires.values())})
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
        related_clock_modes_screened=['fixed_divide16_entire_enabled_lifecycle'],constant_clock_ratio_inductively_proved=True,related_fast_and_divided_clock_paths_preserved=True,
        SPEF_clock_buffer_name_entries_normalized=count,no_SPEF_name_binding_warnings=True,
        corner_worst_slack_ns=worst,all_corner_reported_checks_passed=reported_pass,clock_capacity_mhz=clock_mhz,frequency_sensitivity_only=True,native_model_corner=corner,native_model_temperature_c=27,propagated_clocks_and_routed_nominal_RC=False,minmax_wire_RC_used=True,wire_RC_screening="min_for_early_max_for_late",
        supplied_pin_capacitance_envelope_screen=True,conditional_TT_antenna_diode_capacitance_used=True,native_early_and_late_propagation_and_capture_views_used=True,native_timing_views_qualified=False,actual_clock_range_qualified=False,reset_and_async_paths_qualified=False,
        physical_timing_qualified=False,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('route','placement','proof','output','candidate','divider-proof','divider-negative','native-views','parser','wire-views'):p.add_argument('--'+n,required=True,type=Path)
    p.add_argument('--corner',required=True,choices=('tt','ff','ss','sf','fs'))
    p.add_argument('--clock-mhz',required=True,type=float)
    a=p.parse_args();run(a.route.resolve(),a.placement.resolve(),a.proof.resolve(),a.output.resolve(),a.candidate.resolve(),a.divider_proof.resolve(),a.divider_negative.resolve(),a.native_views.resolve(),a.parser.resolve(),a.corner,a.wire_views.resolve(),a.clock_mhz)
