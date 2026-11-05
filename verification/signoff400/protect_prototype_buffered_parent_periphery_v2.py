"""Add measured antenna diodes while retaining every existing buffer and diode.

Banks surround the macros near the actual protected ports.
Bank sizing includes a twenty-five-percent etch allowance. It is a repair
candidate; rerouted native antenna, DRC/LVS and loading checks remain required.
"""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import time
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge import execute
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import OPENROAD

X0,Y0,SX,SY=10080,13320,480,3330

def diode_count(record,area):
    if area<=0 or record['stage'] not in ('m3','m4'):
        raise ValueError('reviewed diode area and measured metal3/4 target required')
    required=(1.25*record['ratio']-400-2200)/400-record['diffusion_area_um2']
    return max(4,math.ceil(max(0,required)/area))

def bank_site(point,width,occupied):
    """Exact nearest legal grid site around the unchanged compact macros."""
    lo=0;hi=math.floor((640000-width-X0)/SX)
    best=None
    for row in range(0,140,2):
        y=Y0+row*SY
        if y<70000 or y+SY>480000:continue
        blocked=[]
        for a,b,c,d in occupied:
            if y>=d or y+SY<=b:continue
            first=max(lo,math.floor((a-width-X0)/SX)+1)
            last=min(hi,math.ceil((c-X0)/SX)-1)
            if first<=last:blocked.append((first,last))
        cursor=lo;gaps=[]
        for first,last in sorted(blocked):
            if cursor<first:gaps.append((cursor,first-1))
            cursor=max(cursor,last+1)
        if cursor<=hi:gaps.append((cursor,hi))
        near=math.floor((point[0]-width/2-X0)/SX)
        for first,last in gaps:
            for col in (max(first,min(last,near)),max(first,min(last,near+1))):
                x=X0+col*SX
                score=(abs(x+width/2-point[0])+abs(y+SY/2-point[1]),x,y)
                if best is None or score<best:best=score
    if best is None:raise ValueError('no legal protection bank site')
    return best[1:]

def rails_for_bank(bank,macro_boxes):
    x,y,width=bank;choices=[]
    boxes=[(a-3000,b-3000,c+3000,d+3000) for a,b,c,d in macro_boxes]
    for px,gx in ((20000,30000),(420000,430000),(600000,610000)):
        clear=True
        for tx,cy in ((px,y+SY),(gx,y)):
            box=(min(x,tx-245),cy-245,max(x+width,tx+245),cy+245)
            if any(box[0]<c and box[2]>a and box[1]<d and box[3]>b for a,b,c,d in boxes):clear=False
        if clear:choices.append((abs(px-(x+width/2))+abs(gx-(x+width/2)),px,gx))
    if not choices:raise ValueError('no macro-clear rail connection for peripheral bank')
    _,px,gx=min(choices);return px,gx


