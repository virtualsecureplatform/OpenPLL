"""Screen the routed fixed-divider candidate with its inductively proved clock ratio."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge import execute

OPENROAD='/nix/store/qqz49dx8dpx4q9i5wriif091n7iaa0ld-openroad-2026-02-17/bin/openroad'


def run(route,placement,proof,output,candidate,divider_proof,divider_negative):
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
    lib=next(Path(p) for p in records[0]['input_sha256'] if p.endswith('.lib'))
    image=ROOT/'build/apptainer/openpll-release-modern.sif';sdc=placement/'diagnostic.sdc'
    text=sdc.read_text()
    if text.count('-divide_by 16')!=1 or 'set_false_path -from $left -to $right' not in text:raise ValueError('expected explicit capacity-screen clock constraints')
    output.mkdir(parents=True,exist_ok=False);pins={str(p):sha(p) for p in (*receipts,*extra,route/'route.odb',route/'route.nom.spef',sdc,lib,Path(__file__).resolve())}
    # Called within the pinned image so all native tool/library inputs can be verified.
    pins[OPENROAD]=sha(OPENROAD)
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    artifacts={}
    for mode,divide in [('fixed_divide16',16)]:
        folder=output/mode;folder.mkdir();constraints=folder/'screen.sdc';constraints.write_text(text.replace('-divide_by 16',f'-divide_by {divide}'))
        script=folder/'screen.tcl'
        script.write_text(f'''read_liberty {lib}
read_db {route}/route.odb
source {constraints}
set_thread_count 1
set_propagated_clock [all_clocks]
read_spef {route}/route.nom.spef
report_worst_slack -max
report_worst_slack -min
report_checks -path_delay max -group_path_count 5 -digits 6
report_checks -path_delay min -group_path_count 5 -digits 6
foreach pair {{{{PLLOUT FINECLK}} {{FINECLK PLLOUT}} {{FINECLK FINECLK}}}} {{
 lassign $pair source target
 puts "RELATED_CLOCK_PAIR $source $target"
 report_checks -from [get_clocks $source] -to [get_clocks $target] -path_delay min_max -group_path_count 5 -digits 6
}}
report_check_types -max_slew -max_capacitance -min_pulse_width -violators
check_setup -verbose
exit
''')
        with lease(1,4,deadline):execute([OPENROAD,'-exit',script],folder/'screen.log',deadline,4)
        artifacts.update({str(p):sha(p) for p in (constraints,script,folder/'screen.log')})
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
        related_clock_modes_screened=['fixed_divide16_entire_enabled_lifecycle'],constant_clock_ratio_inductively_proved=True,related_fast_and_divided_clock_paths_preserved=True,
        clock_capacity_mhz=500,supplied_library_temperature_c=25,propagated_clocks_and_routed_nominal_RC=True,
        native_timing_views_qualified=False,actual_clock_range_qualified=False,reset_and_async_paths_qualified=False,
        physical_timing_qualified=False,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('route','placement','proof','output','candidate','divider-proof','divider-negative'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();run(a.route.resolve(),a.placement.resolve(),a.proof.resolve(),a.output.resolve(),a.candidate.resolve(),a.divider_proof.resolve(),a.divider_negative.resolve())
