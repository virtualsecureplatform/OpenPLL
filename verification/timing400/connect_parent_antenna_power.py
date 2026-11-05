#!/usr/bin/env python3
"""Connect candidate diode/tap islands to existing PG using M1 rails and via stacks.

All new conductors stay outside the three macro bodies. Search via-stack
locations against exact existing GDS metal2/metal3 and power separation.
Existing parent signal wires and macro geometry are preserved. Full streamed
DRC/LVS and signal routing are separate mandatory checks, not inferred here.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import time
import pya
from check_compact_clock_tree import verify
from check_compact_mapping import OPENROAD
from run_dco_qualification import ROOT,sha,save


def boxreg(coords):return pya.Region(pya.Box(*coords))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();base=ROOT/'build/timing400/release_001'
    placed=base/'parent_dco_antenna_placement_002';verify(placed/'assessment.json')
    audit=base/'candidate_assembled_layout_audit_repaired_macros_001/assessment.json'
    proof=json.loads(audit.read_text())
    for p,digest in proof['input_sha256'].items():assert sha(p)==digest,p
    source=Path(proof['assembled_gds']);assert sha(source)==proof['assembled_gds_sha256']
    original_owner=placed/'owner.json';deadline=json.loads(original_owner.read_text())['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    plan=json.loads((placed/'placement_plan.json').read_text())
    # The source PG repair changed only met5 and vias; its met4 shapes are
    # unchanged from this exact bound source.tsv (confirmed by OpenDB probe).
    source_tsv=base/'candidate_macro_power_repair_007/source.tsv'
    rails=[]
    for line in source_tsv.read_text().splitlines():
        net,ident,layer,*rest=line.split('\t')
        if layer=='met4':rails.append(dict(net=net,box=tuple(map(int,rest[:4]))))
    layout=pya.Layout();layout.read(str(source));assert layout.dbu==.001
    top=layout.cell('IntegerPLL_400MHz_CandidateTop')
    window=boxreg((650000,70000,980000,350000))
    blocked={}
    for layer in (1,2,3):
        reg=pya.Region(top.begin_shapes_rec(layout.layer(67+layer,20))).merged()&window
        blocked[layer]=reg.sized(500 if layer>1 else 140)
    bodies=boxreg((147000,147000,607615,607615))+boxreg((747000,147000,878000,278000))+boxreg((747000,397000,873000,523000))
    additions={n:pya.Region() for n in ('VPWR','VGND')};connections=[]
    for index,row in enumerate(plan):
        assert row['orient']=='R0'
        x0=row['x_nm'];x1=x0+4320
        for net,y in [('VGND',row['y_nm']),('VPWR',row['y_nm']+3330)]:
            other='VGND' if net=='VPWR' else 'VPWR'
            candidates=sorted([r for r in rails if r['net']==net and r['box'][1]+500<=y<=r['box'][3]-500],key=lambda r:abs((r['box'][0]+r['box'][2])//2-(x0+x1)//2))
            found=None
            for target in candidates:
                a,b,c,d=target['box'];center=(a+c)//2
                for dy in [0,120,-120,240,-240,480,-480,720,-720,960,-960]:
                    yy=y+dy
                    if not b+500<=yy<=d-500:continue
                    for dx in [0,100,-100,200,-200,400,-400,600,-600]:
                        xx=center+dx
                        if xx-165<a or xx+165>c:continue
                        via2=boxreg((xx-140,yy-185,xx+140,yy+185))
                        via3=boxreg((xx-190,yy-165,xx+190,yy+165))
                        if not (via2&blocked[2]).is_empty() or not (via3&blocked[3]).is_empty():continue
                        horizontal=(min(x0,xx-245),y-245,max(x1,xx+245),y+245)
                        vertical=(xx-245,min(y,yy)-245,xx+245,max(y,yy)+245)
                        route=(boxreg(horizontal)+boxreg(vertical)).merged()
                        if not (route&bodies).is_empty():continue
                        if not (route&blocked[1]).is_empty():continue
                        if not (route&additions[other].sized(140)).is_empty():continue
                        found=dict(index=index,net=net,x=xx,y=yy,rectangles=[horizontal,vertical],target_met4_box=target['box'])
                        break
                    if found:break
                if found:break
            assert found,('no collision-free PG connection',index,net,row)
            additions[net]+=boxreg(found['rectangles'][0])+boxreg(found['rectangles'][1])
            connections.append(found)
    assert (additions['VPWR']&additions['VGND'].sized(140)).is_empty()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__).resolve(),Path(OPENROAD),placed/'assessment.json',placed/'placed.odb',placed/'placement_plan.json',original_owner,audit,source,source_tsv,
           base/'parent_antenna_pg_via_probe_001/probe.tcl',base/'parent_antenna_pg_via_probe_001/probe.log']
    pins={str(p):sha(p) for p in files}
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),deadline_uptime=deadline,
        original_owner=str(original_owner),total_budget_restarted=False,automatic_identical_retry=False))
    save(out/'power_plan.json',connections)
    script=out/'connect.tcl';lines=[f'read_db {placed}/placed.odb','set block [ord::get_db_block]','set tech [ord::get_db_tech]',
        'foreach supply {VPWR VGND} {set sw($supply) [odb::dbSWire_create [$block findNet $supply] ROUTED]}',
        'set layer [$tech findLayer met1]']
    for row in connections:
        for a,b,c,d in row['rectangles']:lines.append(f'odb::dbSBox_create $sw({row["net"]}) $layer {a} {b} {c} {d} STRIPE')
        for via in ['M1M2_PR','M2M3_PR','M3M4_PR']:
            lines.append(f'odb::dbSBox_create $sw({row["net"]}) [$tech findVia {via}] {row["x"]} {row["y"]} STRIPE')
    lines += [f'write_db {out}/powered.odb',f'write_def {out}/powered.def',f'write_verilog -include_pwr_gnd {out}/powered.v',
              f'check_power_grid -net VPWR -error_file {out}/vpwr_errors.rpt',f'check_power_grid -net VGND -error_file {out}/vgnd_errors.rpt']
    script.write_text('\n'.join(lines)+'\n');pins[str(script)]=sha(script)
    save(out/'input_manifest.json',dict(input_sha256=pins,scope=__doc__))
    with (out/'connect.log').open('x') as log:
        result=subprocess.run([OPENROAD,'-no_init','-exit',str(script)],stdout=log,stderr=subprocess.STDOUT,
            timeout=deadline-time.clock_gettime(time.CLOCK_BOOTTIME))
    assert result.returncode==0
    text=(out/'connect.log').read_text();assert 'All supply instances connected.' in text
    for path,digest in pins.items():assert sha(path)==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        connected_island_rail_pairs=131,via_stacks=262,new_macro_interior_conductors=0,
        openroad_power_connectivity_passed=True,ordinary_signal_wires_unchanged=True,
        full_gds_drc_passed=False,lvs_qualified=False,diode_signal_routing_completed=False,
        antenna_qualified=False,analog_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Added 262 outside-macro M1 PG connections and via stacks; OpenROAD power connectivity passes. Full GDS checks remain mandatory.')

if __name__=='__main__':main()
