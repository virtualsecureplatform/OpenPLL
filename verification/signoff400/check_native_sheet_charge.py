#!/usr/bin/env python3
"""Check observed signed C operators against spatial P1 sheet/reference fields.

A selected-operator control, not full-layout attachment, numerical-domain
qualification or permission to attach unlocated arithmetic fields.
"""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor,as_completed
from fractions import Fraction as F
import json
import math
from pathlib import Path
import resource
import sys
import time
from common import ROOT,save,sha
from resources import lease
from floating_sheet_basis import mesh,energy
from floating_sheet_charge import constant,sheet,area,line
from floating_sheet_fringe import fringe
EPS=sys.float_info.epsilon

def limits():resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
def scalar(op):
    kind=op[0];a=op[4]
    if kind=='A':return (a[2]-a[0])*(a[3]-a[1])*op[5],0.
    if kind=='L':return ((a[2]-a[0])+(a[3]-a[1]))*op[6],0.
    b=op[5];d=op[6];normal=0 if d in (1,4) else 1;along=1-normal;sign=-1 if d in (1,8) else 1;origin=a[normal]
    distances=sorted(max(0,sign*(b[i]-origin)) for i in (normal,normal+2));near,far=distances;lo,hi=math.atan(op[8]*near),math.atan(op[8]*far);factor=op[7]*(b[along+2]-b[along])*.6366
    return factor*(hi-lo),abs(factor)*8*EPS*(abs(lo)+abs(hi)+abs(hi-lo))

def build(context,refinement,scales,contours):
    if context.get('explicit_reference'):return constant('REF'),{'REF':None},'REF'
    name=context['original_conductor'];scale=scales[context['native_type']]
    if context['rectangle']:
        x0,y0,x1,y1=context['bbox_gds_dbu'];hull=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)];holes=[]
    else:
        record=contours[name]
        if context['global_field_id'] not in record['field_ids']:raise ValueError('nonrectangle field identity mismatch')
        hull=record['hull_gds_dbu'];holes=record['holes_gds_dbu']
    hull=[(F(x,scale),F(y,scale)) for x,y in hull];holes=[[(F(x,scale),F(y,scale)) for x,y in ring] for ring in holes];t=mesh(hull,holes,refinement)
    prefix=name+'::p1::';return sheet(t,prefix),{prefix+str(i):p for i,p in enumerate(t['points'])},name

def integrate(op,source,target,precision=80):
    if op[0]=='A':return area(source,target,op[4],op[5])
    if op[0]=='L':return line(source,target,op[4],op[5],op[6])
    if op[0]=='F':return fringe(source,target,op[4],op[5],op[6],op[7],op[8],precision)
    raise ValueError('unsupported C operator')
def numeric_energy(matrix,values):
    if all(isinstance(v,F) for v in matrix.values()):return float(energy(matrix,values)),0.
    terms=[float(v)*float(values[a])*float(values[b]) for (a,b),v in matrix.items()];return math.fsum(terms),512*EPS*math.fsum(abs(v) for v in terms)

def check_case(payload):
    row,scales,contours=payload;op=row['operator'];expected,scalar_bound=scalar(op);results=[];affine_energies=[]
    same=row['source'].get('original_conductor','REF')==row['target'].get('original_conductor','REF')
    for refinement in (1,2,4):
        source,sp,sn=build(row['source'],refinement,scales,contours);target,tp,tn=build(row['target'],refinement,scales,contours);positions=dict(sp);positions.update(tp);matrix=integrate(op,source,target)
        sums=defaultdict(list)
        for (a,b),v in matrix.items():
            if v!=matrix.get((b,a),0):raise ValueError('asymmetric integrated C matrix')
            sums[a].append(v)
        for terms in sums.values():
            if all(isinstance(v,F) for v in terms):
                if sum(terms,F(0)):raise ValueError('exact C row does not conserve charge')
            elif abs(math.fsum(map(float,terms)))>256*EPS*math.fsum(abs(float(v)) for v in terms):raise ValueError('C row exceeds floating summation conservation bound')
        active=sn if sn!='REF' else tn;prefix=active+'::p1::';constant_values={n:F(n.startswith(prefix)) for n in positions}
        actual,round_bound=numeric_energy(matrix,constant_values);wanted=0. if same else expected;tolerance=scalar_bound+round_bound+2e-12*abs(wanted)
        if abs(actual-wanted)>tolerance:raise ValueError(('native constant-collapse integral differs',row['operator_byte_offset'],actual,wanted,tolerance))
        active_points=[p for n,p in positions.items() if n.startswith(prefix)];x0=min(p[0] for p in active_points);y0=min(p[1] for p in active_points);width=max(p[0] for p in active_points)-x0;height=max(p[1] for p in active_points)-y0
        values={n:(F(0) if p is None or not n.startswith(prefix) else (p[0]-x0)/width+2*(p[1]-y0)/height) for n,p in positions.items()};e,bound=numeric_energy(matrix,values)
        affine_energies.append((e,bound));density=op[5] if op[0]=='A' else op[6] if op[0]=='L' else op[7]
        if (density>0 and e < -bound) or (density<0 and e > bound):raise ValueError('signed local squared-voltage energy changed sign')
        if op[0]=='F' and refinement==1:
            independent_precision=integrate(op,source,target,precision=120);norm=max([abs(v) for v in matrix.values()]+[0.]);delta=max([abs(float(matrix.get(k,0))-float(independent_precision.get(k,0))) for k in set(matrix)|set(independent_precision)]+[0.])
            if delta>2e-13*norm:raise ValueError('fringe precision control differs')
        results.append(dict(refinement=refinement,matrix_entries=len(matrix),constant_collapse=actual,native_scalar=wanted,scalar_roundoff_bound=scalar_bound,energy_roundoff_bound=round_bound,affine_energy=e,affine_roundoff_bound=bound))
    first,first_bound=affine_energies[0]
    for e,bound in affine_energies[1:]:
        if abs(e-first)>bound+first_bound+2e-12*max(abs(e),abs(first)):raise ValueError('affine energy changes under sheet refinement')
    return dict(operator_byte_offset=row['operator_byte_offset'],category=row['category'],source_field=row['source']['global_field_id'],target_field=row['target']['global_field_id'],same_sheet=same,refinements=results,full_layout_attachment_qualified=False)

