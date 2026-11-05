#!/usr/bin/env python3
"""Independently verify all sheet instances and serialized element matrices."""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction as F
import hashlib
import json
import multiprocessing
from pathlib import Path
import time
from common import save,sha
from resources import lease


def q(pair):return F(int(pair[0]),int(pair[1]))
def decode(rows):
    result={}
    for a,b,n,d in rows:
        if (a,b) in result:raise ValueError('duplicate sparse matrix entry')
        result[a,b]=F(int(n),int(d))
    return {key:value for key,value in result.items() if value}


def audit_atlas(root,proof):
    requests=json.loads((root/'atlas/requests.json').read_text());aliases=json.loads((root/'atlas/template_aliases.json').read_text())
    alias={r['local_template_id']:r['global_template_id'] for r in aliases}
    if len(alias)!=len(aliases):raise ValueError('duplicate template alias')
    sizes={};seen=set()
    with (root/'atlas/templates.jsonl').open() as stream:
        for line in stream:
            t=json.loads(line);key=t['global_template_id'],t['refinement']
            if key in seen:raise ValueError('duplicate atlas variant')
            seen.add(key);request=requests[key[0]];points=[(q(x),q(y)) for x,y in t['points_native_internal']]
            if len(set(points))!=len(points):raise ValueError('duplicate mesh points')
            stiffness=defaultdict(F);mass=defaultdict(F);area=F(0);boundary=defaultdict(int)
            for tri in t['triangles']:
                if len(set(tri))!=3 or any(i<0 or i>=len(points) for i in tri):raise ValueError('invalid triangle indices')
                p=[points[i] for i in tri];det=(p[1][0]-p[0][0])*(p[2][1]-p[0][1])-(p[2][0]-p[0][0])*(p[1][1]-p[0][1])
                if det<=0:raise ValueError('nonpositive triangle')
                area+=det/2
                # Reconstruct element gradients from the serialized vertices.
                gradients=[((p[(i+1)%3][1]-p[(i+2)%3][1])/det,(p[(i+2)%3][0]-p[(i+1)%3][0])/det) for i in range(3)]
                for i,a in enumerate(tri):
                    for j,b in enumerate(tri):
                        stiffness[a,b]+=det/2*sum(x*y for x,y in zip(gradients[i],gradients[j]))
                        mass[a,b]+=det/(12 if i==j else 24)
                for a,b in zip(tri,tri[1:]+tri[:1]):boundary[tuple(sorted((a,b)))]+=1
            k={key:value for key,value in stiffness.items() if value};m={key:value for key,value in mass.items() if value}
            if k!=decode(t['unit_sheet_stiffness']) or m!=decode(t['unit_area_mass']):raise ValueError('serialized matrix differs from exact element assembly')
            scale=F(request['coordinate_scale']);perimeter=F(0)
            for (a,b),count in boundary.items():
                if count not in (1,2):raise ValueError('nonconforming mesh edge')
                if count==1:perimeter+=abs(points[a][0]-points[b][0])+abs(points[a][1]-points[b][1])
            if area!=F(request['area_gds_dbu_squared'])/scale**2 or perimeter!=F(request['perimeter_gds_dbu'])/scale:
                raise ValueError('atlas area/perimeter differs from source polygon')
            if q(t['area_native_internal_squared'])!=area or q(t['perimeter_native_internal'])!=perimeter:raise ValueError('atlas measure metadata differs')
            for a in range(len(points)):
                if sum(k.get((a,b),F(0)) for b in range(len(points))):raise ValueError('floating constant mode lost')
            if sum(m.values())!=area:raise ValueError('constant mass differs from area')
            sizes[key]=len(points)
    expected={(i,r) for i in range(len(requests)) for r in (1,2,4)}
    if seen!=expected or len(seen)!=proof['exact_geometry_certificates']:raise ValueError('incomplete shape/refinement coverage')
    return requests,alias,sizes


