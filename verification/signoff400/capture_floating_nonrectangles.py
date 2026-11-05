#!/usr/bin/env python3
"""Retain complete GDS hull/hole contours for nonrectangular floating domains."""
import argparse
import json
from pathlib import Path
import time
import pya
from common import ROOT,save,sha
from parallel_hash import sha_prefetch
from resources import lease
from check_floating_gds_geometry import MATERIALS

def capture_polygon(cell,index,row):
    x,y=row['point_gds_dbu'];point=pya.Point(x,y);it=cell.begin_shapes_rec_overlapping(index,pya.Box(x,y,x+1,y+1));polygons=[]
    while not it.at_end():
        shape=it.shape();poly=pya.Polygon(shape.box) if shape.is_box() else shape.polygon
        if poly.inside(point):polygons.append(poly)
        it.next()
    if len(polygons)!=1:raise ValueError('nonrectangle probe missing or ambiguous')
    poly=polygons[0];box=poly.bbox()
    if [box.left,box.bottom,box.right,box.top]!=row['bbox_gds_dbu'] or poly.area()!=row['area_gds_dbu_squared'] or poly.perimeter()!=row['perimeter_gds_dbu']:raise ValueError('nonrectangle geometry differs from full audit')
    if poly.area()==box.area() and poly.holes()==0:raise ValueError('rectangle in exception inventory')
    result=dict(row);result['hull_gds_dbu']=[[p.x,p.y] for p in poly.each_point_hull()];result['holes_gds_dbu']=[[[p.x,p.y] for p in poly.each_point_hole(i)] for i in range(poly.holes())]
    result['all_edges_manhattan']=all(a[0]==b[0] or a[1]==b[1] for contour in [result['hull_gds_dbu'],*result['holes_gds_dbu']] for a,b in zip(contour,contour[1:]+contour[:1]))
    return result

def run(audit,output):
    audit,out=(Path(p).resolve() for p in (audit,output));out.mkdir(parents=True,exist_ok=False);start=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=start+43200
    def status(state):save(out/'status.json',dict(state=state,release_qualified=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start))
    save(out/'owner.json',dict(wall_limit_s=43200,automatic_identical_retry=False,cpu_slots=2,memory_limit_GiB=8))
    try:
        status('validating_geometry_audit')
        with lease(2,8,deadline):
            proof=json.loads((audit/'assessment.json').read_text());gds=[(Path(p),h) for p,h in proof['input_sha256'].items() if p.endswith('.gds')]
            if len(gds)!=1:raise ValueError('one source GDS required')
            gds,gh=gds[0];pins={str(gds):gh,str(audit/'assessment.json'):sha(audit/'assessment.json')};pending={};expected=0
            for t,r in proof['per_native_type'].items():
                n=r['counts']['nodes']-r['counts'].get('rectangle',0)
                if n:
                    p=audit/t/'nodes.jsonl';pins[str(p)]=proof['artifacts'][str(p)];pending[t]=(p,n);expected+=n
            for p in (Path(__file__).resolve(),Path(__file__).with_name('check_floating_gds_geometry.py'),Path(__file__).with_name('common.py'),Path(__file__).with_name('parallel_hash.py'),Path(__file__).with_name('resources.py')):pins[str(p)]=sha(p)
            for p,h in pins.items():
                if sha_prefetch(p,deadline=deadline)!=h:raise ValueError('nonrectangle input changed: '+p)
            save(out/'input_manifest.json',dict(input_sha256=pins));status('capturing_all_nonrectangle_contours')
            layout=pya.Layout();layout.read(str(gds));top=layout.top_cell();lookup=pya.Layout();lookup.dbu=layout.dbu;cell=lookup.create_cell('NONRECTANGLE_LOOKUP');captured=0;manhattan=0
            with (out/'polygons.jsonl').open('x') as rows:
                for t,(path,n) in pending.items():
                    layer=MATERIALS[t][0];index=lookup.layer(layer,20);cell.shapes(index).insert(pya.Region(top.begin_shapes_rec(layout.find_layer(layer,20))).merged());count=0
                    with path.open() as f:
                        for line in f:
                            if '"rectangle":false' not in line:continue
                            row=json.loads(line)
                            if row.get('rectangle') is not False:continue
                            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('contour capture deadline')
                            result=capture_polygon(cell,index,row);result['native_type']=t;rows.write(json.dumps(result,separators=(',',':'))+'\n');count+=1;captured+=1;manhattan+=int(result['all_edges_manhattan'])
                    if count!=n:raise ValueError('nonrectangle partition count differs')
            if captured!=expected:raise ValueError('nonrectangle coverage differs')
            for p,h in pins.items():
                if sha_prefetch(p,deadline=deadline)!=h:raise ValueError('nonrectangle input changed during capture: '+p)
            result=dict(input_sha256=pins,artifacts={str(out/'polygons.jsonl'):sha(out/'polygons.jsonl')},captured_polygons=captured,expected_nonrectangles=expected,manhattan_polygons=manhattan,shared_geometry_sha256=gh,finite_R_basis_qualified=False,physical_domain_complete=False,runtime_model_eligible=False,release_qualified=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
            save(out/'assessment.json',result);status('nonrectangle_contours_complete_pending_finite_R_mesh');return result
    except BaseException:status('failed');raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--audit',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();r=run(a.audit,a.output);print(json.dumps({k:r[k] for k in ('captured_polygons','manhattan_polygons','elapsed_s')}))
