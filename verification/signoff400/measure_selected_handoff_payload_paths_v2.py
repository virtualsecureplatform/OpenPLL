"""Measure selected REF snapshot-to-capture min/max delays at one corner.

Cross-clock exceptions are removed only for this explicit measurement. Reported
related-clock slacks do not qualify the asynchronous bundled-data capture budget.
"""
import argparse,json,os,re,time,subprocess
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from selected_physical_rtl import source_pins
from resources import lease
from compiled_charge import execute
from screen_prototype_decision_hold_phase_v3 import OPENROAD


def registers(module,alias):
    bits=module['netnames'][alias]['bits'];result=[]
    for bit in bits:
        if not isinstance(bit,int):continue
        matches=[name.lstrip('\\') for name,cell in module['cells'].items() if cell['connections'].get('Q')==[bit]]
        if not matches and not any(bit in pins for cell in module['cells'].values() for pins in cell['connections'].values()):continue
        if len(matches)!=1:raise ValueError('unique implemented state FF driver required')
        result.extend(matches)
    return sorted(set(result))


def run(baseline,inventory,output,bundle):
    os.sched_setaffinity(0,{28})
    selected=source_pins()
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    container_prefix=['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp',image]
    receipts=[p/'assessment.json' for p in (baseline,inventory)]
    b,i=[json.loads(p.read_text()) for p in receipts]
    for r in (b,i):verify(r['artifacts'])
    lineage={name:digest for name,digest in i['input_sha256'].items() if name.endswith('/assessment.json') and 'equivalence' in name}
    if len(lineage)!=1 or any(b['input_sha256'].get(name)!=digest for name,digest in lineage.items()):raise ValueError('route/proof lineage mismatch')
    routed=inventory/'routed.json';module=json.loads(routed.read_text())['modules']['IntegerPLL_ProgrammedCore']
    prefix='handoff' if bundle=='fast' else 'gen_feedback_handoff.fine_handoff'
    sources=registers(module,prefix+'.payload');targets=registers(module,prefix+'.APPLIED_COMMAND')
    if len(sources)!=30 or len(targets)!=(1 if bundle=='fast' else 29):raise ValueError('actual snapshot/capture register inventory differs')
    if str(ROOT/'build/signoff400/prototype_v3_selected_route_019/route.odb') not in (baseline/'fixed_divide16/screen.tcl').read_text():raise ValueError('selected route required')
    constants={}
    original=baseline/'fixed_divide16/screen.tcl'
    if b['artifacts'].get(str(original))!=sha(original):raise ValueError('native-view timing script changed')
    text=original.read_text().split('report_parasitic_annotation',1)[0]
    output.mkdir(parents=True,exist_ok=False);script=output/'paths.tcl'
    original_sdc=baseline/'fixed_divide16/screen.sdc'
    if b['artifacts'].get(str(original_sdc))!=sha(original_sdc):raise ValueError('baseline SDC changed')
    constraints=output/'measurement.sdc'
    sdc_text=original_sdc.read_text()
    marker='# Keep PLLOUT/FINECLK related paths visible.'
    if sdc_text.count(marker)!=1:raise ValueError('unique capacity async-exception block required')
    constraints.write_text(sdc_text.split(marker)[0]+'# Interclock exceptions removed only for explicit snapshot delay measurement.\n')
    if text.count('source '+str(original_sdc))!=1:raise ValueError('unique baseline SDC source required')
    text=text.replace('source '+str(original_sdc),'source '+str(constraints))
    text+='set launch [get_cells {'+' '.join(sources)+'}]\nset capture [get_cells {'+' '.join(targets)+'}]\n'
    text+=f'if {{[llength $launch]!={len(sources)} || [llength $capture]!={len(targets)}}} {{error "snapshot/capture cell binding differs"}}\n'
    text+='report_checks -from $launch -to $capture -path_delay min_max -group_path_count 100 -endpoint_path_count 1 -digits 6\nexit\n'
    script.write_text(text);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    with lease(1,4,deadline):execute([*container_prefix,OPENROAD,'-exit',script],output/'paths.log',deadline,4)
    log=(output/'paths.log').read_text()
    if re.search(r'\[ERROR|Error:|STA-(1648|1650)',log):raise ValueError('native seed-path query failed')
    records=[]
    for block in log.split('Startpoint: ')[1:]:
        start=block.splitlines()[0].strip();endpoint=re.search(r'^Endpoint: (\S+)',block,re.M)
        arrival=re.search(r'([-+0-9.eE]+)\s+data arrival time',block)
        clock=re.search(r'[-+0-9.eE]+\s+([-+0-9.eE]+)\s+[\^v] '+re.escape(start)+r'/CLK ',block)
        slack=re.search(r'([-+0-9.eE]+)\s+slack \((MET|VIOLATED)\)',block)
        kind=re.search(r'Path Type: (min|max)',block)
        if not all((endpoint,arrival,clock,slack,kind)):raise ValueError('seed path fields incomplete')
        if start not in sources or endpoint[1] not in targets:raise ValueError('unexpected payload path endpoint')
        delay=float(arrival[1])-float(clock[1])
        if delay<=0:raise ValueError('nonpositive command-to-consumer delay')
        records.append(dict(kind=kind[1],startpoint=start,endpoint=endpoint[1],source_clock_to_consumer_D_ns=delay,setup_slack_ns=float(slack[1])))
    if len(records)!=2*len(targets) or any({r['endpoint'] for r in records if r['kind']==kind}!=set(targets)-set(constants) for kind in ('min','max')):raise ValueError('not every implemented handoff capture bit was covered')
    paths=[*receipts,routed,original,original_sdc,constraints,script,image,Path(__file__).resolve(),Path(__file__).with_name('selected_physical_rtl.py')];pins={**selected,**{str(p):sha(p) for p in paths}};verify(pins)
    tool_digest=subprocess.check_output([str(x) for x in (*container_prefix,'sha256sum',OPENROAD)],text=True).split()[0]
    if b['input_sha256'].get(OPENROAD)!=tool_digest:raise ValueError('timing tool differs from native baseline')
    detail=output/'paths.json';save(detail,records)
    save(output/'assessment.json',dict(input_sha256=pins,container_tool_sha256={OPENROAD:tool_digest},artifacts={str(p):sha(p) for p in (detail,output/'paths.log')},
        corner=b['native_model_corner'],bundle=bundle,snapshot_registers=len(sources),capture_registers=len(targets),
        every_implemented_handoff_capture_bit_has_a_reported_payload_path=True,
        request_synchronization_and_earliest_capture_budget_qualified=False,
        maximum_reported_source_clock_to_consumer_D_ns=max(r['source_clock_to_consumer_D_ns'] for r in records if r['kind']=='max'),
        minimum_reported_source_clock_to_consumer_D_ns=min(r['source_clock_to_consumer_D_ns'] for r in records if r['kind']=='min'),
        explicit_min_max_paths=len(records),
        diagnostic_related_clock_checks_pass=all(r['setup_slack_ns']>=0 for r in records),
        cross_clock_capacity_exceptions_removed_for_explicit_measurement=True,first_cycle_hold_exception_generated=False,actual_startup_guard_timing_qualified=False,
        conditional_observed_reset_charge_loads_and_routed_min_max_RC_used=True,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('baseline','inventory','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--bundle',choices=('fast','fine'),required=True)
    a=p.parse_args();run(a.baseline.resolve(),a.inventory.resolve(),a.output.resolve(),a.bundle)
