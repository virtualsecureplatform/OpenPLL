"""Independently audit junction support using compiled polygon Boolean geometry."""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import time
from common import ROOT,save,sha
from compiled_charge import execute
from resources import lease


def normalized(lines):
    result=[]
    for key,intervals in sorted(lines.items()):
        begin=end=None
        for lo,hi in sorted(intervals):
            if lo>=hi:
                raise ValueError('positive boundary interval required')
            if begin is None:
                begin,end=lo,hi
            elif lo<end:
                raise ValueError('duplicate or overlapping boundary coverage')
            elif lo==end:
                end=hi
            else:
                result.append([*key,begin,end])
                begin,end=lo,hi
        if begin is not None:
            result.append([*key,begin,end])
    return result


def region_edges(region):
    result=defaultdict(list)
    for polygon in region.each_merged():
        for edge in polygon.each_edge():
            a,b=edge.p1,edge.p2
            if a.x==b.x:
                key=(0,a.x,-1 if b.y>a.y else 1)
                lo,hi=sorted((a.y,b.y))
            elif a.y==b.y:
                key=(1,a.y,1 if b.x>a.x else -1)
                lo,hi=sorted((a.x,b.x))
            else:
                raise ValueError('Manhattan junction polygon boundary required')
            result[key].append((lo,hi))
    return normalized(result)


def inside(config):
    import pya
    cfg=json.loads(config.read_text())
    support,out=Path(cfg['support']),Path(cfg['output'])
    proof=support/'assessment.json'
    source=json.loads(proof.read_text())
    catalog=next(Path(p) for p in source['input_sha256'] if p.endswith('/native/tile_catalog.jsonl'))
    tiles=support/'junction_support_tiles.jsonl'
    boundaries=support/'junction_support_boundary.jsonl'
    paths=[proof,catalog,tiles,boundaries,Path(__file__).resolve()]
    pins={str(p):sha(p) for p in paths}
    if not source['native_node_junction_area_and_perimeter_exactly_supported_by_final_R_tiles']:
        raise ValueError('complete source support required')
    if pins[str(catalog)]!=source['input_sha256'][str(catalog)]:
        raise ValueError('native support catalog changed')
    for p in (tiles,boundaries):
        if pins[str(p)]!=source['artifacts'][str(p)]:
            raise ValueError('complete native support artifact changed')
    # Establish polygon edge orientation from a box and from a hole.
    test=pya.Region(pya.Box(0,0,3,2))
    assert region_edges(test)==[[0,0,-1,0,2],[0,3,1,0,2],[1,0,-1,0,3],[1,2,1,0,3]]
    hole=pya.Region(pya.Box(0,0,3,3))-pya.Region(pya.Box(1,1,2,2))
    assert len(region_edges(hole))==8 and int(hole.perimeter())==16
    regions,owners,counts={}, {},defaultdict(int)
    with catalog.open('rb') as raw,tiles.open() as stream:
        for line in stream:
            row=json.loads(line)
            key=(row['original_conductor'],row['raw_material'])
            serial=row['tile_serial']
            owner=(key,serial)
            if owner in owners:
                raise ValueError('duplicate junction support tile')
            owners[owner]=row['box_internal']
            raw.seek(row['source_catalog_byte_offset'])
            original=json.loads(raw.readline())
            for field in ('native_group_id','original_conductor','raw_material','raw_type_id',
                          'tile_serial','box_internal','private_voltage_nodes'):
                if original[field]!=row[field]:
                    raise ValueError('independent source catalog/tile identity mismatch')
            regions.setdefault(key,pya.Region()).insert(pya.Box(*row['box_internal']))
            counts[key]+=1
    owned=defaultdict(lambda:defaultdict(list))
    nboundary=0
    with boundaries.open() as stream:
        for line in stream:
            conductor,material,serial,axis,coord,lo,hi,normal=json.loads(line)
            key=(conductor,material)
            box=owners[key,serial]
            if axis not in (0,1) or normal not in (-1,1) or coord!=box[axis+(2 if normal==1 else 0)]:
                raise ValueError('boundary outward normal or owner side differs')
            if not box[1-axis]<=lo<hi<=box[3-axis]:
                raise ValueError('boundary exceeds its owner tile')
            owned[key][axis,coord,normal].append((lo,hi))
            nboundary+=1
    results=[]
    for target in source['results']:
        key=(target['original_conductor'],target['raw_material'])
        region=regions[key]
        region.merge()
        if int(region.area())!=target['exact_area_internal_squared'] or int(region.perimeter())!=target['exact_perimeter_internal']:
            raise ValueError('independent polygon area/perimeter differs')
        expected,actual=region_edges(region),normalized(owned[key])
        if expected!=actual or counts[key]!=target['support_tiles']:
            raise ValueError('complete owned boundary coverage differs from polygon union')
        results.append(dict(original_conductor=key[0],raw_material=key[1],support_tiles=counts[key],
             polygon_area_internal_squared=int(region.area()),polygon_perimeter_internal=int(region.perimeter()),
             normalized_directed_boundary_intervals=len(expected)))
    if any(sha(Path(p))!=h for p,h in pins.items()):
        raise ValueError('independent junction geometry source changed')
    save(out/'native_assessment.json',dict(input_sha256=pins,results=results,
         independent_polygon_union_area_perimeter_and_every_owned_boundary_checked=True,
         owned_boundary_segments=nboundary,physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))


def run(support,output):
    support,out=support.resolve(),output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    paths=[support/'assessment.json',image,Path(__file__).resolve()]
    pins={str(p):sha(p) for p in paths}
    cfg=out/'config.json'
    save(cfg,dict(support=str(support),output=str(out)))
    with lease(2,8,deadline):
        python='/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3'
        execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,python,
                 Path(__file__).resolve(),'--inside',cfg],out/'native.log',deadline,8)
        if any(sha(Path(p))!=h for p,h in pins.items()):
            raise ValueError('junction audit source changed')
        report=out/'native_assessment.json'
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(report):sha(report)},
             independent_junction_support_polygon_audit_pass=True,
             results=json.loads(report.read_text())['results'],
             physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
        print(json.dumps(dict(independent_junction_support_polygon_audit_pass=True)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inside',type=Path)
    parser.add_argument('--support',type=Path)
    parser.add_argument('--output',type=Path)
    a=parser.parse_args()
    if a.inside:
        inside(a.inside)
    else:
        run(a.support,a.output)