def run(samples,geometry,contours,output):
    samples,geometry,contours,out=(Path(p).resolve() for p in (samples,geometry,contours,output));out.mkdir(parents=True,exist_ok=False);start=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=start+43200
    save(out/'owner.json',dict(wall_limit_s=43200,automatic_identical_retry=False,cpu_slots=8,per_worker_memory_limit_GiB=1))
    def status(state,**extra):save(out/'status.json',dict(state=state,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start,release_qualified=False,**extra))
    try:
        with lease(8,8,deadline):
            s=json.loads((samples/'assessment.json').read_text());g=json.loads((geometry/'assessment.json').read_text());c=json.loads((contours/'assessment.json').read_text())
            if len({s['shared_geometry_sha256'],g['shared_geometry_sha256'],c['shared_geometry_sha256']})!=1:raise ValueError('native C controls mix GDS geometries')
            cases=samples/'native/cases.jsonl';polygons=contours/'polygons.jsonl';pins={str(cases):s['artifacts'][str(cases)],str(polygons):c['artifacts'][str(polygons)]}
            for p in (Path(__file__).resolve(),*[Path(__file__).with_name(n) for n in ('floating_sheet_basis.py','floating_sheet_charge.py','floating_sheet_fringe.py','common.py','resources.py')],samples/'assessment.json',geometry/'assessment.json',contours/'assessment.json'):pins[str(p)]=sha(p)
            for p,h in pins.items():
                if sha(p)!=h:raise ValueError('native sheet control input changed')
            rows=[json.loads(line) for line in cases.read_text().splitlines()]
            if len(rows)!=s['selected_cases'] or not rows:raise ValueError('complete nonempty selected operator set required')
            contour_map={r['original_conductor']:r for r in map(json.loads,polygons.read_text().splitlines())};scales={t:r['integer_coordinate_scale'] for t,r in g['per_native_type'].items()};save(out/'input_manifest.json',dict(input_sha256=pins));status('integrating_signed_native_operator_controls',cases=len(rows));results=[]
            with ProcessPoolExecutor(max_workers=8,initializer=limits) as pool:
                futures=[pool.submit(check_case,(r,scales,contour_map)) for r in rows]
                for future in as_completed(futures):
                    if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('native sheet control deadline')
                    results.append(future.result());status('integrating_signed_native_operator_controls',cases=len(rows),completed=len(results))
            for p,h in pins.items():
                if sha(p)!=h:raise ValueError('native sheet control input changed during integration')
            save(out/'results.json',sorted(results,key=lambda r:r['operator_byte_offset']));result=dict(input_sha256=pins,artifacts={str(out/'results.json'):sha(out/'results.json')},cases=len(rows),refinements_per_case=3,operator_kinds=sorted({r['operator'][0] for r in rows}),sample_buckets=s['sample_buckets'],same_sheet_cases=sum(r['same_sheet'] for r in results),selected_signed_energy_and_charge_controls_passed=True,selected_operator_file_fully_rehashed=s['selected_operator_file_fully_rehashed'],full_native_inputs_rehashed=False,full_layout_capacitance_attachment_qualified=False,unlocated_arithmetic_attachment_qualified=False,global_passivity_qualified=False,finite_R_basis_qualified=False,physical_domain_complete=False,runtime_model_eligible=False,release_qualified=False,shared_geometry_sha256=s['shared_geometry_sha256'],elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
            save(out/'assessment.json',result);status('selected_native_sheet_charge_controls_complete_pending_full_attachment');return result
    except BaseException as e:status('failed',reason=repr(e));raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('samples','geometry','contours','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();r=run(a.samples,a.geometry,a.contours,a.output);print(json.dumps({k:r[k] for k in ('cases','operator_kinds','elapsed_s')}))
