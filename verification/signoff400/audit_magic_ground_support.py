"""Check native ground additions against tile area/perimeter support and state updates."""
import json,math
from audit_magic_coupling_geometry_trace import lines
from audit_magic_overlap_support import area


def support(row):
    tile=row['tile'];area(tile)
    clip=row['clip']
    if clip is not None:area(clip)
    kind=row['measure_kind'];direction=row['direction'];split=row['split']
    if kind=='area':
        if direction!=-1 or row['neighbor'] is not None:raise ValueError('area support identity')
        box=tile if clip is None else [max(tile[0],clip[0]),max(tile[1],clip[1]),min(tile[2],clip[2]),min(tile[3],clip[3])]
        measure=max(0,box[2]-box[0])*max(0,box[3]-box[1])
        if split:measure//=2
    elif kind=='diagonal_length':
        if direction!=0 or not split:raise ValueError('split diagonal identity')
        measure=math.isqrt((tile[2]-tile[0])**2+(tile[3]-tile[1])**2)
        box=tile
    elif kind=='edge_length':
        n=row['neighbor'];area(n)
        if direction in [2,8]:
            y=tile[3] if direction==2 else tile[1]
            if (n[1] if direction==2 else n[3])!=y:raise ValueError('nonadjacent horizontal neighbor')
            box=[max(tile[0],n[0]),y,min(tile[2],n[2]),y]
        elif direction in [1,4]:
            x=tile[0] if direction==1 else tile[2]
            if (n[2] if direction==1 else n[0])!=x:raise ValueError('nonadjacent vertical neighbor')
            box=[x,max(tile[1],n[1]),x,min(tile[3],n[3])]
        else:raise ValueError('unknown edge direction')
        if clip is not None:box=[max(box[0],clip[0]),max(box[1],clip[1]),min(box[2],clip[2]),min(box[3],clip[3])]
        measure=0 if box[2]<box[0] or box[3]<box[1] else (box[2]-box[0])+(box[3]-box[1])
    else:raise ValueError('unknown native support measure')
    native=float.fromhex(row['native_measure_hex']);coefficient=float.fromhex(row['coefficient_hex'])
    if not math.isfinite(native) or not math.isfinite(coefficient) or native!=measure:raise ValueError('native ground support measure mismatch')
    return dict(measure=measure,coefficient=coefficient,box=box,rectilinear_support_verified=not split and not row['neighbor_split'])


def audit(trace):
    pending=None;count=unsupported=0;epochs=set();kinds={}
    for line in lines(trace):
        r=json.loads(line)
        if pending is not None:
            old,s=pending
            if r['kind']!='ground_update' or any(r[k]!=old[k] for k in ['cell','epoch','node_id','site']) or not r['has_before']:raise ValueError('ground support lacks adjacent matching update')
            before,after=[float.fromhex(r[k+'_hex']) for k in ['before','after']]
            if not math.isfinite(before) or not math.isfinite(after) or before+s['measure']*s['coefficient']!=after:raise ValueError('native ground arithmetic mismatch')
            pending=None
        if r['kind']=='ground_support':
            if r['pointwise_placement_qualified'] is not False:raise ValueError('observer cannot qualify placement')
            s=support(r);pending=(r,s);count+=1;unsupported+=not s['rectilinear_support_verified'];epochs.add((r['cell'],r['epoch']));kinds[r['measure_kind']]=kinds.get(r['measure_kind'],0)+1
    if pending is not None or not count or len(epochs)!=1:raise ValueError('one complete ground-support epoch required')
    return dict(ground_support_events=count,measure_kinds=kinds,native_support_measures_and_additions_verified=True,unsupported_split_supports=unsupported,all_support_rectilinear=not unsupported,ground_shielding_subtractions_spatially_qualified=False,pointwise_placement_qualified=False,distributed_wire_R_qualified=False,release_ready=False)
