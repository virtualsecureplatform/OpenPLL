"""Propagate characterized size changes using fixed extracted RC before rerouting.

This is proposal optimization, not physical qualification: pin capacitances
update with master sizes, while wire geometry is reused. Pending source buffers
are not inserted in these estimates. Final routed RC/timing checks are required.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import time
from common_v3 import ROOT, save, sha, verify
from compiled_charge import execute
from resources import lease
from inventory_prototype_electrical_limits_v2 import electrical_rows
from extend_prototype_plan_measured_timing import next_strength

OPENROAD=Path('/nix/store/qqz49dx8dpx4q9i5wriif091n7iaa0ld-openroad-2026-02-17/bin/openroad')
CORNERS=('tt','ff','ss','sf','fs')


def electrical_driver(pin,module,cells,drivers):
    if '/' in pin:
        name,terminal=pin.rsplit('/',1);bits=cells[name]['connections'][terminal]
    else:
        matches=[]
        for name,port in module['ports'].items():
            width=len(port['bits'])
            for index,bit in enumerate(port['bits']):
                logical=(width-1-index if port.get('upto',0) else index)+port.get('offset',0)
                label=name if width==1 else f'{name}[{logical}]'
                if label==pin:matches.append(bit)
        bits=matches
    if len(bits)!=1 or len(drivers.get(bits[0],[]))!=1:
        raise ValueError('unique scalar electrical driver required')
    return drivers[bits[0]][0]


def changes_for_driver(name,pin,cells,targets,buffers,protected,available):
    if name in protected or name in buffers:
        return False
    old=cells[name]['type']; current=targets.get(name,{}).get('replacement_master',old)
    replacement=next_strength(current,available)
    if replacement:
        targets[name]=dict(action='resize',capture_cell=name,capture_master=old,replacement_master=replacement)
        return True
    if current=='sky130_fd_sc_hs__clkbuf_16':
        return False  # Fanout topology changes require the separate checked planner.
    if pin not in ('Y','X','Q') or 'sky130_fd_sc_hs__clkbuf_8' not in available:
        raise ValueError('review source-buffer family/pin before proposing a change')
    buffers[name]=dict(driver=dict(cell=name,pin=pin,master=current),buffer_master='sky130_fd_sc_hs__clkbuf_8')
    return True


def resize_tcl(targets):
    text='set block [ord::get_db_block]\n'
    for name,t in sorted(targets.items()):
        if any(c in name for c in '{}\\\r\n') or t['capture_master'].rsplit('_',1)[0]!=t['replacement_master'].rsplit('_',1)[0]:
            raise ValueError('same-family safe size change required')
        text+=f'''set inst [$block findInst {{{name}}}]
if {{$inst eq {{NULL}} || [[$inst getMaster] getName] ne {{{t['capture_master']}}}}} {{error "source master changed"}}
replace_cell {{{name}}} {t['replacement_master']}
'''
    return text


def run(plan,route,inventory,views,timing,output,rounds,guard):
    pp=plan/'plan.json'; p=json.loads(pp.read_text());verify(p['input_sha256'])
    rr=route/'assessment.json'; ir=inventory/'assessment.json'; vr=views/'assessment.json'
    r,i,v=[json.loads(f.read_text()) for f in (rr,ir,vr)]
    for record in (r,i,v):verify(record['input_sha256']);verify(record['artifacts'])
    if p['route_sha256']!=sha(route/'route.odb') or i['input_sha256'].get(str(rr))!=sha(rr):
        raise ValueError('same-route electrical proposal and proved inventory required')
    if not 0<guard<1 or not 1<=rounds<=8:
        raise ValueError('bounded stricter proposal guard required')
    graph=inventory/'routed.json'; module=json.loads(graph.read_text())['modules']['IntegerPLL_ProgrammedCore']
    cells={n.lstrip('\\'):c for n,c in module['cells'].items()};drivers={}
    for name,cell in cells.items():
        for pin,bits in cell['connections'].items():
            if cell['port_directions'].get(pin)=='output':
                for bit in bits:drivers.setdefault(bit,[]).append((name,pin))
    protected=set(p['protected_first_stage_cells'])
    if len(protected)!=13 or any(cells[n]['type']!='sky130_fd_sc_hs__dfrtp_1' for n in protected):
        raise ValueError('thirteen native first-stage masters must remain fixed')
    libraries=[views/f'{c}_{edge}.lib' for c in CORNERS for edge in ('early','late')]
    available=set.intersection(*(set(re.findall(r'cell \(([^)]+)\)',f.read_text())) for f in libraries))
    eq={n:h for n,h in i['input_sha256'].items() if n.endswith('/assessment.json') and 'equivalence' in n}
    if len(eq)!=1:raise ValueError('one routed equivalence identity required')
    templates={};inputs=dict(p['input_sha256'])
    for folder in timing:
        receipt=folder/'assessment.json';a=json.loads(receipt.read_text())
        verify(a['input_sha256']);verify(a['artifacts'])
        c=a['native_model_corner'];script=folder/'fixed_divide16/screen.tcl'
        if (c in templates or c not in CORNERS or not a.get('minmax_wire_RC_used')
                or any(a['input_sha256'].get(n)!=h for n,h in eq.items())
                or a['input_sha256'].get(str(vr))!=sha(vr)
                or a['input_sha256'].get(str(route/'route.odb'))!=sha(route/'route.odb')
                or a['artifacts'].get(str(script))!=sha(script)):
            raise ValueError('same-route five-corner native wire templates required')
        templates[c]=script.read_text();inputs.update(a['input_sha256']);inputs.update(a['artifacts'])
        inputs[str(receipt)]=sha(receipt)
    if set(templates)!=set(CORNERS):raise ValueError('all five corners required')
    inputs.update({str(f):sha(f) for f in (pp,rr,ir,vr,graph,*libraries,OPENROAD,Path(__file__).resolve(),
                  Path(__file__).with_name('inventory_prototype_electrical_limits_v2.py'),
                  Path(__file__).with_name('extend_prototype_plan_measured_timing.py'))})
    targets={t['capture_cell']:t for t in p['targets']}
    buffers={t['driver']['cell']:t for t in p.get('source_buffers',[])}
    if protected & targets.keys() or protected & buffers.keys():raise ValueError('protected source changed')
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+86400
    save(output/'owner.json',dict(deadline_uptime=deadline,automatic_identical_retry=False,
         proposal_only=True,round_limit=rounds,optimization_max_transition_ns=guard))
    history=[];artifacts={};last_rows=[]
    for step in range(rounds+1):
        actions=resize_tcl(targets)+f'set_max_transition {guard:.12g} [current_design]\n'
        for name in sorted(protected):
            actions+=f'if {{[[[$block findInst {{{name}}}] getMaster] getName] ne {{sky130_fd_sc_hs__dfrtp_1}}}} {{error "first-stage master changed"}}\n'
        scripts={}
        for c,template in templates.items():
            folder=output/f'round_{step:02d}_{c}';folder.mkdir()
            marker='report_parasitic_annotation -report_unannotated'
            if template.count(marker)!=1:raise ValueError('unique post-SPEF query boundary required')
            script=folder/'screen.tcl';script.write_text(template.replace(marker,actions+marker))
            inputs[str(script)]=sha(script);scripts[c]=script
        def check(item):
            c,script=item;log=script.with_suffix('.log')
            with lease(1,4,deadline):execute([OPENROAD,'-exit',script],log,deadline,4)
            text=log.read_text()
            if re.search(r'\[ERROR|^Error:|STA-(1648|1650)',text,re.M):raise ValueError('native what-if binding error')
            if 'worst slack max ' not in text:raise ValueError('missing native timing result')
            return c,log,electrical_rows(text)
        with ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(check,scripts.items()))
        failing=set();last_rows=[]
        for c,log,rows in results:
            artifacts[str(log)]=sha(log)
            for kind,unit,pin,limit,measured,slack in rows:
                driver=electrical_driver(pin,module,cells,drivers);failing.add(driver)
                last_rows.append(dict(corner=c,kind=kind,pin=pin,unit=unit,limit=float(limit),
                                      measured=float(measured),slack=float(slack),driver=driver[0]))
        history.append(dict(round=step,resizes=len(targets),pending_source_buffers=len(buffers),
                            failing_drivers=len(failing),reported_rows=len(last_rows)))
        save(output/'progress.json',dict(history=history,proposal_only=True,release_ready=False))
        if step==rounds:break
        previous_targets=dict(targets)
        for name,pin in sorted(failing):
            changes_for_driver(name,pin,cells,targets,buffers,protected,available)
        # Pending buffers are deliberately not simulated here. Replaying the
        # same size map after only adding a buffer proposal would be redundant.
        if targets==previous_targets:break
    verify(inputs)
    detail=output/'fixed_geometry_findings.json';save(detail,last_rows);artifacts[str(detail)]=sha(detail)
    p.update(input_sha256=inputs,targets=list(targets.values()),source_buffers=list(buffers.values()),
             sizing_proposal_guard_ns=guard,wire_geometry_reused_for_size_proposal_only=True,
             pending_source_buffers_not_inserted_in_estimates=True,
             all_first_stage_synchronizer_masters_preserved=True,
             independent_postroute_minmax_RC_recheck_required=True,electrical_closure_claimed=False,release_ready=False)
    save(output/'plan.json',p);artifacts[str(output/'plan.json')]=sha(output/'plan.json')
    save(output/'assessment.json',dict(input_sha256=inputs,artifacts=artifacts,history=history,
         sizing_proposal_complete=True,wire_geometry_reused=True,pending_buffer_topology_estimated=False,
         physical_timing_qualified=False,electrical_limits_qualified=False,release_ready=False))
    print(json.dumps(dict(resizes=len(targets),source_buffers=len(buffers),native_rounds=len(history))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','route','inventory','views','output'):parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--timing',required=True,action='append',type=Path)
    parser.add_argument('--rounds',type=int,default=6);parser.add_argument('--guard-ns',type=float,default=.9)
    a=parser.parse_args();run(*(getattr(a,n).resolve() for n in ('plan','route','inventory','views')),
        [p.resolve() for p in a.timing],a.output.resolve(),a.rounds,a.guard_ns)
