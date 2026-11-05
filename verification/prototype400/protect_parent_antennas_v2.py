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
import pya
from common import ROOT,save,sha,source_pins,verify
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import OPENROAD


def reg(b):return pya.Region(pya.Box(*b))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('power','localization','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();power=a.power.resolve();loc=a.localization.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    receipt=json.loads((power/'assessment.json').read_text());verify(receipt['input_sha256']);verify(receipt['artifacts'])
    located=json.loads((loc/'assessment.json').read_text());verify(located['input_sha256']);verify(located['artifacts'])
    assert located['violations_with_macro_port']==located['violations']
    records=json.loads((loc/'records.json').read_text());by_net={}
    for row in records:
        for port in row['macro_ports']:
            if port['net'] not in by_net or port['instance']=='oscillator':by_net[port['net']]=port
    boxes=json.loads((ROOT/'build/timing400/prototype_001/assembly_frame_001/assessment.json').read_text())['macro_bboxes_dbu']
    bodies=pya.Region()
    for b in boxes.values():bodies+=reg(b).sized(3000)
    occupied=bodies.dup();plan=[]
    for net,port in sorted(by_net.items()):
        cx,cy=port['point'];options=[]
        for row in range(max(0,(cy-100000-13320)//3330),min(248,(cy+100000-13320)//3330)+1):
            if row%2:continue
            y=13320+row*3330
            for col in range(max(0,(cx-100000-10080)//480),min(2033,(cx+100000-10080)//480)+1):
                x=10080+col*480;box=(x,y,x+4320,y+3330)
                if not (reg(box)&occupied).is_empty():continue
                options.append((abs(x+2160-cx)+abs(y+1665-cy),x,y,box))
        assert options,net
        distance,x,y,box=min(options);occupied+=reg((x-1920,y,x+4320+1920,y+3330))
        plan.append(dict(net=net,x_nm=x,y_nm=y,orient='R0',diodes=4,port=port,distance_nm=distance))
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
    lines += [f'write_db {{{out/"power.odb"}}}',f'write_def {{{out/"power.def"}}}',
              f'write_verilog -include_pwr_gnd {{{out/"powered.v"}}}',
              f'check_power_grid -net VPWR -error_file {{{out/"VPWR_errors.rpt"}}}',
              f'check_power_grid -net VGND -error_file {{{out/"VGND_errors.rpt"}}}']
    task=out/'protect.tcl';task.write_text('\n'.join(lines)+'\n')
    save(out/'placement_plan.json',plan);save(out/'power_plan.json',connections)
    pins=source_pins()
    for path in [Path(__file__).resolve(),Path(OPENROAD),power/'assessment.json',power/'power.odb',loc/'assessment.json',loc/'records.json',task]:pins[str(path)]=sha(path)
    save(out/'status.json',dict(state='protection_placement_and_power_running',release_qualified=False))
    with (out/'protect.log').open('x') as log:
        result=subprocess.run([OPENROAD,'-no_init','-exit',str(task)],stdout=log,stderr=subprocess.STDOUT,timeout=1800)
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
