"""Measure actual REF snapshot-to-handoff capture paths without timing exceptions."""
import argparse,json,os,re,time
from pathlib import Path
from common_v3 import save,sha,verify
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
    receipts=[p/'assessment.json' for p in (baseline,inventory)]
    b,i=[json.loads(p.read_text()) for p in receipts]
    for r in (b,i):verify(r['artifacts'])
    lineage={name:digest for name,digest in i['input_sha256'].items() if name.endswith('/assessment.json') and 'equivalence' in name}
    if len(lineage)!=1 or any(b['input_sha256'].get(name)!=digest for name,digest in lineage.items()):raise ValueError('route/proof lineage mismatch')
    routed=inventory/'routed.json';module=json.loads(routed.read_text())['modules']['IntegerPLL_ProgrammedCore']
    prefix='handoff' if bundle=='fast' else 'gen_feedback_handoff.fine_handoff'
    sources=registers(module,prefix+'.payload');targets=registers(module,prefix+'.APPLIED_COMMAND')
    if len(sources)!=30 or len(targets)!=(1 if bundle=='fast' else 29):raise ValueError('actual snapshot/capture register inventory differs')
    constants={}
    original=baseline/'fixed_divide16/screen.tcl'
    if b['artifacts'].get(str(original))!=sha(original):raise ValueError('native-view timing script changed')
    text=original.read_text().split('report_parasitic_annotation',1)[0]
    output.mkdir(parents=True,exist_ok=False);script=output/'paths.tcl'
    text+='set launch [get_cells {'+' '.join(sources)+'}]\nset capture [get_cells {'+' '.join(targets)+'}]\n'
    text+=f'if {{[llength $launch]!={len(sources)} || [llength $capture]!={len(targets)}}} {{error "snapshot/capture cell binding differs"}}\n'
    text+='report_checks -from $launch -to $capture -path_delay max -group_path_count 100 -endpoint_path_count 1 -digits 6\nexit\n'
    script.write_text(text);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    with lease(1,4,deadline):execute([OPENROAD,'-exit',script],output/'paths.log',deadline,4)
    log=(output/'paths.log').read_text()
    if re.search(r'\[ERROR|Error:|STA-(1648|1650)',log):raise ValueError('native seed-path query failed')
    records=[]
    for block in log.split('Startpoint: ')[1:]:
        start=block.splitlines()[0].strip();endpoint=re.search(r'^Endpoint: (\S+)',block,re.M)
        arrival=re.search(r'([-+0-9.eE]+)\s+data arrival time',block)
        clock=re.search(r'[-+0-9.eE]+\s+([-+0-9.eE]+)\s+[\^v] '+re.escape(start)+r'/CLK ',block)
        slack=re.search(r'([-+0-9.eE]+)\s+slack \((MET|VIOLATED)\)',block)
        if not all((endpoint,arrival,clock,slack)) or 'Path Type: max' not in block:raise ValueError('seed path fields incomplete')
        if start not in sources or endpoint[1] not in targets:raise ValueError('unexpected payload path endpoint')
        delay=float(arrival[1])-float(clock[1])
        if delay<=0:raise ValueError('nonpositive command-to-consumer delay')
        records.append(dict(startpoint=start,endpoint=endpoint[1],source_clock_to_consumer_D_ns=delay,setup_slack_ns=float(slack[1])))
    if {r['endpoint'] for r in records}!=set(targets)-set(constants):raise ValueError('not every nonconstant accumulator state bit was covered')
    paths=[*receipts,routed,original,script,Path(OPENROAD),Path(__file__).resolve()];pins={str(p):sha(p) for p in paths};verify(pins)
    detail=output/'paths.json';save(detail,records)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (detail,output/'paths.log')},
        corner=b['native_model_corner'],bundle=bundle,snapshot_registers=len(sources),capture_registers=len(targets),
        every_implemented_handoff_capture_bit_has_a_reported_payload_path=True,
        request_synchronization_and_earliest_capture_budget_qualified=False,
        maximum_reported_source_clock_to_consumer_D_ns=max(r['source_clock_to_consumer_D_ns'] for r in records),
        all_reported_payload_setup_checks_pass=all(r['setup_slack_ns']>=0 for r in records),
        first_cycle_hold_exception_generated=False,actual_startup_guard_timing_qualified=False,
        conditional_TT_pin_loads_and_nominal_routed_RC_used=True,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('baseline','inventory','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--bundle',choices=('fast','fine'),required=True)
    a=p.parse_args();run(a.baseline.resolve(),a.inventory.resolve(),a.output.resolve(),a.bundle)
