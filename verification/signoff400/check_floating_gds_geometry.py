#!/usr/bin/env python3
"""Match native floating-node probes/classes to exact GDS conductor polygons.

Run inside the pinned CAD image. This is geometry attribution only; no finite-R
basis, resistance unit/PVT model, arithmetic attachment or release is qualified.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import time
import pya
MATERIALS={'m1':(68,'metal1','metal1'),'m2':(69,'metal2','metal2'),'m3':(70,'metal3','metal3'),'m4':(71,'metal4','metal4'),'m5':(72,'metal5','metal5'),'li':(67,'locali','locali'),'p':(66,'active','poly')}

def run(gds,nodes,output,native_type,unit_um=.005,limit=0,deadline=None):
    if deadline is None:deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    def check():
        if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('floating GDS geometry deadline')
    check();out=Path(output);out.mkdir(parents=True,exist_ok=False)
    layer,plane,material=MATERIALS[native_type];layout=pya.Layout();layout.read(str(gds));top=layout.top_cell()
    if top is None:raise ValueError('one GDS top cell required')
    li=layout.find_layer(layer,20)
    if li is None:raise ValueError('native conductor layer absent from GDS')
    ratio=unit_um/layout.dbu;scale=round(ratio)
    if scale<=0 or abs(ratio-scale)>1e-10:raise ValueError('native grid is not an exact integer GDS grid multiple')
    connected=pya.Region(top.begin_shapes_rec(li)).merged()
    lookup=pya.Layout();lookup.dbu=layout.dbu;cell=lookup.create_cell('FLOATING_LOOKUP');index=lookup.layer(1,0);cell.shapes(index).insert(connected)
    dbu=layout.dbu;del connected,layout
    counts=Counter();seen={};started=time.clock_gettime(time.CLOCK_BOOTTIME)
    with Path(nodes).open() as stream,(out/'nodes.jsonl').open('x') as rows:
        for line in stream:
            if limit and counts['nodes']>=limit:break
            if counts['nodes']%1000==0:check()
            row=json.loads(line);name=row['original_conductor']
            if row['native_type']!=native_type:raise ValueError('native type partition mismatch')
            counts['nodes']+=1;x,y=(int(v)*scale for v in row['point_internal']);point=pya.Point(x,y)
            iterator=cell.begin_shapes_rec_overlapping(index,pya.Box(x,y,x+1,y+1));candidates=[]
            while not iterator.at_end():
                shape=iterator.shape();poly=pya.Polygon(shape.box) if shape.is_box() else shape.polygon
                if poly.inside(point):candidates.append(poly)
                iterator.next()
            result=dict(original_conductor=name,field_ids=row['field_ids'],point_gds_dbu=[x,y],candidate_polygons=len(candidates),exact_rectangle_geometry=False)
            if len(candidates)==1:
                counts['one_polygon']+=1;poly=candidates[0];box=poly.bbox();bbox=(box.left,box.bottom,box.right,box.top)
                area=poly.area();perimeter=poly.perimeter();rectangle=area==box.area() and poly.holes()==0
                if rectangle:counts['rectangle']+=1
                classes=row['native_classes'];one_class=len(classes)==1
                area_equal=one_class and area==classes[0]['area_internal_squared']*scale*scale
                perimeter_equal=one_class and perimeter==classes[0]['perimeter_internal']*scale
                spatial=row['spatial_field_keys'];material_equal=not spatial or spatial==[[plane,material]]
                if area_equal:counts['area_equal']+=1
                if perimeter_equal:counts['perimeter_equal']+=1
                if material_equal:counts['spatial_material_equal']+=1
                duplicate=bbox in seen
                if duplicate:counts['duplicate_component_box']+=1
                else:seen[bbox]=name
                exact=rectangle and area_equal and perimeter_equal and material_equal and not duplicate
                if exact:counts['exact_rectangle_geometry']+=1
                result.update(bbox_gds_dbu=list(bbox),area_gds_dbu_squared=area,perimeter_gds_dbu=perimeter,rectangle=rectangle,native_area_equal=area_equal,native_perimeter_equal=perimeter_equal,spatial_material_equal=material_equal,duplicate_component_box=duplicate,exact_rectangle_geometry=exact)
            else:counts['missing_or_ambiguous_probe']+=1
            rows.write(json.dumps(result,separators=(',',':'))+'\n')
    check();summary=dict(native_type=native_type,counts=dict(counts),native_unit_um=unit_um,gds_dbu_um=dbu,integer_coordinate_scale=scale,limited_to_prefix=bool(limit),geometry_inventory_matches_all_nodes=counts['nodes']>0 and counts['exact_rectangle_geometry']==counts['nodes'],finite_R_basis_qualified=False,resistance_units_and_PVT_qualified=False,unlocated_arithmetic_attachment_qualified=False,release_qualified=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--gds',required=True,type=Path);p.add_argument('--nodes',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--native-type',required=True,choices=tuple(MATERIALS));p.add_argument('--limit',type=int,default=0);p.add_argument('--deadline-uptime',type=float)
    a=p.parse_args();print(json.dumps(run(a.gds,a.nodes,a.output,a.native_type,limit=a.limit,deadline=a.deadline_uptime)))
