"""Reconstruct native halo truncation geometry, float multiplier and ground subtraction."""
import json,math,struct
from audit_magic_coupling_geometry_trace import lines
from audit_magic_overlap_support import area


def tail(row):
    edge,clip=row['boundary'],row['clip'];area(edge);area(clip)
    direction=row['direction']
    if direction in [1,4]:
        if edge[0]!=edge[2]:raise ValueError('vertical tail boundary required')
        length=edge[3]-edge[1];distance=edge[0]-clip[0] if direction==1 else clip[2]-edge[2]
    elif direction in [2,8]:
        if edge[1]!=edge[3]:raise ValueError('horizontal tail boundary required')
        length=edge[2]-edge[0];distance=clip[3]-edge[3] if direction==2 else edge[1]-clip[1]
    else:raise ValueError('unknown native tail direction')
    distance=max(0,distance)
    if length<=0 or (row['length'],row['distance'])!=(length,distance):raise ValueError('native tail geometry mismatch')
    multiplier=float.fromhex(row['native_float_multiplier_hex']);fraction=float.fromhex(row['fraction_hex']);coefficient=float.fromhex(row['coefficient_hex']);subcap=float.fromhex(row['subcap_hex'])
    if not all(map(math.isfinite,[multiplier,fraction,coefficient,subcap])):raise ValueError('finite native tail values required')
    if struct.unpack('f',struct.pack('f',multiplier))[0]!=multiplier:raise ValueError('native float multiplier required')
    if not math.isclose(.6366*math.atan(multiplier*distance),fraction,rel_tol=5e-13,abs_tol=1e-13):raise ValueError('native tail fraction mismatch')
    if (coefficient*(1.0-fraction))*length!=subcap:raise ValueError('native tail formula mismatch')
    return subcap


def audit(trace):
    pending=None;events=split=0;epochs=set()
    for line in lines(trace):
        r=json.loads(line)
        if pending is not None:
            old,subcap=pending
            if r['kind']!='ground_update' or any(r[k]!=old[k] for k in ['cell','epoch','node_id']) or r['site']!='ExtCouple.c:1254' or not r['has_before']:raise ValueError('matching adjacent tail ground update required')
            before,after=[float.fromhex(r[k+'_hex']) for k in ['before','after']]
            if not all(map(math.isfinite,[before,after])) or before-subcap!=after:raise ValueError('native tail ground arithmetic mismatch')
            pending=None
        if r['kind']=='ground_halo_tail':
            if r['pointwise_placement_qualified'] is not False:raise ValueError('diagnostic cannot qualify placement')
            pending=(r,tail(r));events+=1;split+=bool(r['split']);epochs.add((r['cell'],r['epoch']))
    if pending is not None or not events or len(epochs)!=1:raise ValueError('one completed native tail epoch required')
    return dict(halo_tail_events=events,native_geometry_fraction_and_subtraction_verified=True,unsupported_split_boundaries=split,diagnostic_relative_integral_tolerance=5e-13,diagnostic_absolute_integral_tolerance=1e-13,legacy_fringe_ground_qualified=False,pointwise_placement_qualified=False,distributed_wire_R_qualified=False,release_ready=False)