def audit_material(job):
    root,inventory,geometry,native_type,scale,sheet,begin,end,exceptions,requests,aliases,sizes,deadline=job
    root,inventory,geometry=map(Path,(root,inventory,geometry));paths=[inventory/'native'/('nodes_'+native_type+'.jsonl'),geometry/native_type/'nodes.jsonl',root/'native'/native_type/'instances.jsonl']
    hashes=[hashlib.sha256() for _ in paths];ids=[];shapes={};shape_rows=[];counts={r:0 for r in (1,2,4)};arithmetic=0
    with paths[0].open('rb') as ns,paths[1].open('rb') as gs,paths[2].open('rb') as ins:
        streams=(ns,gs,ins);row=0
        while True:
            offsets=[f.tell() for f in streams];raw=[f.readline() for f in streams]
            if not any(raw):break
            if not all(raw):raise ValueError('instance source row count differs')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('instance audit deadline')
            for h,data in zip(hashes,raw):h.update(data)
            n,g,actual=map(json.loads,raw);row+=1;physical=n['physical_field_ids'];book=n['arithmetic_bookkeeping_field_ids']
            if len(physical)!=1 or not 0<physical[0]<begin or any(not begin<=x<end for x in book):raise ValueError('field role mismatch')
            if sorted(physical+book)!=sorted(n['field_ids']) or len(set(n['field_ids']))!=len(n['field_ids']):raise ValueError('native field IDs lost or duplicated')
            if n['field_ids']!=g['field_ids'] or n['original_conductor']!=g['original_conductor']:raise ValueError('native/GDS identity differs')
            if len(n['native_classes'])!=1 or n['native_classes'][0]['native_sheet_class_value']!=sheet:raise ValueError('nominal material rule differs')
            cls=n['native_classes'][0]
            if g['point_gds_dbu']!=[x*scale for x in n['point_internal']] or g['area_gds_dbu_squared']!=cls['area_internal_squared']*scale**2 or g['perimeter_gds_dbu']!=cls['perimeter_internal']*scale:
                raise ValueError('native/GDS geometry measures differ')
            x,y,x1,y1=g['bbox_gds_dbu'];w,h=x1-x,y1-y
            if g['rectangle']:hull=[[0,0],[w,0],[w,h],[0,h]];holes=[]
            else:
                e=exceptions[n['original_conductor']];hull=[[a-x,b-y] for a,b in e['hull_gds_dbu']];holes=[[[a-x,b-y] for a,b in ring] for ring in e['holes_gds_dbu']]
            signature=json.dumps([scale,hull,holes],separators=(',',':'))
            if signature not in shapes:
                shapes[signature]=len(shapes);shape_rows.append(dict(local_template_id=native_type+':'+str(len(shapes)-1),coordinate_scale=scale,hull_gds_dbu=hull,holes_gds_dbu=holes,area_gds_dbu_squared=g['area_gds_dbu_squared'],perimeter_gds_dbu=g['perimeter_gds_dbu']))
            local=native_type+':'+str(shapes[signature]);global_id=aliases[local];request=requests[global_id]
            if [request[k] for k in ('coordinate_scale','hull_gds_dbu','holes_gds_dbu')]!=[scale,hull,holes]:raise ValueError('shared atlas alias changes shape')
            expected=dict(physical_field_id=physical[0],original_conductor=n['original_conductor'],local_template_id=local,origin_gds_dbu=[x,y],coordinate_scale=scale,
                native_type=native_type,nominal_sheet_milliohm=sheet,voltage_namespace='_fmesh_'+str(physical[0]),arithmetic_bookkeeping_field_ids=book,
                source_geometry_byte_offset=offsets[1],source_native_byte_offset=offsets[0],source_row=row,supported_refinements=[1,2,4],physical_RC_qualified=False)
            if actual!=expected:raise ValueError('basis instance differs from native/GDS/field-role sources')
            ids.append(physical[0]);arithmetic+=len(book)
            for refinement in counts:counts[refinement]+=sizes[global_id,refinement]
    shape_path=root/'native'/native_type/'shape_requests.jsonl'
    actual=[json.loads(s) for s in shape_path.open()]
    if actual!=shape_rows:raise ValueError('shape request cache differs from full instance population')
    return dict(native_type=native_type,instances=len(ids),physical_ids=ids,logical_basis_nodes_by_refinement=counts,arithmetic_ids_preserved_without_states=arithmetic,
        input_hashes={str(p):h.hexdigest() for p,h in zip(paths,hashes)},shape_request_sha256=sha(shape_path))


