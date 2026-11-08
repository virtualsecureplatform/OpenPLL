"""Link native ground subtraction to the already resolved overlap mask."""
import json,math
from audit_magic_coupling_geometry_trace import lines


def audit(trace):
    latest=None;pending=None;count=split=0;epochs=set()
    for line in lines(trace):
        r=json.loads(line)
        if pending is not None:
            if r['kind']!='ground_update' or any(r[k]!=pending[k] for k in ['cell','epoch','node_id']) or r['site']!='ExtCouple.c:522' or not r['has_before']:raise ValueError('matching adjacent ground subtraction required')
            before,after=[float.fromhex(r[k+'_hex']) for k in ['before','after']]
            coefficient=float.fromhex(pending['coefficient_hex'])
            if not all(map(math.isfinite,[before,after,coefficient])) or before-coefficient*pending['native_area']!=after:raise ValueError('native ground subtraction arithmetic mismatch')
            pending=None
        if r['kind']=='overlap_support_end':latest=r
        elif r['kind']=='ground_overlap_subtraction':
            if latest is None or any(r[k]!=latest[k] for k in ['cell','epoch','overlap_id','native_area']) or r['node_id']!=latest['node1_id']:raise ValueError('resolved overlap support identity mismatch')
            if r['pointwise_placement_qualified'] is not False or r['native_area']<=0:raise ValueError('positive diagnostic-only native overlap required')
            count+=1;split+=bool(latest['split']);epochs.add((r['cell'],r['epoch']));pending=r
    if pending is not None or not count or len(epochs)!=1:raise ValueError('one completed overlap subtraction epoch required')
    return dict(ground_overlap_subtractions=count,all_subtractions_linked_to_native_overlap_support=True,native_subtraction_arithmetic_verified=True,unsupported_split_supports=split,fringe_ground_subtractions_qualified=False,pointwise_placement_qualified=False,distributed_wire_R_qualified=False,release_ready=False)
