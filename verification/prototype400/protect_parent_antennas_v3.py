#!/usr/bin/env python3
"""Add four diodes and a local well tap beside each measured failing parent net.

Preserve three source macros and power ports. Rebuild signal routing afterwards;
placement/PG checks alone do not establish forming-stage antenna protection.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
from klayout_compat import pya
import time
from common import ROOT,save,sha,source_pins,verify
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import OPENROAD


def reg(b):return pya.Region(pya.Box(*b))


def main():
    started=time.monotonic();deadline=started+43200
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('power','localization','output'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--frame',type=Path,required=True)
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--reference',type=Path,required=True)
    a=p.parse_args();power=a.power.resolve();loc=a.localization.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    receipt=json.loads((power/'assessment.json').read_text());verify(receipt['input_sha256']);verify(receipt['artifacts'])
    located=json.loads((loc/'assessment.json').read_text());verify(located['input_sha256']);verify(located['artifacts'])
    assert located['violations_with_macro_port']==located['violations']
    records=json.loads((loc/'records.json').read_text());by_net={}
    for row in records:
        for port in row['macro_ports']:
            if port['net'] not in by_net or port['instance']=='oscillator':by_net[port['net']]=port
    frame=a.frame.resolve();planner=a.plan.resolve();reference=a.reference.resolve()
    frame_proof=json.loads((frame/'assessment.json').read_text());verify(frame_proof['input_sha256']);verify(frame_proof['artifacts'])
    assert frame_proof['assembly_frame_pass']
    assert receipt['input_sha256'][str(frame/'assessment.json')]==sha(frame/'assessment.json')
    plan_proof=json.loads((planner/'assessment.json').read_text());verify(plan_proof['input_sha256']);verify(plan_proof['artifacts'])
    ref=json.loads(reference.read_text());verify(ref['input_sha256'])
    assert ref['all_coordinates_and_ties_equal'] and ref['nets_compared']==len(by_net)
    assert ref['input_sha256'][str(planner/'assessment.json')]==sha(planner/'assessment.json')
    for path in (frame/'assessment.json',loc/'assessment.json',loc/'records.json'):
        assert plan_proof['input_sha256'][str(path)]==sha(path)
    rows=json.loads((planner/'plan.json').read_text())
    assert len(rows)==len(by_net) and [r['net'] for r in rows]==sorted(by_net)
    boxes=frame_proof['macro_bboxes_dbu']
    bodies=pya.Region()
    for b in boxes.values():bodies+=reg(b).sized(3000)
    occupied=bodies.dup();plan=[]
    for row in rows:
        net=row['net'];port=by_net[net];cx,cy=port['point']
        x,y=row['x_nm'],row['y_nm']
        assert type(x) is int and type(y) is int
        assert row['orient']=='R0' and row['diodes']==4
        assert (x-10080)%480==0 and (y-13320)%3330==0
        col=(x-10080)//480;grid_row=(y-13320)//3330
        assert grid_row%2==0
        assert max(0,(cy-100000-13320)//3330)<=grid_row<=min(248,(cy+100000-13320)//3330)
        assert max(0,(cx-100000-10080)//480)<=col<=min(2033,(cx+100000-10080)//480)
        box=(x,y,x+4320,y+3330)
        assert (reg(box)&occupied).is_empty(),('compiled bank geometry collision',net)
        distance=abs(x+2160-cx)+abs(y+1665-cy)
        assert row['distance_nm']==distance
        occupied+=reg((x-1920,y,x+4320+1920,y+3330))
        plan.append(dict(row,port=port))
    additions={n:pya.Region() for n in ('VPWR','VGND')};connections=[]
    for i,row in enumerate(plan):
        x0=row['x_nm'];x1=x0+4320
        for net,y in [('VGND',row['y_nm']),('VPWR',row['y_nm']+3330)]:
            candidates=[]
            for tx in ([100000,700000,900000] if net=='VPWR' else [110000,710000,910000]):
                box=(min(x0,tx-245),y-245,max(x1,tx+245),y+245)
                if not (reg(box)&bodies).is_empty():continue
                other='VGND' if net=='VPWR' else 'VPWR'
                if not (reg(box)&additions[other].sized(140)).is_empty():continue
                candidates.append((abs(tx-(x0+x1)//2),tx,box))
            assert candidates,(net,row)
            _,tx,box=min(candidates);additions[net]+=reg(box)
            connections.append(dict(net=net,x=tx,y=y,box=box))
    assert (additions['VPWR']&additions['VGND'].sized(140)).is_empty()
    lines=[f'read_db {{{power/"power.odb"}}}','set_thread_count 2','set block [ord::get_db_block]',
           'set tech [ord::get_db_tech]','foreach net {VPWR VGND} {set sw($net) [odb::dbSWire_create [$block findNet $net] ROUTED]}']
    bindings=[]
    for i,row in enumerate(plan):
        tap=f'prototype_ant_tap_{i:03d}'
        lines += [f'set tap [odb::dbInst_create $block [[ord::get_db] findMaster sky130_fd_sc_hs__tapvpwrvgnd_1] {tap}]',
                  f'$tap setLocation {row["x_nm"]} {row["y_nm"]}','$tap setPlacementStatus FIRM',
                  '[$tap findITerm VPWR] connect [$block findNet VPWR]','[$tap findITerm VGND] connect [$block findNet VGND]']
        bindings.extend([[tap,'VPWR','VPWR'],[tap,'VGND','VGND']])
        for number in range(4):
            name=f'prototype_ant_{i:03d}_{number}'
            lines += [f'set inst [odb::dbInst_create $block [[ord::get_db] findMaster sky130_fd_sc_hs__diode_2] {name}]',
                      f'$inst setLocation {row["x_nm"]+480+number*960} {row["y_nm"]}','$inst setPlacementStatus FIRM',
                      f'[$inst findITerm DIODE] connect [$block findNet {{{row["net"]}}}]',
                      'foreach pin {VPWR VPB} {[$inst findITerm $pin] connect [$block findNet VPWR]}',
                      'foreach pin {VGND VNB} {[$inst findITerm $pin] connect [$block findNet VGND]}']
            bindings += [[name,'DIODE',row['net']]]+[[name,p,'VPWR'] for p in ('VPWR','VPB')]+[[name,p,'VGND'] for p in ('VGND','VNB')]
    for net in ('VPWR','VGND'):
        for tx in ([100000,700000] if net=='VPWR' else [110000,710000]):
            cy=50000 if net=='VPWR' else 60000
            lines.append(f'odb::dbSBox_create $sw({net}) [$tech findLayer met4] {tx-2000} {cy-800} {tx+2000} 800000 STRIPE')
        cy=50000 if net=='VPWR' else 60000;tx=900000 if net=='VPWR' else 910000
        lines += [f'odb::dbSBox_create $sw({net}) [$tech findLayer met5] 698000 {cy-800} 912000 {cy+800} STRIPE',
                  f'odb::dbSBox_create $sw({net}) [$tech findLayer met4] {tx-2000} {cy-800} {tx+2000} 800000 STRIPE',
                  f'odb::dbSBox_create $sw({net}) [$tech findVia M4M5_PR] {tx} {cy} STRIPE']
    seen=set()
    for r in connections:
        net,x,y=r['net'],r['x'],r['y']
        lines.append(f'odb::dbSBox_create $sw({net}) [$tech findLayer met1] '+ ' '.join(map(str,r['box']))+' STRIPE')
        if (net,x,y) in seen:continue
        seen.add((net,x,y))
        for via in ('M1M2_PR','M2M3_PR','M3M4_PR'):
            lines.append(f'odb::dbSBox_create $sw({net}) [$tech findVia {via}] {x} {y} STRIPE')
        # Full-rule intermediate metal3 area, beyond LEF-only router checks.
        lines.append(f'odb::dbSBox_create $sw({net}) [$tech findLayer met3] {x-300} {y-300} {x+300} {y+300} STRIPE')
    lines += ['check_placement -verbose',f'write_db {{{out/"power.odb"}}}',f'write_def {{{out/"power.def"}}}',
              f'write_verilog -include_pwr_gnd {{{out/"powered.v"}}}',
              f'check_power_grid -net VPWR -error_file {{{out/"VPWR_errors.rpt"}}}',
              f'check_power_grid -net VGND -error_file {{{out/"VGND_errors.rpt"}}}']
    task=out/'protect.tcl';task.write_text('\n'.join(lines)+'\n')
    save(out/'placement_plan.json',plan);save(out/'power_plan.json',connections)
    pins=source_pins()
    for p in (frame/'assessment.json',planner/'assessment.json',planner/'plan.json',reference,Path(__file__).with_name('klayout_compat.py'),Path(sys.modules[pya.Layout.__module__].__file__)):
        pins[str(p)]=sha(p)
    for path in [Path(__file__).resolve(),Path(OPENROAD),power/'assessment.json',power/'power.odb',loc/'assessment.json',loc/'records.json',task]:pins[str(path)]=sha(path)
    save(out/'status.json',dict(state='protection_placement_and_power_running',release_qualified=False))
    if time.monotonic()>=deadline:raise TimeoutError('whole-check budget exhausted before bank application')
    with (out/'protect.log').open('x') as log:
        result=subprocess.run([OPENROAD,'-no_init','-exit',str(task)],stdout=log,stderr=subprocess.STDOUT,timeout=min(1800,max(.001,deadline-time.monotonic())))
    if result.returncode:
        save(out/'status.json',dict(state='failed',reason='CAD placement/PG nonpass',release_qualified=False))
        raise RuntimeError((out/'protect.log').read_text()[-2500:])
    text=(out/'protect.log').read_text();assert '[ERROR' not in text
    assert all(f'All shapes on net {n} are connected.' in text for n in ('VPWR','VGND'))
    verify(pins)
    save(out/'assessment.json',dict(input_sha256=pins,protected_net_candidates=len(plan),added_diodes=4*len(plan),
         added_taps=len(plan),parent_instance_bindings=bindings,main_rail_database_connectivity_pass=True,
         macro_interiors_unchanged=True,placement_and_pg_only=True,antenna_qualified=False,release_qualified=False,
         artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'}))
    save(out/'status.json',dict(state='protection_placed_and_powered_pending_reroute',completed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False))
    print('Protected net candidates',len(plan),'diodes',4*len(plan))


if __name__=='__main__':main()
