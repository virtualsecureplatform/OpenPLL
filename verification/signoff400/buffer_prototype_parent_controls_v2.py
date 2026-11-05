"""Insert two characterized inverters at measured failing DCO control receivers.

The exact Boolean composition is identity. Native electrical response, parent
timing, DRC/LVS and formation-stage antenna closure remain separate checks.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from common_v3 import ROOT,save,sha,verify
from protect_prototype_parent_periphery import bank_site,rails_for_bank,SY
from resources import lease
from compiled_charge import execute
sys.path.insert(0,str(ROOT/'verification/prototype400'))
from build_assembly_frame import expected
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import OPENROAD

def inverter_function(text,master):
    token=f' cell ({master}) {{\n'
    if text.count(token)!=1:raise ValueError('one native inverter definition required')
    block=text.split(token,1)[1].split('\n cell (',1)[0]
    functions=re.findall(r'\bfunction\s*:\s*"([^"]+)"',block)
    if functions!=['(!A)']:raise ValueError('native cell must implement exactly !A')
    if 'pin (A)' not in block or 'pin (Y)' not in block:raise ValueError('reviewed inverter interface required')
    return [1,0]

def run(power,frame,localization,views,output,prior):
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    receipts=[p/'assessment.json' for p in (power,frame,localization,views)]
    p,f,l,v=[json.loads(path.read_text()) for path in receipts]
    for record in (p,f,l,v):verify(record['input_sha256']);verify(record['artifacts'])
    if not p['main_rail_database_connectivity_pass'] or not f['assembly_frame_pass'] or l['violations_with_macro_port']!=l['violations']:
        raise ValueError('matching checked power/frame and localized failures required')
    if p['candidate_source_sha256']!=f['candidate_source_sha256'] or l['input_sha256'].get(str(receipts[1]))!=sha(receipts[1]):
        raise ValueError('selected source identity differs')
    libraries=[views/f'{c}_{edge}.lib' for c in ('tt','ff','ss','sf','fs') for edge in ('early','late')]
    for path in libraries:
        if v['artifacts'].get(str(path))!=sha(path):raise ValueError('native inverter library changed')
        for master in ('sky130_fd_sc_hs__inv_8','sky130_fd_sc_hs__inv_2'):inverter_function(path.read_text(),master)
    records_path=localization/'records.json';rows=json.loads(records_path.read_text());targets={};logical=expected()
    lef=Path(f['macro_sources']['oscillator']['lef']);text=lef.read_text()
    for row in rows:
        nets={port['net'] for port in row['macro_ports']}
        if len(nets)!=1:raise ValueError('one logical net per failing component required')
        net=next(iter(nets));ports=[port for port in row['macro_ports'] if port['instance']=='oscillator']
        if len(ports)!=1:raise ValueError('one actual DCO receiver per measured net required')
        port=ports[0];pin=port['pin']
        if logical.get(('oscillator',pin))!=net:raise ValueError('DCO receiver differs from logical frame')
        match=re.search(r'^\s*PIN '+re.escape(pin)+r'\s*$(.*?)^\s*END '+re.escape(pin)+r'\s*$',text,re.M|re.S)
        if match is None or not re.search(r'\bDIRECTION\s+INPUT\s*;',match[1]):raise ValueError('only input control ports may be buffered')
        targets[net]=port
    if not targets:raise ValueError('measured input control targets required')
    boxes=f['macro_bboxes_dbu'];occupied=[(a-3000,b-3000,c+3000,d+3000) for a,b,c,d in boxes.values()]
    previous_plan=power/'placement_plan.json';old_plan=json.loads(previous_plan.read_text())
    for row in old_plan:
        x,y,width=row['x_nm'],row['y_nm'],row['width_nm'];occupied.append((x-1920,y-245,x+width+1920,y+SY+245))
    prior_receipt=prior/'assessment.json';prior_plan=prior/'placement_plan.json'
    previous=json.loads(prior_receipt.read_text());verify(previous['input_sha256']);verify(previous['artifacts'])
    if previous['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]) or previous['candidate_source_sha256']!=f['candidate_source_sha256']:
        raise ValueError('retained buffer placements must share the exact original power/frame')
    fixed={row['net']:row for row in json.loads(prior_plan.read_text())}
    if not set(fixed)<=set(targets):raise ValueError('historical successful control repairs must be retained')
    for row in fixed.values():
        x,y,width=row['x_nm'],row['y_nm'],row['width_nm'];occupied.append((x-1920,y-245,x+width+1920,y+SY+245))
    plan=[]
    for index,(net,port) in enumerate(sorted(targets.items())):
        width=480+4320+1440+480
        if net in fixed:
            row=fixed[net]
            if row['width_nm']!=width or row['port']!=port:raise ValueError('retained control port or footprint differs')
            x,y=row['x_nm'],row['y_nm']
        else:
            x,y=bank_site(port['point'],width,occupied)
            occupied.append((x-1920,y-245,x+width+1920,y+SY+245))
        plan.append(dict(net=net,port=port,x_nm=x,y_nm=y,width_nm=width,orient='R0',
             intermediate_net=f'prototype_control_inverted_{index}',output_net=f'prototype_control_buffered_{index}',
             first_instance=f'prototype_control_inv8_{index}',second_instance=f'prototype_control_inv2_{index}'))
    output.mkdir(parents=True,exist_ok=False);plan_path=output/'placement_plan.json';save(plan_path,plan)
    tcl=[f'read_db {{{power/"power.odb"}}}','set_thread_count 4','set block [ord::get_db_block]','set tech [ord::get_db_tech]',
         'foreach net {VPWR VGND} {set sw($net) [odb::dbSWire_create [$block findNet $net] ROUTED]}']
    bindings=list(p['parent_instance_bindings']);overrides=[]
    for index,row in enumerate(plan):
        x,y,width=row['x_nm'],row['y_nm'],row['width_nm']
        for name in (row['intermediate_net'],row['output_net']):
            tcl += [f'if {{[$block findNet {name}] ne {{NULL}}}} {{error "reserved control net collision"}}',f'odb::dbNet_create $block {name}']
        cells=[(f'prototype_control_tap_{index}_0','sky130_fd_sc_hs__tapvpwrvgnd_1',x,None,None),
               (row['first_instance'],'sky130_fd_sc_hs__inv_8',x+480,row['net'],row['intermediate_net']),
               (row['second_instance'],'sky130_fd_sc_hs__inv_2',x+480+4320,row['intermediate_net'],row['output_net']),
               (f'prototype_control_tap_{index}_1','sky130_fd_sc_hs__tapvpwrvgnd_1',x+width-480,None,None)]
        for name,master,xx,input_net,output_net in cells:
            tcl += [f'set inst [odb::dbInst_create $block [[ord::get_db] findMaster {master}] {name}]','$inst setOrient R0',f'$inst setLocation {xx} {y}','$inst setPlacementStatus FIRM']
            pins=[('VPWR','VPWR'),('VGND','VGND')]
            if input_net is not None:pins += [('VPB','VPWR'),('VNB','VGND'),('A',input_net),('Y',output_net)]
            for pin,net in pins:
                tcl.append(f'[$inst findITerm {pin}] connect [$block findNet {{{net}}}]');bindings.append([name,pin,net])
        pin=row['port']['pin'];old=row['net'];new=row['output_net']
        tcl += [f'set receiver [[$block findInst oscillator] findITerm {{{pin}}}]',f'if {{[[$receiver getNet] getName] ne {{{old}}}}} {{error "DCO receiver source changed"}}',f'$receiver connect [$block findNet {new}]']
        overrides.append(['oscillator',pin,old,new])
        px,gx=rails_for_bank((x,y,width),boxes.values())
        for net,tx,cy in [('VGND',gx,y),('VPWR',px,y+SY)]:
            tcl.append(f'odb::dbSBox_create $sw({net}) [$tech findLayer met1] {min(x,tx-245)} {cy-245} {max(x+width,tx+245)} {cy+245} STRIPE')
            for via in ('M1M2_PR','M2M3_PR','M3M4_PR'):tcl.append(f'odb::dbSBox_create $sw({net}) [$tech findVia {via}] {tx} {cy} STRIPE')
            tcl.append(f'odb::dbSBox_create $sw({net}) [$tech findLayer met3] {tx-300} {cy-300} {tx+300} {cy+300} STRIPE')
    proof=output/'composition.json';save(proof,dict(native_inverter_libraries=[str(path) for path in libraries],
         truth_table=[dict(input=a,first=1-a,output=a) for a in (0,1)],
         original_macro_connection_overrides=overrides,inverter_pairs=plan,
         Boolean_identity_proved=True,native_electrical_timing_qualified=False))
    tcl += [f'write_db {{{output/"power.odb"}}}',f'write_def {{{output/"power.def"}}}',f'write_verilog -include_pwr_gnd {{{output/"powered.v"}}}']
    for net in ('VPWR','VGND'):tcl.append(f'check_power_grid -net {net} -error_file {{{output/(net+"_errors.rpt")}}}')
    script=output/'buffer.tcl';script.write_text('\n'.join(tcl)+'\n')
    paths=[prior_receipt,prior_plan,*receipts,*libraries,records_path,previous_plan,lef,plan_path,proof,script,power/'power.odb',Path(OPENROAD),Path(__file__).resolve(),Path(__file__).with_name('protect_prototype_parent_periphery.py')]
    pins={str(path):sha(path) for path in paths};save(output/'input_manifest.json',dict(input_sha256=pins))
    os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',GOMAXPROCS='4')
    save(output/'status.json',dict(state='control_buffer_placement_and_power_running',release_ready=False))
    with lease(4,8,deadline):execute([OPENROAD,'-no_init','-exit',script],output/'buffer.log',deadline,8)
    log=(output/'buffer.log').read_text()
    if '[ERROR' in log or not all(f'All shapes on net {net} are connected.' in log for net in ('VPWR','VGND')):raise ValueError('buffer placement or PG nonpass')
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(path):sha(path) for path in output.iterdir() if path.is_file() and path.name!='status.json'},
         candidate_source_sha256=f['candidate_source_sha256'],parent_instance_bindings=bindings,macro_connection_overrides=overrides,
         control_buffer_composition_proved=True,control_buffer_composition_sha256=sha(proof),added_inverter_pairs=len(plan),prior_control_net_positions_retained=len(fixed),
         main_rail_database_connectivity_pass=True,macro_interiors_unchanged=True,
         parent_timing_and_control_response_qualified=False,antenna_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='control_buffers_placed_pending_reroute_and_signoff',release_ready=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('power','frame','localization','views','output','prior'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(*(getattr(args,n).resolve() for n in ('power','frame','localization','views','output','prior')))
