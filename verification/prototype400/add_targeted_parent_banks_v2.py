#!/usr/bin/env python3
"""Protect the ten remaining M3 nets on existing PG rails; freeze other routes.

Place tap+four-diode banks only where both physical M1 supply rails already
cover the full cell ports. Add no PG straps or vias. Encode every unaffected
signal route FIXED, then reroute only the ten changed nets. Fresh full-GDS
physical and antenna checks remain mandatory; no model or release is adopted.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'timing400'))
from check_bbpd_repair_identity import design,section
from check_compact_clock_tree import verify
from check_compact_mapping import OPENROAD, TECH, LEF
from run_dco_qualification import ROOT,sha,save


def merged(intervals):
    result=[]
    for a,b in sorted(intervals):
        if result and a<=result[-1][1]:result[-1]=(result[-1][0],max(b,result[-1][1]))
        else:result.append((a,b))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    for name in ('source-route','localization','old-plan','frame'):
        parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args()
    source=args.source_route.resolve();source_proof=verify(source/'assessment.json')
    assert source_proof['router_drc_violations']==0 and source_proof['exact_macro_bindings_preserved']
    localized=args.localization.resolve();located=verify(localized/'assessment.json')
    frame=args.frame.resolve();frame_proof=verify(frame/'assessment.json')
    assert frame_proof['assembly_frame_pass']
    assert located['input_sha256'][str(frame/'assessment.json')]==sha(frame/'assessment.json')
    failed=[dict(r,logical_nets=sorted({p['net'] for p in r['macro_ports']}),macro_port_aliases=r['macro_ports']) for r in json.loads((localized/'records.json').read_text())];assert failed and all(len(r['logical_nets'])==1 for r in failed)
    selected={r['logical_nets'][0] for r in failed};assert len(selected)==len(failed)
    oldplan=args.old_plan.resolve();old=json.loads(oldplan.read_text())
    original_owner=source/'owner.json';deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,
        original_owner=str(original_owner),new_distinct_check_budget=True,changed_algorithm='targeted_existing_rail_banks_with_fixed_background',automatic_identical_retry=False))
    def run(name,text):
        script=out/(name+'.tcl');script.write_text(text)
        with (out/(name+'.log')).open('x') as log:
            child=subprocess.Popen([OPENROAD,'-no_init','-exit',str(script)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            save(out/'status.json',dict(state=name,native_pid=child.pid,release_qualified=False))
            try:code=child.wait(timeout=deadline-time.clock_gettime(time.CLOCK_BOOTTIME))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                save(out/'status.json',dict(state='timeout_inconclusive',release_qualified=False));raise
        assert code==0,(name,code)
    run('power_probe',f'''read_db {source}/route.odb
set f [open {out}/m1_power.tsv w]
foreach net {{VPWR VGND}} {{
 foreach wire [[[ord::get_db_block] findNet $net] getSWires] {{
  foreach box [$wire getWires] {{
   if {{![$box isVia] && [[$box getTechLayer] getName] eq {{met1}}}} {{
    puts $f [list $net [$box xMin] [$box yMin] [$box xMax] [$box yMax]]
   }}
  }}
 }}
}}
close $f
''')
    boxes=[]
    for line in (out/'m1_power.tsv').read_text().splitlines():
        net,*coordinates=line.split();boxes.append((net,*map(int,coordinates)))
    bodies=[(a-3000,b-3000,c+3000,d+3000) for a,b,c,d in frame_proof['macro_bboxes_dbu'].values()]
    occupied=[(r['x_nm']-1920,r['y_nm'],r['x_nm']+4320+1920,r['y_nm']+3330) for r in old]
    support=[]
    for y in sorted({r['y_nm'] for r in old}):
        ground=merged([(a,c) for n,a,b,c,d in boxes if n=='VGND' and b<=y-245 and d>=y+245])
        power=merged([(a,c) for n,a,b,c,d in boxes if n=='VPWR' and b<=y+3085 and d>=y+3575])
        support.extend((y,max(a,c),min(b,d)) for a,b in ground for c,d in power if min(b,d)-max(a,c)>=4320)
    plan=[]
    for row in sorted(failed,key=lambda r:r['logical_nets']):
        net=row['logical_nets'][0]
        port=next((p for p in row['macro_port_aliases'] if p['instance']=='oscillator'),None)
        if port is None:port=next((p for p in row['macro_port_aliases'] if p['instance']=='detector'),row['macro_port_aliases'][0])
        cx,cy=port['point'];options=[]
        for y,left,right in support:
            first=max(0,(left-10080+479)//480);last=(right-4320-10080)//480
            for column in range(first,last+1):
                x=10080+column*480;bb=(x,y,x+4320,y+3330)
                if any(bb[0]<b[2] and bb[2]>b[0] and bb[1]<b[3] and bb[3]>b[1] for b in bodies+occupied):continue
                distance=abs(x+2160-cx)+abs(y+1665-cy)
                options.append((distance,x,y))
        assert options,('no existing-rail site',net)
        distance,x,y=min(options);occupied.append((x-1920,y,x+4320+1920,y+3330))
        plan.append(dict(net=net,x_nm=x,y_nm=y,orient='R0',diodes=4,port_center_nm=[cx,cy],center_distance_nm=distance,
            both_m1_power_ports_fully_covered_by_existing_rails=True))
    save(out/'extra_placement_plan.json',plan)
    files=[Path(__file__).resolve(),Path(__file__).resolve().parents[1]/'timing400/check_bbpd_repair_identity.py',Path(OPENROAD),source/'assessment.json',source/'route.odb',source/'route.def',original_owner,
        frame/'assessment.json',oldplan,localized/'assessment.json',localized/'records.json',out/'m1_power.tsv']
    pins={str(p):sha(p) for p in files}
    lines=[f'read_db {source}/route.odb','set block [ord::get_db_block]']
    for index,row in enumerate(plan):
        for kind,dx in [('tapvpwrvgnd_1',0)]+[('diode_2',480+i*960) for i in range(4)]:
            name=f'parent_extra_antenna_{index:02d}_{dx}'
            lines.extend([f'set inst [odb::dbInst_create $block [[ord::get_db] findMaster sky130_fd_sc_hs__{kind}] {name}]',
                f'$inst setOrient R0',f'$inst setLocation {row["x_nm"]+dx} {row["y_nm"]}','$inst setPlacementStatus PLACED',
                '[$inst findITerm VPWR] connect [$block findNet VPWR]',
                '[$inst findITerm VGND] connect [$block findNet VGND]'])
            if kind=='diode_2':lines.extend(['[$inst findITerm VPB] connect [$block findNet VPWR]',
                '[$inst findITerm VNB] connect [$block findNet VGND]',f'[$inst findITerm DIODE] connect [$block findNet {{{row["net"]}}}]'])
    lines.extend(['check_placement -verbose',f'write_db {out}/placed.odb',f'write_def {out}/placed.def',
        f'check_power_grid -net VPWR -error_file {out}/placed_vpwr_errors.rpt',f'check_power_grid -net VGND -error_file {out}/placed_vgnd_errors.rpt'])
    run('place','\n'.join(lines)+'\n')
    def_text=(out/'placed.def').read_text();net_section=section(out/'placed.def','NETS');frozen=[]
    def freeze(match):
        name=match[1];body=match[2]
        if name not in selected and re.search(r'\+\s+ROUTED\b',body):
            body=re.sub(r'\+\s+ROUTED\b','+ FIXED',body);frozen.append(name)
        return '- '+name+' '+body+';'
    modified=re.sub(r'^\s*-\s+(\S+)\s+(.*?);',freeze,net_section,flags=re.M|re.S)
    expected_background=len(frozen)
    assert expected_background>0
    (out/'fixed_background.def').write_text(def_text.replace(net_section,modified))
    selected_tcl=' '.join('{'+name+'}' for name in sorted(selected))
    dco='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    macros=[Path(frame_proof['macro_sources'][name]['lef']) for name in ('digital','oscillator','detector')]
    head='\n'.join(f'read_lef {{{path}}}' for path in [TECH,LEF,*macros])+'\n'
    for path in [TECH,LEF,*macros]:pins[str(path)]=sha(path)
    run('route',head+f'''read_def {out}/fixed_background.def
set_thread_count 4
set block [ord::get_db_block]
set targets {{{selected_tcl}}}
set decoder [odb::dbWireDecoder]
set fixed 0
foreach net [$block getNets] {{
 if {{[$net getSigType] in {{POWER GROUND}}}} {{continue}}
 if {{[$net getName] in $targets}} {{
  if {{[$net getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$net getWire]}}
 }} else {{
  $decoder begin [$net getWire]
  $decoder next
  if {{[$decoder getWireType] ne {{FIXED}}}} {{error "unfixed background route"}}
  incr fixed
 }}
}}
if {{$fixed!={expected_background}}} {{error "wrong background count"}}
set_routing_layers -signal met1-met4 -clock met1-met4
set_global_routing_layer_adjustment met2 0.5
set_global_routing_layer_adjustment met3 0.99
set_global_routing_layer_adjustment met4 0.9
global_route -verbose -guide_file {out}/route.guide -congestion_iterations 100
detailed_route -output_drc {out}/route.drc -output_maze {out}/route.maze.log -output_guide_coverage {out}/route.coverage
write_db {out}/route.odb
write_def {out}/route.def
write_verilog {out}/route.v
write_verilog -include_pwr_gnd {out}/powered.v
check_power_grid -net VPWR -error_file {out}/vpwr_errors.rpt
check_power_grid -net VGND -error_file {out}/vgnd_errors.rpt
''')
    text=(out/'route.log').read_text();counts=re.findall(r'Number of violations = (\d+)',text)
    assert counts and counts[-1]=='0' and (out/'route.drc').stat().st_size==0
    for net in ['VPWR','VGND']:assert f'All shapes on net {net} are connected.' in text
    oldcells,oldpins,oldnets=design(source/'route.def');newcells,newpins,newnets=design(out/'route.def')
    assert all(newcells[n]==row for n,row in oldcells.items())
    assert all(newpins[k]==net for k,net in oldpins.items())
    _,placedpins,_=design(out/'placed.def');assert all(newpins[k]==net for k,net in placedpins.items())
    assert section(source/'route.def','PINS')==section(out/'route.def','PINS')
    def normalized(body):return re.sub(r'\bFIXED\b','ROUTED',body)
    assert all(normalized(newnets[n])==normalized(oldnets[n]) for n in frozen)
    for p,digest in pins.items():assert sha(p)==digest,p
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'},
        detailed_route_completed=True,router_drc_violations=0,main_rail_connectivity_passed=True,main_rail_database_connectivity_pass=True,exact_macro_bindings_preserved=True,parent_signal_routes_rebuilt=True,
        extra_placement_plan=str(out/'extra_placement_plan.json'),added_diode_instances=4*len(plan),added_well_tap_instances=len(plan),
        target_nets=sorted(selected),unchanged_background_signal_routes=expected_background,retained_macro_and_cell_placements_identical=True,
        all_old_pin_bindings_preserved=True,all_macro_ports_preserved=True,no_new_power_straps_or_vias=True,
        full_assembled_drc_passed=False,assembled_lvs_passed=False,antenna_qualified=False,rc_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='routed_candidate',router_drc_violations=0,background_fixed_routes=expected_background,release_qualified=False))
    print('Added',4*len(plan),'diodes and',len(plan),'taps; rerouted',len(selected),'nets;',expected_background,'background routes verified unchanged.')

if __name__=='__main__':
    try:main()
    except BaseException as e:
        if '--output' in sys.argv:
            output=Path(sys.argv[sys.argv.index('--output')+1])
            if output.exists():save(output/'status.json',dict(state='failed',reason=repr(e),release_qualified=False))
        raise
