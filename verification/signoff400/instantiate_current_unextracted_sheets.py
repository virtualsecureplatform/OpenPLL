#!/usr/bin/env python3
"""Prepare all current conductor bases with shared exact shape matrices."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction as F
import json
import os
from pathlib import Path
import time
from common import ROOT,save,sha
from compiled_charge import execute
from parallel_hash import sha_prefetch
from resources import identity,lease
from certify_sheet_shape_atlas import build_atlas

MATERIALS={'li':('locali','locali'),'p':('active','poly'),**{'m'+str(i):('metal'+str(i),'metal'+str(i)) for i in range(1,6)}}
CAD_PYTHON='/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3'


def run(a):
    inventory,geometry,contours,roles,out=[p.resolve() for p in (a.inventory,a.geometry,a.contours,a.roles,a.output)]
    out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=8,memory_limit_GiB=16,automatic_identical_retry=False))
    ir,gr,cr,rr=[p/'assessment.json' for p in (inventory,geometry,contours,roles)]
    i,g,c,r=[json.loads(p.read_text()) for p in (ir,gr,cr,rr)]
    if g['input_sha256'].get(str(ir))!=sha(ir) or c['input_sha256'].get(str(gr))!=sha(gr):
        raise ValueError('complete matching native/GDS/contour proofs required')
    if i['input_sha256'].get(str(rr))!=sha(rr) or not i['physical_and_arithmetic_field_ids_separated']:
        raise ValueError('matching proven field roles required')
    total=i['unique_native_conductors']
    if any(g['counts'].get(k,0)!=total for k in ('nodes','one_polygon','area_equal','perimeter_equal','spatial_material_equal')):
        raise ValueError('complete native-to-GDS correspondence required')
    if i['nodes_with_multiple_spatial_field_keys'] or i['nodes_without_exactly_one_nonzero_resistance_class']:
        raise ValueError('explicit single material class required')
    if c['captured_polygons']!=total-g['counts']['rectangle']:raise ValueError('all nonrectangles must be retained')
    domains=[Path(p) for p in i['input_sha256'] if p.endswith('/domain/assessment.json')]
    if len(domains)!=1:raise ValueError('one common domain required')
    dp=domains[0];d=json.loads(dp.read_text());techs=[Path(p) for p in d['input_sha256'] if p.endswith('/sky130A.tech')]
    if len(techs)!=1:raise ValueError('one pinned technology required')
    tech=techs[0];image=ROOT/'build/apptainer/openpll-release-modern.sif';reader=Path(__file__).with_name('read_nominal_sheet_rules.py')
    contour_path=contours/'polygons.jsonl';role_path=roles/'field_role_intervals.json'
    paths=[ir,gr,cr,rr,dp,image,contour_path,role_path,a.binary.resolve(),reader,Path(__file__).resolve(),
           ROOT/'tools/native_rc_coverage/instantiate_unextracted_sheets.cpp',ROOT/'tools/charge_compiler/json.hpp',
           *[Path(__file__).with_name(n) for n in ('nominal_sheet_resistance.py','certify_sheet_shape_atlas.py','floating_sheet_basis.py','parallel_hash.py','resources.py')]]
    jobs=[]
    for t in sorted(i['native_types']):
        if t not in MATERIALS:raise ValueError('unsupported native material')
        native=inventory/'native'/('nodes_'+t+'.jsonl');geom=geometry/t/'nodes.jsonl';paths.extend((native,geom))
        plane,material=MATERIALS[t];jobs.append(dict(native_type=t,native=str(native),geometry=str(geom),plane=plane,material=material,
                                                  coordinate_scale=g['per_native_type'][t]['integer_coordinate_scale']))
    with lease(8,16,deadline):
        save(out/'status.json',dict(state='verifying_complete_sheet_instance_geometry_inputs',release_qualified=False))
        with ThreadPoolExecutor(max_workers=4) as pool:hashes=list(pool.map(lambda p:sha_prefetch(p,readers=2,deadline=deadline),paths))
        pins=dict(zip(map(str,paths),hashes))
        for job in jobs:
            if pins[job['native']]!=i['artifacts'][job['native']] or pins[job['geometry']]!=g['artifacts'][job['geometry']]:
                raise ValueError('attributed geometry input changed')
        if pins[str(contour_path)]!=c['artifacts'][str(contour_path)] or pins[str(role_path)]!=r['artifacts'][str(role_path)]:
            raise ValueError('contour/field-role artifact changed')
        rules=out/'nominal_sheet_rules.json'
        execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,CAD_PYTHON,reader,'--tech',tech,'--output',rules],out/'nominal_rules.log',deadline,4)
        nominal=json.loads(rules.read_text())
        if nominal['unit']!='milliohms_per_square' or nominal['tech_sha256']!=d['input_sha256'][str(tech)]:
            raise ValueError('documented sheet rule/technology mismatch')
        for job in jobs:
            value=F(nominal['values'][job['material']])
            if value<=0 or value.denominator!=1:raise ValueError('positive exact integer nominal rule required')
            job['nominal_sheet_milliohm']=value.numerator
        role=json.loads(role_path.read_text());interval=role['arithmetic_bookkeeping_field_id_interval']
        cfg=out/'config.json';save(cfg,dict(jobs=jobs,contours=str(contour_path),output=str(out/'native'),deadline_uptime=deadline,
                                          arithmetic_field_begin=interval[0],arithmetic_field_end=interval[1]))
        save(out/'input_manifest.json',dict(input_sha256=pins))
        save(out/'status.json',dict(state='instantiating_all_spatial_sheets_in_parallel',release_qualified=False))
        execute([a.binary.resolve(),cfg],out/'native.log',deadline,8)
        result=json.loads((out/'native/summary.json').read_text())
        if result['basis_instances']!=total or result['nonrectangles']!=c['captured_polygons']:
            raise ValueError('full sheet instance coverage mismatch')
        save(out/'status.json',dict(state='certifying_all_unique_sheet_shapes_at_three_refinements',release_qualified=False))
        atlas=build_atlas(out/'native',out/'atlas',deadline)
        for p,h in pins.items():
            if sha_prefetch(Path(p),readers=4,deadline=deadline)!=h:raise ValueError('sheet input changed during instantiation')
        artifacts=[cfg,rules,out/'native/summary.json',out/'atlas/assessment.json',*[Path(p) for p in atlas['artifacts']]]
        for job in jobs:artifacts.extend((out/'native'/job['native_type']/'instances.jsonl',out/'native'/job['native_type']/'shape_requests.jsonl'))
        save(out/'assessment.json',dict(**result,input_sha256=pins,artifacts={str(p):sha_prefetch(p,deadline=deadline) for p in artifacts},
            source_inventory=str(inventory),source_geometry=str(geometry),source_contours=str(contours),source_roles=str(roles),
            unique_geometry_templates=atlas['unique_geometry_templates'],exact_geometry_certificates=atlas['exact_geometry_certificates'],
            spatial_basis_instance_specs_prepared=True,independent_instance_audit_complete=False,
            nominal_sheet_reference_temperature_known=False,resistance_PVT_qualified=False,charge_projection_complete=False))
        save(out/'status.json',dict(state='complete_sheet_instance_specs_pending_independent_audit_and_charge_projection',release_qualified=False))
        print(json.dumps(dict(instances=total,unique_shapes=atlas['unique_geometry_templates'],certificates=atlas['exact_geometry_certificates'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('inventory','geometry','contours','roles','binary','output'):p.add_argument('--'+name,required=True,type=Path)
    run(p.parse_args())
