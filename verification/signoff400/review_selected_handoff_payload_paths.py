"""Review selected bundle delay coverage; asynchronous timing qualification stays open."""
import argparse,json,math,os,re
from pathlib import Path
from common_v3 import save,sha,verify
from selected_physical_rtl import source_pins
from measure_selected_handoff_payload_paths_v2 import registers
from screen_prototype_decision_hold_phase_v3 import OPENROAD


def parse(text,sources,targets):
    if re.search(r'\[ERROR|Error:|invalid command',text):raise ValueError('native timing query failed')
    rows=[]
    for block in text.split('Startpoint: ')[1:]:
        start=block.splitlines()[0].strip();end=re.search(r'^Endpoint: (\S+)',block,re.M);kind=re.search(r'Path Type: (min|max)',block);arrival=re.search(r'([-+0-9.eE]+)\s+data arrival time',block);clock=re.search(r'[-+0-9.eE]+\s+([-+0-9.eE]+)\s+[\^v] '+re.escape(start)+r'/CLK ',block)
        if not all((end,kind,arrival,clock)) or start not in sources or end[1] not in targets:raise ValueError('explicit payload path identity differs')
        delay=float(arrival[1])-float(clock[1])
        if not math.isfinite(delay) or delay<=0:raise ValueError('positive finite propagation delay required')
        rows.append(dict(startpoint=start,endpoint=end[1],kind=kind[1],delay_ns=delay))
    required={(target,kind) for target in targets for kind in ('min','max')};actual=[(r['endpoint'],r['kind']) for r in rows]
    if len(actual)!=len(required) or set(actual)!=required:raise ValueError('exact min/max coverage of every capture register required')
    return rows


def run(family,capture,output):
    if output.exists():raise FileExistsError(output)
    os.sched_setaffinity(0,{30});a=json.loads(family.read_text());verify(a['input_sha256']);pins=source_pins();proof=json.loads(capture.read_text());verify(proof['input_sha256']);verify(proof['artifacts'])
    if not proof['two_prior_destination_rising_edges_of_payload_stability_before_capture_proven'] or not proof['qualification_register_bypass_rejected']:raise ValueError('selected handoff age theorem and hardware control required')
    expected={(c,b) for c in ('tt','ff','ss','sf','fs') for b in ('fast','fine')};seen=set();summary=[];details=[]
    for row in a['records']:
        corner,bundle=row['corner'],row['bundle'];key=(corner,bundle)
        if key not in expected or key in seen:raise ValueError('unique five-corner/two-bundle coverage required')
        seen.add(key);receipt=Path(row['receipt'])
        if sha(receipt)!=row['sha256']:raise ValueError('measurement receipt changed')
        r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        if (r['corner'],r['bundle'])!=key:raise ValueError('measurement corner/bundle differs')
        for p,h in pins.items():
            if p.endswith('.v') and r['input_sha256'].get(p)!=h:raise ValueError('selected source identity differs')
        baselines=[Path(p) for p in r['input_sha256'] if p.endswith('/assessment.json') and f'prototype_v3_selected_402p1_timing_{corner}_019/' in p]
        inventories=[Path(p) for p in r['input_sha256'] if p.endswith('/routed.json')]
        if len(baselines)!=1 or len(inventories)!=1:raise ValueError('unique selected native timing/routed sources required')
        b=json.loads(baselines[0].read_text());verify(b['artifacts'])
        for p,h in b['input_sha256'].items():
            if Path(p).exists():verify({p:h})
            elif p==OPENROAD and r['container_tool_sha256'].get(p)==h:pass
            else:raise ValueError('unverified native timing input: '+p)
        module=json.loads(inventories[0].read_text())['modules']['IntegerPLL_ProgrammedCore'];prefix='handoff' if bundle=='fast' else 'gen_feedback_handoff.fine_handoff';sources=registers(module,prefix+'.payload');targets=registers(module,prefix+'.APPLIED_COMMAND')
        if len(sources)!=30 or len(targets)!=(1 if bundle=='fast' else 29):raise ValueError('complete implemented storage inventory required')
        log=receipt.parent/'paths.log';paths=parse(log.read_text(),sources,targets);low=min(x['delay_ns'] for x in paths if x['kind']=='min');high=max(x['delay_ns'] for x in paths if x['kind']=='max')
        if abs(low-r['minimum_reported_source_clock_to_consumer_D_ns'])>1e-9 or abs(high-r['maximum_reported_source_clock_to_consumer_D_ns'])>1e-9:raise ValueError('reparsed propagation delays differ')
        summary.append(dict(corner=corner,bundle=bundle,capture_registers=len(targets),explicit_min_max_paths=len(paths),minimum_source_clock_to_D_ns=low,maximum_source_clock_to_D_ns=high));details += [dict(corner=corner,bundle=bundle,**p) for p in paths]
        for p in(receipt,baselines[0],inventories[0],log):pins[str(p)]=sha(p)
    if seen!=expected or len(details)!=300:raise ValueError('all 300 explicit selected payload min/max paths required')
    for p in(family,capture,Path(__file__).resolve(),*(Path(__file__).with_name(n) for n in ('common_v3.py','selected_physical_rtl.py','measure_selected_handoff_payload_paths_v2.py','screen_prototype_decision_hold_phase_v3.py'))):pins[str(p)]=sha(p)
    verify(pins);save(output,dict(input_sha256=pins,records=summary,explicit_min_max_paths=300,all_implemented_capture_registers_covered_at_five_corners=True,discrete_two_prior_destination_edges_before_capture_proven=True,conditional_native_views_and_routed_min_max_RC=True,related_clock_slacks_used_as_asynchronous_acceptance=False,physical_request_aperture_qualified=False,actual_startup_frequency_range_qualified=False,physical_payload_setup_hold_qualified=False,physical_CDC_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('family','capture','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.family.resolve(),a.capture.resolve(),a.output.resolve())
