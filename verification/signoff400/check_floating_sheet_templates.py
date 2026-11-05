#!/usr/bin/env python3
"""Exact-rational finite-R sheet controls on all retained exceptional contours."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import resource
import time
from common import ROOT,save,sha
from resources import lease
from floating_sheet_basis import mesh,certify

def limits():resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
def check_case(row):
    results=[]
    for refinement in (1,2,4):
        t=mesh(row['hull_gds_dbu'],row.get('holes_gds_dbu',[]),refinement)
        if t['area']!=row['area_gds_dbu_squared'] or t['perimeter']!=row['perimeter_gds_dbu']:raise ValueError('sheet mesh differs from attributed GDS polygon')
        r=certify(t);r['refinement']=refinement;results.append(r)
    return dict(original_conductor=row['original_conductor'],native_type=row['native_type'],refinements=results)
def run(geometry,contours,output):
    geometry,contours,out=(Path(p).resolve() for p in (geometry,contours,output));out.mkdir(parents=True,exist_ok=False);start=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=start+43200
    save(out/'owner.json',dict(wall_limit_s=43200,automatic_identical_retry=False,cpu_slots=8,per_worker_memory_limit_GiB=1))
    def status(state,**extra):save(out/'status.json',dict(state=state,release_qualified=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start,**extra))
    try:
        with lease(8,8,deadline):
            g=json.loads((geometry/'assessment.json').read_text());c=json.loads((contours/'assessment.json').read_text())
            if g['shared_geometry_sha256']!=c['shared_geometry_sha256']:raise ValueError('sheet controls mix physical geometries')
            path=contours/'polygons.jsonl';pins={str(path):c['artifacts'][str(path)]}
            for p in (Path(__file__).resolve(),Path(__file__).with_name('floating_sheet_basis.py'),Path(__file__).with_name('common.py'),Path(__file__).with_name('resources.py'),geometry/'assessment.json',contours/'assessment.json'):pins[str(p)]=sha(p)
            for p,h in pins.items():
                if sha(p)!=h:raise ValueError('sheet control input changed')
            rows=[json.loads(line) for line in path.read_text().splitlines()]
            if len(rows)!=c['captured_polygons'] or c['manhattan_polygons']!=len(rows):raise ValueError('complete Manhattan contour inventory required')
            for t,part in g['per_native_type'].items():
                p=geometry/t/'nodes.jsonl';pins[str(p)]=g['artifacts'][str(p)]
                if sha(p)!=pins[str(p)]:raise ValueError('rectangle sample source changed')
                with p.open() as f:
                    for line in f:
                        r=json.loads(line)
                        if r['exact_rectangle_geometry']:
                            x0,y0,x1,y1=r['bbox_gds_dbu'];r.update(native_type=t,hull_gds_dbu=[[x0,y0],[x1,y0],[x1,y1],[x0,y1]],holes_gds_dbu=[]);rows.append(r);break
                    else:raise ValueError('no real rectangle sample for native material')
            save(out/'input_manifest.json',dict(input_sha256=pins));save(out/'cases.json',rows);status('checking_exact_sheet_energy_in_parallel',cases=len(rows));results=[]
            with ProcessPoolExecutor(max_workers=8,initializer=limits) as pool:
                futures=[pool.submit(check_case,r) for r in rows]
                for future in as_completed(futures):
                    if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('sheet control deadline')
                    results.append(future.result());status('checking_exact_sheet_energy_in_parallel',cases=len(rows),completed=len(results))
            for p,h in pins.items():
                if sha(p)!=h:raise ValueError('sheet control input changed during execution')
            save(out/'results.json',sorted(results,key=lambda r:r['original_conductor']))
            result=dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (out/'cases.json',out/'results.json')},cases=len(rows),refinements_per_case=3,all_nonrectangles_covered=c['captured_polygons'],real_rectangle_material_samples=len(g['per_native_type']),exact_sheet_energy_controls_passed=True,mesh_capacitance_attachment_qualified=False,resistance_units_and_PVT_qualified=False,finite_R_basis_qualified=False,physical_domain_complete=False,runtime_model_eligible=False,release_qualified=False,shared_geometry_sha256=g['shared_geometry_sha256'],elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
            save(out/'assessment.json',result);status('exact_sheet_controls_complete_pending_physical_attachment');return result
    except BaseException as error:status('failed',reason=repr(error));raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('geometry','contours','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();r=run(a.geometry,a.contours,a.output);print(json.dumps({k:r[k] for k in ('cases','refinements_per_case','elapsed_s')}))
