#!/usr/bin/env python3
"""Replace intrusive macro PG overlays with connections to existing macro ports.

Preserves ordinary signal wires and source macro GDS. Full layout checks are
mandatory after this repair; OpenDB connectivity alone is insufficient.
"""
import argparse
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import re
import subprocess
import sys

import pya

from check_compact_clock_tree import verify
from check_compact_mapping import OPENROAD
from run_dco_qualification import ROOT,sha,save


def region(boxes):
    result=pya.Region()
    for box in boxes:result.insert(pya.Box(*box))
    return result.merged()


def run(out,name,text):
    path=out/(name+'.tcl');path.write_text(text)
    with (out/(name+'.log')).open('w') as log:
        subprocess.run([OPENROAD,'-no_init','-exit',str(path)],stdout=log,
                       stderr=subprocess.STDOUT,check=True,timeout=1800)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();out=args.output.resolve();assert not out.exists()
    base=ROOT/'build/timing400/release_001';route=base/'candidate_detailed_route_002'
    verify(base/'candidate_detailed_route_audit_001/assessment.json')
    streamed=verify(base/'candidate_stream_002/assessment.json')
    out.mkdir(parents=True)
    run(out,'source',f'''read_db {route}/route.odb
set f [open {out}/source.tsv w]
set serial 0
foreach supply {{VPWR VGND}} {{
    foreach wire [[[ord::get_db_block] findNet $supply] getSWires] {{
        foreach box [$wire getWires] {{
            incr serial
            set layer VIA
            set template -
            if {{[$box isVia]}} {{set template [[$box getBlockVia] getName]}} else {{set layer [[$box getTechLayer] getName]}}
            puts $f [join [list $supply $serial $layer [$box xMin] [$box yMin] [$box xMax] [$box yMax] $template] "\\t"]
        }}
    }}
}}
close $f
''')
    shapes=[]
    for line in (out/'source.tsv').read_text().splitlines():
        net,ident,layer,*rest=line.split('\t')
        shapes.append(dict(net=net,index=int(ident),layer=layer,box=tuple(map(int,rest[:4])),template=rest[4]))
    definitions={}
    section=(route/'route.def').read_text().split('VIAS ',1)[1].split('END VIAS',1)[0]
    for name,body in re.findall(r'-\s+(\S+)\s+([^;]+);',section):
        cut=tuple(map(int,re.search(r'CUTSIZE (\d+) (\d+)',body).groups()))
        enc=tuple(map(int,re.search(r'ENCLOSURE (\d+) (\d+) (\d+) (\d+)',body).groups()))
        definitions[name]=(cut[0]+2*enc[2],cut[1]+2*enc[3])
    placement=json.loads((base/'candidate_floorplan_003/assessment.json').read_text())['placements']
    source_manifest=json.loads((base/'candidate_stream_002/input_manifest.json').read_text())
    source_paths=[Path(p) for p in source_manifest['input_sha256'] if p.endswith('.gds')]
    lef_paths=[Path(p) for p in source_manifest['input_sha256'] if p.endswith('.lef')]
    contexts={n:pya.Region() for n in ('VPWR','VGND')}
    unknown=pya.Region();bodies=[];ports=[];macro_inputs=[]
    for instance,record in placement.items():
        name=record['master'];a,b,c,d=record['bbox_dbu'];bodies.append((a,b,c,d))
        lef=next(p for p in lef_paths if re.search(r'^MACRO '+re.escape(name)+r'\s*$',p.read_text(),re.M))
        gds=next(p for p in source_paths if (name=='IntegerPLL_AcquiringCore' and p.name=='route.gds') or p.stem==name or (name=='IntegerPLL_BBPD' and p.name=='IntegerPLL_BBPD.magic.gds'))
        layout=pya.Layout();layout.read(str(gds));assert layout.dbu==.001
        cell=layout.cell(name);idx=layout.find_layer(72,20);assert cell is not None and idx is not None
        actual=pya.Region(cell.begin_shapes_rec(idx)).transformed(pya.Trans(a,b))
        local=pya.Region()
        for pin,net in ([('VDD','VPWR'),('VSS','VGND')] if instance=='digital' else [('VPWR','VPWR'),('VGND','VGND')]):
            text=lef.read_text();match=re.search(r'^\s*PIN '+re.escape(pin)+r'\s*$',text,re.M);assert match
            body=text[match.end():].split('END '+pin,1)[0];layer=None
            for line in body.splitlines():
                fields=line.split()
                if fields and fields[0]=='LAYER':layer=fields[1]
                if fields and fields[0]=='RECT' and layer=='met5':
                    coords=[Decimal(v)*1000 for v in fields[1:5]]
                    assert all(v==v.to_integral_value() for v in coords)
                    x0,y0,x1,y1=map(int,coords);box=(x0+a,y0+b,x1+a,y1+b)
                    ports.append(dict(instance=instance,net=net,box=box))
                    piece=region([box]);assert (piece-actual).is_empty()
                    contexts[net]+=piece;local+=piece
        unknown+=actual-local
        macro_inputs.extend([lef,gds])
    body_region=region(bodies);guard=body_region.sized(3000)
    removed=set()
    for s in shapes:
        if s['layer']=='met5' and not (region([s['box']])&body_region).is_empty():removed.add(s['index'])
        if s['layer']=='VIA' and not (region([s['box']])&guard).is_empty():removed.add(s['index'])
    stubs={n:pya.Region() for n in contexts};targets=[]
    for port in ports:
        net=port['net'];x0,y0,x1,y1=port['box'];ym=(y0+y1)//2
        assert y1-y0>=1600 and (y0+y1)%2==0 and ym%5==0
        candidates=[]
        for s in shapes:
            if s['net']!=net or s['layer']!='met4':continue
            aa,bb,cc,dd=s['box'];xx=(aa+cc)//2
            if cc<=x0-3000 and cc-aa>=1600 and bb<=ym-800 and dd>=ym+800:
                if (region([s['box']])&guard).is_empty():candidates.append(s)
        assert candidates,port
        target=max(candidates,key=lambda s:s['box'][2]);xx=(target['box'][0]+target['box'][2])//2
        stub=(xx-800,ym-800,x0+1600,ym+800)
        assert (region([stub])&unknown.sized(1600)).is_empty(),('unknown macro metal5',port)
        stubs[net]+=region([stub]);targets.append(dict(net=net,x=xx,y=ym,port=port,stub=stub))
    for net,other in [('VPWR','VGND'),('VGND','VPWR')]:
        assert ((contexts[net]+stubs[net])&(contexts[other]+stubs[other]).sized(1599)).is_empty(),('protected PG conflict',net)
    via_regions={n:pya.Region() for n in contexts};centers=[]
    for s in shapes:
        if s['layer']!='VIA' or s['index'] in removed:continue
        a,b,c,d=s['box'];x,y=(a+c)//2,(b+d)//2
        w,h=definitions[s['template']];foot=(x-w//2,y-h//2,x+w//2,y+h//2)
        other='VGND' if s['net']=='VPWR' else 'VPWR'
        if not (region([foot])&(contexts[other]+stubs[other]).sized(1600)).is_empty():removed.add(s['index']);continue
        via_regions[s['net']]+=region([foot]);centers.append((x,y))
    added_vias=[]
    for target in targets:
        x,y=target['x'],target['y']
        if any(abs(x-a)<2000 and abs(y-b)<2000 for a,b in centers):continue
        centers.append((x,y));added_vias.append(target)
        via_regions[target['net']]+=region([(x-800,y-800,x+800,y+800)])
    initial={}
    for net,other in [('VPWR','VGND'),('VGND','VPWR')]:
        existing=region([s['box'] for s in shapes if s['net']==net and s['layer']=='met5' and s['index'] not in removed])
        initial[net]=(existing-(contexts[other]+stubs[other]).sized(1600))+stubs[net]+via_regions[net]
    final={}
    for net,other in [('VPWR','VGND'),('VGND','VPWR')]:
        combined=(initial[net]+contexts[net]).merged()
        fill=combined.sized(800).sized(-800)-combined
        fill-=body_region
        fill-=(initial[other]+contexts[other]+stubs[other]).sized(1600)
        fill-=unknown.sized(1600)
        final[net]=(initial[net]+fill).merged()
    assert ((final['VPWR']+contexts['VPWR'])&(final['VGND']+contexts['VGND']).sized(1599)).is_empty(),'PG spacing/short remains'
    rectangles=[]
    for net,r in final.items():
        for polygon in r.decompose_trapezoids_to_region().each():
            box=polygon.bbox();assert polygon.area()==box.area()
            rectangles.append((net,box.left,box.bottom,box.right,box.top))
    recipe=[f'read_db {route}/route.odb','set_thread_count 2','set block [ord::get_db_block]','set serial 0']
    # Replace top-level met5; source macro metal is represented only by the GDS macro.
    ids={s['index'] for s in shapes if s['layer']=='met5'}|removed
    recipe += ['foreach supply {VPWR VGND} {',' foreach wire [[$block findNet $supply] getSWires] {','  foreach box [$wire getWires] {',
        '   incr serial','   if {$serial in {'+' '.join(map(str,sorted(ids)))+'}} {odb::dbSBox_destroy $box}', '  }',' }','}',
        'set layer [[ord::get_db_tech] findLayer met5]']
    for net in ('VPWR','VGND'):
        recipe.append(f'set wire_{net} [odb::dbSWire_create [$block findNet {net}] ROUTED]')
    for net,a,b,c,d in rectangles:recipe.append(f'odb::dbSBox_create $wire_{net} $layer {a} {b} {c} {d} STRIPE')
    recipe.append('set via [$block findVia via5_6_1600_1600_1_1_1600_1600]')
    for via in added_vias:recipe.append(f'odb::dbSBox_create $wire_{via["net"]} $via {via["x"]} {via["y"]} STRIPE')
    for net in ('VPWR','VGND'):
        rings=[s for s in shapes if s['net']==net and s['layer']=='met5' and s['box'][2]-s['box'][0]>900000]
        assert rings
        a,b,c,d=min(rings,key=lambda s:s['box'][1])['box']
        pin=(495000,b,505000,d)
        assert (region([pin])-final[net]).is_empty()
        recipe += [f'set term [$block findBTerm {net}]','foreach pin [$term getBPins] {odb::dbBPin_destroy $pin}',
            'set pin [odb::dbBPin_create $term]','$pin setPlacementStatus PLACED',
            f'odb::dbBox_create $pin $layer {pin[0]} {pin[1]} {pin[2]} {pin[3]}']
    recipe += ['foreach supply {VPWR VGND} {foreach wire [[$block findNet $supply] getSWires] {if {![llength [$wire getWires]]} {odb::dbSWire_destroy $wire}}}',
        f'write_db {out}/route.odb',f'write_def {out}/route.def',
        f'write_verilog -include_pwr_gnd {out}/powered_top.v',
        f'check_power_grid -net VPWR -floorplanning -error_file {out}/vpwr_errors.rpt',
        f'check_power_grid -net VGND -floorplanning -error_file {out}/vgnd_errors.rpt']
    plan=dict(removed_power_objects=sorted(removed),new_port_stubs=targets,new_vias=added_vias,
              metal5_rectangles=rectangles,release_qualified=False)
    save(out/'repair_plan.json',plan)
    run(out,'repair','\n'.join(recipe)+'\n')
    original=(route/'route.def').read_text();changed=(out/'route.def').read_text()
    def signal_section(text):return text.split('\nNETS ',1)[1].split('\nEND NETS',1)[0]
    assert signal_section(original)==signal_section(changed),'ordinary signal routes changed'
    files=[Path(__file__).resolve(),Path(sys.executable),Path(OPENROAD),route/'route.odb',route/'route.def',
        base/'candidate_detailed_route_audit_001/assessment.json',base/'candidate_stream_002/assessment.json',*macro_inputs]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        source_macro_gds_unchanged=True,ordinary_signal_def_routes_unchanged=True,
        main_rail_connectivity_passed=True,intrusive_macro_power_overlay_removed=True,
        port_stubs=len(targets),added_external_vias=len(added_vias),
        full_assembled_drc_passed=False,assembled_lvs_passed=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Replaced macro-interior PG overlays with port stubs; ordinary signal routes preserved.')


if __name__=='__main__':
    main()