def run(a):
    root,out=a.instances.resolve(),a.output.resolve();out.mkdir(parents=True,exist_ok=False);receipt=root/'assessment.json';proof=json.loads(receipt.read_text())
    inventory,geometry,contours,roles=[Path(proof[k]) for k in ('source_inventory','source_geometry','source_contours','source_roles')]
    g=json.loads((geometry/'assessment.json').read_text());nominal=json.loads((root/'nominal_sheet_rules.json').read_text())
    role=json.loads((roles/'field_role_intervals.json').read_text());begin,end=role['arithmetic_bookkeeping_field_id_interval'];deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    exceptions={r['original_conductor']:r for r in map(json.loads,(contours/'polygons.jsonl').read_text().splitlines())}
    material={'li':'locali','p':'poly',**{'m'+str(i):'metal'+str(i) for i in range(1,6)}}
    with lease(8,16,deadline):
        requests,aliases,sizes=audit_atlas(root,proof);jobs=[]
        for t in sorted(proof['per_native_type']):jobs.append((str(root),str(inventory),str(geometry),t,g['per_native_type'][t]['integer_coordinate_scale'],int(nominal['values'][material[t]]),begin,end,exceptions,requests,aliases,sizes,deadline))
        with ProcessPoolExecutor(max_workers=7,mp_context=multiprocessing.get_context('spawn')) as pool:results=list(pool.map(audit_material,jobs))
        ids=[];pins={str(receipt):sha(receipt)};states={r:0 for r in (1,2,4)};arithmetic=0
        for result in results:
            ids.extend(result.pop('physical_ids'));arithmetic+=result['arithmetic_ids_preserved_without_states']
            for refinement,n in result['logical_basis_nodes_by_refinement'].items():states[refinement]+=n
            for p,h in result['input_hashes'].items():
                if h!=proof['input_sha256'].get(p,proof['artifacts'].get(p)):raise ValueError('complete instance/source hashes differ')
                pins[p]=h
            shape_path=root/'native'/result['native_type']/'shape_requests.jsonl'
            if result['shape_request_sha256']!=proof['artifacts'][str(shape_path)]:raise ValueError('shape request hash differs')
            pins[str(shape_path)]=result['shape_request_sha256']
        if len(ids)!=proof['basis_instances'] or len(set(ids))!=len(ids):raise ValueError('missing or duplicated physical basis identity')
        for p in (root/'atlas/requests.json',root/'atlas/template_aliases.json',root/'atlas/templates.jsonl',root/'nominal_sheet_rules.json'):
            h=sha(p)
            if h!=proof['artifacts'][str(p)]:raise ValueError('atlas artifact changed')
            pins[str(p)]=h
        pins[str(Path(__file__).resolve())]=sha(Path(__file__))
        save(out/'assessment.json',dict(input_sha256=pins,all_instances_independently_checked=True,exact_saved_element_matrices_reconstructed=True,
            basis_instances=len(ids),unique_geometry_templates=len(requests),atlas_variants=len(sizes),logical_floating_basis_nodes_by_refinement=states,
            arithmetic_ids_preserved_without_states=arithmetic,physical_field_namespaces_unique=True,
            charge_projection_complete=False,resistance_PVT_qualified=False,physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
        print(json.dumps(dict(instances=len(ids),unique_shapes=len(requests),exact_atlas_variants=len(sizes),logical_basis_nodes_by_refinement=states)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('instances','output'):p.add_argument('--'+name,required=True,type=Path)
    run(p.parse_args())
