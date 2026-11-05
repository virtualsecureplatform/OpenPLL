#!/usr/bin/env python3
"""Connect existing macro PG ports through external parent trunks.

Checks exact GDS metal5 clearance before adding geometry. Database continuity
is an intermediate check; assembled DRC/LVS and power integrity remain gates.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'verification/prototype400'))
from klayout_compat import pya
from common_v3 import ROOT, save, sha, verify
import time,os
from resources import lease
from compiled_charge import execute
from build_assembly_frame import expected, DCO
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import OPENROAD


def region(box):
    return pya.Region(pya.Box(*box))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frame',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args(); frame=a.frame.resolve(); out=a.output.resolve()
    checked=json.loads((frame/'assessment.json').read_text())
    assert checked['assembly_frame_pass']
    if checked.get('parent_floorplan_profile')!='compact_650x500_v1':raise ValueError('compact frame geometry required')
    verify(checked['input_sha256']);verify(checked['artifacts'])
    out.mkdir(parents=True,exist_ok=False)
    sources={name:(Path(view['lef']),Path(view['gds']),view['master'])
             for name,view in checked['macro_sources'].items()}
    assert set(sources)=={'digital','oscillator','detector'}
    pins=dict(checked['candidate_source_sha256'])
    for p in (Path(__file__).resolve(),ROOT/'verification/prototype400/klayout_compat.py',
              Path(sys.modules[pya.Layout.__module__].__file__),Path(sys.executable),Path(OPENROAD),frame/'assessment.json',frame/'floorplan.odb'):
        pins[str(p)]=sha(p)
    contexts={net:pya.Region() for net in ('VPWR','VGND')};unknown=pya.Region();ports=[]
    for inst,(lef,gds,master) in sources.items():
        pins[str(lef)]=sha(lef);pins[str(gds)]=sha(gds)
        x,y,_,_=checked['macro_bboxes_dbu'][inst]
        layout=pya.Layout();layout.read(str(gds));assert layout.dbu==.001
        cell=layout.cell(master);idx=layout.find_layer(72,20);assert cell and idx is not None
        actual=pya.Region(cell.begin_shapes_rec(idx)).transformed(pya.Trans(x,y))
        local=pya.Region()
        for pin,net in ([('VDD','VPWR'),('VSS','VGND')] if inst=='digital' else [('VPWR','VPWR'),('VGND','VGND')]):
            text=lef.read_text(); match=re.search(r'^\s*PIN '+pin+r'\s*$',text,re.M);assert match
            body=text[match.end():].split('END '+pin,1)[0]; layer=None; options=[]
            for line in body.splitlines():
                fields=line.split()
                if fields and fields[0]=='LAYER':layer=fields[1]
                if fields and fields[0]=='RECT' and layer=='met5':
                    coords=[Decimal(v)*1000 for v in fields[1:5]]
                    assert all(v==v.to_integral_value() for v in coords)
                    aa,bb,cc,dd=map(int,coords);box=(aa+x,bb+y,cc+x,dd+y)
                    r=region(box);assert (r-actual).is_empty(),(inst,pin,box,'LEF not in GDS')
                    contexts[net]+=r;local+=r;options.append(box)
            assert options
            # The lowest horizontal exposed port is in the existing perimeter ring.
            options=[b for b in options if b[3]-b[1]>=1600 and b[2]-b[0]>=1600]
            box=min(options,key=lambda b:(b[1],b[0])); cy=(box[1]+box[3])//2
            assert cy%5==0
            ports.append(dict(instance=inst,net=net,box=box,y=cy,
                              trunk_x=(20000 if inst=='digital' else 420000)+(10000 if net=='VGND' else 0)))
        unknown+=actual-local
    shapes=[];vias=[]
    for net in ('VPWR','VGND'):
        cy=50000 if net=='VPWR' else 60000
        shapes.append(dict(net=net,layer='met5',box=[18000,cy-800,432000,cy+800]))
        for x in ((20000,420000) if net=='VPWR' else (30000,430000)):
            top=max(p['y'] for p in ports if p['net']==net and p['trunk_x']==x)
            shapes.append(dict(net=net,layer='met4',box=[x-2000,cy-800,x+2000,top+800]))
            vias.append(dict(net=net,x=x,y=cy))
    for p in ports:
        x0,y0,x1,y1=p['box'];x=p['trunk_x'];cy=p['y']
        stub=[x-800,cy-800,x0+1600,cy+800]
        assert (region(stub)&unknown.sized(1600)).is_empty(),('unknown macro metal clearance',p)
        shapes.append(dict(net=p['net'],layer='met5',box=stub));vias.append(dict(net=p['net'],x=x,y=cy))
    combined={net:contexts[net].dup() for net in contexts}
    for s in shapes:
        if s['layer']=='met5':combined[s['net']]+=region(s['box'])
    assert (combined['VPWR']&combined['VGND'].sized(1599)).is_empty(),'opposite rail metal5 clearance'
    for s in shapes:
        for b in checked['macro_bboxes_dbu'].values():
            if s['layer']=='met4':assert (region(s['box'])&region(b).sized(3000)).is_empty()
    recipe=[f'read_db {{{frame/"floorplan.odb"}}}', 'set_thread_count 4',
      'set block [ord::get_db_block]','set tech [ord::get_db_tech]',
      'foreach bias {VPB VNB} {[$block findNet $bias] setSigType SIGNAL}',
      'set via [$tech findVia M4M5_PR]','if {$via == "NULL"} {error "missing M4M5 via"}']
    for net in contexts:
        recipe.append(f'set wire_{net} [odb::dbSWire_create [$block findNet {net}] ROUTED]')
    for s in shapes:
        recipe.append(f'odb::dbSBox_create $wire_{s["net"]} [$tech findLayer {s["layer"]}] '+ ' '.join(map(str,s['box']))+' STRIPE')
    for v in vias:
        recipe.append(f'odb::dbSBox_create $wire_{v["net"]} $via {v["x"]} {v["y"]} STRIPE')
    for net in contexts:
        cy=50000 if net=='VPWR' else 60000
        recipe += [f'set term [$block findBTerm {net}]',
            'set pin [odb::dbBPin_create $term]','$pin setPlacementStatus PLACED',
            f'odb::dbBox_create $pin [$tech findLayer met5] 195000 {cy-800} 205000 {cy+800}']
    recipe += [f'write_db {{{out/"power.odb"}}}',f'write_def {{{out/"power.def"}}}',
               f'write_verilog -include_pwr_gnd {{{out/"powered.v"}}}']
    for net in contexts:
        recipe.append(f'check_power_grid -net {net} -floorplanning -error_file {{{out/(net+"_errors.rpt")}}}')
    (out/'power.tcl').write_text('\n'.join(recipe)+'\n')
    save(out/'plan.json',dict(ports=ports,shapes=shapes,vias=vias))
    save(out/'status.json',dict(state='parent_power_running',started_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False))
    verify(pins)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.environ.update(GOMAXPROCS='4',OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1')
    with lease(4,8,deadline):execute([OPENROAD,'-no_init','-exit',out/'power.tcl'],out/'power.log',deadline,8)
    log=(out/'power.log').read_text()
    assert '[ERROR' not in log
    assert all(f'All shapes on net {net} are connected.' in log for net in contexts)
    verify(pins)
    save(out/'assessment.json',dict(input_sha256=pins,candidate_source_sha256=checked['candidate_source_sha256'],DCO_selection_provisional=True,release_ready=False,
         main_rail_database_connectivity_pass=True,
         macro_gds_metal5_port_and_clearance_preflight_pass=True,existing_macro_geometry_unchanged=True,
         assembled_drc_pass=False,assembled_lvs_pass=False,power_integrity_qualified=False,
         prototype_handoff_qualified=False,release_qualified=False,
         artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'}))
    save(out/'status.json',dict(state='parent_power_connectivity_pass_pending_assembled_signoff',completed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False))
    print('Parent power database connectivity and GDS port clearance preflight passed.')


if __name__=='__main__':main()