def run(power,frame,localization,output):
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    receipts=[p/'assessment.json' for p in (power,frame,localization)]
    p,f,l=[json.loads(path.read_text()) for path in receipts]
    for record in (p,f,l):verify(record['input_sha256']);verify(record['artifacts'])
    if not p['main_rail_database_connectivity_pass'] or not f['assembly_frame_pass'] or l['violations']!=l['violations_with_macro_port']:
        raise ValueError('checked compact power/frame and fully mapped antenna failures required')
    if f.get('parent_floorplan_profile')!='compact_650x500_v1' or p['input_sha256'].get(str(receipts[1]))!=sha(receipts[1]) or l['input_sha256'].get(str(receipts[1]))!=sha(receipts[1]):
        raise ValueError('matching compact source frame required')
    import pya
    digital=Path(f['macro_sources']['digital']['gds']);layout=pya.Layout();layout.read(str(digital))
    if layout.dbu!=.001:raise ValueError('one-nm source geometry grid required')
    diode=layout.cell('sky130_fd_sc_hs__diode_2');tap=layout.cell('sky130_fd_sc_hs__tapvpwrvgnd_1')
    if diode is None or tap is None:raise ValueError('actual source diode and tap geometry required')
    diffusion=pya.Region(diode.begin_shapes_rec(layout.layer(65,20)))
    poly=pya.Region(diode.begin_shapes_rec(layout.layer(66,20)))
    area=(diffusion-poly).merged().area()*1e-6
    if abs(area-.6417)>1e-9:raise ValueError('reviewed diode geometry differs')
    # Nominal site bounds plus actual source-cell geometric protrusions.
    for cell,width in ((diode,960),(tap,480)):
        if cell.bbox()!=pya.Box(-190,-245,width+190,SY+245):
            raise ValueError('source protection cell footprint differs')
    if not p.get('control_buffer_composition_proved') or p['control_buffer_composition_sha256']!=sha(power/'composition.json'):
        raise ValueError('identity-proved buffered source required')
    records_path=localization/'records.json';records=json.loads(records_path.read_text());targets={}
    for record in records:
        nets={port['net'] for port in record['macro_ports']}
        if len(nets)!=1:raise ValueError('one logical net per measured component required')
        net=next(iter(nets))
        if any(c in net for c in '{}\\\r\n'):raise ValueError('unsupported net name')
        port=min(record['macro_ports'],key=lambda port:port['instance']!='oscillator')
        count=diode_count(record,area)
        previous=targets.get(net)
        if previous is None or count>previous['diodes']:
            targets[net]=dict(net=net,diodes=count,port=port)
    occupied=[(a-3000,b-3000,c+3000,d+3000) for a,b,c,d in f['macro_bboxes_dbu'].values()]
    inherited_plans={Path(name) for name in p['input_sha256'] if name.endswith(('/placement_plan.json','/diode_placement_plan.json'))}|{power/'placement_plan.json'}|({power/'diode_placement_plan.json'} if (power/'diode_placement_plan.json').exists() else set())
    for path in inherited_plans:
        for row in json.loads(path.read_text()):
            x,y,width=row['x_nm'],row['y_nm'],row['width_nm']
            occupied.append((x-1920,y-245,x+width+1920,y+SY+245))
    plan=[]
    for net,row in sorted(targets.items()):
        width=960+960*row['diodes'];x,y=bank_site(row['port']['point'],width,occupied)
        occupied.append((x-1920,y-245,x+width+1920,y+SY+245))
        plan.append(dict(row,x_nm=x,y_nm=y,width_nm=width,orient='R0'))
    output.mkdir(parents=True,exist_ok=False)
    for name in ('composition.json','placement_plan.json'):
        (output/name).write_bytes((power/name).read_bytes())
    plan_path=output/'diode_placement_plan.json';save(plan_path,plan)
    tcl=[f'read_db {{{power/"power.odb"}}}','set_thread_count 4','set block [ord::get_db_block]','set tech [ord::get_db_tech]',
         'foreach net {VPWR VGND} {set sw($net) [odb::dbSWire_create [$block findNet $net] ROUTED]}']
    bindings=list(p['parent_instance_bindings'])
    for index,row in enumerate(plan):
        x,y,width=row['x_nm'],row['y_nm'],row['width_nm']
        cells=[(f'prototype_extra_tap_{output.name}_{index}_{side}', 'sky130_fd_sc_hs__tapvpwrvgnd_1',xx,None) for side,xx in enumerate((x,x+width-480))]
        cells += [(f'prototype_extra_ant_{output.name}_{index}_{n}','sky130_fd_sc_hs__diode_2',x+480+n*960,row['net']) for n in range(row['diodes'])]
        for name,master,xx,signal in cells:
            tcl += [f'set inst [odb::dbInst_create $block [[ord::get_db] findMaster {master}] {name}]',
                    '$inst setOrient R0',f'$inst setLocation {xx} {y}','$inst setPlacementStatus FIRM']
            pins=[('VPWR','VPWR'),('VGND','VGND')]
            if signal is not None:pins += [('VPB','VPWR'),('VNB','VGND'),('DIODE',signal)]
            for pin,net in pins:
                tcl.append(f'[$inst findITerm {pin}] connect [$block findNet {{{net}}}]');bindings.append([name,pin,net])
        px,gx=rails_for_bank((x,y,width),f['macro_bboxes_dbu'].values())
        for net,tx,cy in [('VGND',gx,y),('VPWR',px,y+SY)]:
            tcl.append(f'odb::dbSBox_create $sw({net}) [$tech findLayer met1] {min(x,tx-245)} {cy-245} {max(x+width,tx+245)} {cy+245} STRIPE')
            for via in ('M1M2_PR','M2M3_PR','M3M4_PR'):
                tcl.append(f'odb::dbSBox_create $sw({net}) [$tech findVia {via}] {tx} {cy} STRIPE')
            tcl.append(f'odb::dbSBox_create $sw({net}) [$tech findLayer met3] {tx-300} {cy-300} {tx+300} {cy+300} STRIPE')
    tcl += [f'write_db {{{output/"power.odb"}}}',f'write_def {{{output/"power.def"}}}',f'write_verilog -include_pwr_gnd {{{output/"powered.v"}}}']
    for net in ('VPWR','VGND'):
        tcl.append(f'check_power_grid -net {net} -error_file {{{output/(net+"_errors.rpt")}}}')
    script=output/'protect.tcl';script.write_text('\n'.join(tcl)+'\n')
    paths=[power/'composition.json',power/'placement_plan.json',*inherited_plans,*receipts,records_path,digital,plan_path,script,power/'power.odb',Path(OPENROAD),Path(__file__).resolve(),Path(sys.modules[pya.Layout.__module__].__file__)]
    pins=dict(p['input_sha256']);pins.update({str(path):sha(path) for path in paths})
    save(output/'input_manifest.json',dict(input_sha256=pins,diode_diffusion_area_um2=area,etch_allowance_factor=1.25))
    save(output/'status.json',dict(state='protection_placement_and_power_running',release_ready=False))
    os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',GOMAXPROCS='4')
    with lease(4,8,deadline):
        execute([OPENROAD,'-no_init','-exit',script],output/'protect.log',deadline,8)
    text=(output/'protect.log').read_text()
    if '[ERROR' in text or not all(f'All shapes on net {net} are connected.' in text for net in ('VPWR','VGND')):
        raise ValueError('protection placement or main-rail connectivity failed')
    verify(pins)
    result=dict(p)
    result.update(input_sha256=pins,candidate_source_sha256=f['candidate_source_sha256'],
         artifacts={str(path):sha(path) for path in output.iterdir() if path.is_file() and path.name!='status.json'},
         parent_instance_bindings=bindings,additional_protected_net_candidates=len(plan),additional_diodes=sum(r['diodes'] for r in plan),
         additional_taps=2*len(plan),main_rail_database_connectivity_pass=True,macro_interiors_unchanged=True,
         all_prior_parent_leaf_bindings_retained=True,control_buffer_composition_preserved=True,
         placement_and_pg_only=True,antenna_qualified=False,release_ready=False)
    save(output/'assessment.json',result)
    save(output/'status.json',dict(state='protection_placed_pending_reroute_and_signoff',release_ready=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('power','frame','localization','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(args.power.resolve(),args.frame.resolve(),args.localization.resolve(),args.output.resolve())
