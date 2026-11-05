"""Cache exact P1 mesh certificates/matrices by translation-free geometry."""
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction as F
import json
import multiprocessing
from pathlib import Path
import resource
import time
from common import save,sha
from floating_sheet_basis import mesh,certify


def limits():resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
def ratio(q):return [str(q.numerator),str(q.denominator)]
def matrix_rows(matrix):return [[a,b,*ratio(v)] for (a,b),v in sorted(matrix.items()) if v]


def check_shape(request):
    scale=F(request['coordinate_scale'])
    hull=[(F(x)/scale,F(y)/scale) for x,y in request['hull_gds_dbu']]
    holes=[[(F(x)/scale,F(y)/scale) for x,y in ring] for ring in request['holes_gds_dbu']]
    results=[]
    for refinement in (1,2,4):
        t=mesh(hull,holes,refinement)
        if t['area']!=F(request['area_gds_dbu_squared'])/scale**2 or t['perimeter']!=F(request['perimeter_gds_dbu'])/scale:
            raise ValueError('atlas mesh area/boundary differs from attributed GDS')
        proof=certify(t)
        results.append(dict(global_template_id=request['global_template_id'],refinement=refinement,
            points_native_internal=[[ratio(x),ratio(y)] for x,y in t['points']],triangles=t['triangles'],
            unit_sheet_stiffness=matrix_rows(t['stiffness']),unit_area_mass=matrix_rows(t['mass']),
            area_native_internal_squared=ratio(t['area']),perimeter_native_internal=ratio(t['perimeter']),
            certificate=proof))
    return results


def build_atlas(instances,output,deadline):
    instances,output=Path(instances),Path(output);output.mkdir(parents=True,exist_ok=False)
    summary=json.loads((instances/'summary.json').read_text());unique={};requests=[];aliases=[];multiplicity={}
    for native_type in sorted(summary['per_native_type']):
        path=instances/native_type/'shape_requests.jsonl'
        with path.open() as stream:
            for line in stream:
                row=json.loads(line);key=json.dumps([row['coordinate_scale'],row['hull_gds_dbu'],row['holes_gds_dbu']],separators=(',',':'))
                if key not in unique:
                    index=len(requests);unique[key]=index;request=dict(row);request['global_template_id']=index;requests.append(request)
                index=unique[key];r=requests[index]
                if (r['area_gds_dbu_squared'],r['perimeter_gds_dbu'])!=(row['area_gds_dbu_squared'],row['perimeter_gds_dbu']):
                    raise ValueError('same shape has inconsistent geometry measures')
                aliases.append(dict(local_template_id=row['local_template_id'],global_template_id=index))
                multiplicity[row['local_template_id']]=index
    if not requests or len(aliases)!=summary['local_shape_templates'] or len(multiplicity)!=len(aliases):
        raise ValueError('incomplete or duplicate atlas request IDs')
    save(output/'requests.json',requests);save(output/'template_aliases.json',aliases)
    certificates=0
    with (output/'templates.jsonl').open('x') as stream,ProcessPoolExecutor(max_workers=8,initializer=limits,mp_context=multiprocessing.get_context('spawn')) as pool:
        for rows in pool.map(check_shape,requests,chunksize=1):
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('sheet atlas deadline')
            for row in rows:stream.write(json.dumps(row,separators=(',',':'))+'\n');certificates+=1
    result=dict(unique_geometry_templates=len(requests),local_template_aliases=len(aliases),refinements=[1,2,4],
        exact_geometry_certificates=certificates,constant_voltage_nullspace_preserved=True,
        coordinates='native_internal_units; instance origins are GDS DBU divided by coordinate_scale',
        stiffness_units='unit sheet; nominal siemens = stiffness * 1000 / nominal_sheet_milliohm',
        mass_units='native internal area; no physical C density attached',
        artifacts={str(p):sha(p) for p in (output/'requests.json',output/'template_aliases.json',output/'templates.jsonl')},
        charge_projection_complete=False,physical_RC_qualified=False,release_qualified=False)
    save(output/'assessment.json',result)
    return result
