"""Reconstruct resolved halo ground shielding from native per-rule geometry ledgers."""
import json,math
from audit_magic_coupling_geometry_trace import lines
from magic_fringe_kernel import measure


def audit(trace):
    active=completed=pending=None;callbacks=subtractions=rules=split=0;epochs=set()
    fields=['cell','epoch','node_id','other_node_id','boundary','box','direction','length','multiplier_hex','fraction_hex','coefficient_hex','split']
    def value(r,k):
        n=float.fromhex(r[k+'_hex'])
        if not math.isfinite(n):raise ValueError('nonfinite halo value')
        return n
    def matching(a,b):
        if any(a[k]!=b[k] for k in fields):raise ValueError('halo callback identity changed')
    for line in lines(trace):
        r=json.loads(line);kind=r['kind']
        if pending is not None:
            if kind!='ground_update' or any(r[k]!=pending[k] for k in ['cell','epoch','node_id']) or r['site']!='ExtCouple.c:1521' or not r['has_before']:raise ValueError('matching adjacent halo ground update required')
            if value(r,'before')-value(pending,'subcap')!=value(r,'after'):raise ValueError('native halo ground arithmetic mismatch')
            pending=None
        if kind=='ground_halo_begin':
            if active is not None:raise ValueError('nested halo callback')
            if r['pointwise_placement_qualified'] is not False or type(r['length']) is not int or r['length']<=0 or value(r,'shield')!=0:raise ValueError('diagnostic positive-length zero-shield callback required')
            geometric=measure(r['box'],r['boundary'],r['direction'],value(r,'multiplier'))
            if not math.isclose(geometric,value(r,'fraction')*r['length'],rel_tol=5e-13,abs_tol=1e-13):raise ValueError('native halo geometric fraction mismatch')
            active=dict(begin=r,shield=0.0);completed=None;epochs.add((r['cell'],r['epoch']))
        elif kind=='fringe_rule_end':
            if active is None:raise ValueError('fringe rule outside halo callback')
            b=active['begin']
            if (r['cell'],r['epoch'],r['node1_id'],r['node2_id'],r['reference_length'])!=(b['cell'],b['epoch'],b['node_id'],b['other_node_id'],b['length']):raise ValueError('halo rule identity mismatch')
            if b['node_id']!=b['other_node_id']:active['shield']+=value(r,'substrate_shield')
            rules+=1
        elif kind=='ground_halo_end':
            if active is None:raise ValueError('halo end without begin')
            matching(active['begin'],r)
            if value(r,'shield')!=active['shield']:raise ValueError('native halo shielding accumulator mismatch')
            callbacks+=1;split+=bool(r['split']);completed=r;active=None
        elif kind=='ground_halo_subtract':
            if active is not None or completed is None:raise ValueError('halo subtraction without completed callback')
            matching(completed,r)
            if value(r,'shield')!=value(completed,'shield'):raise ValueError('halo shielding changed before subtraction')
            expected=value(r,'coefficient')*((value(r,'fraction')-value(r,'shield'))*r['length'])
            if value(r,'subcap')!=expected:raise ValueError('native halo subtraction formula mismatch')
            subtractions+=1;pending=r;completed=None
    if active is not None or pending is not None or not callbacks or not subtractions or len(epochs)!=1:raise ValueError('one completed halo subtraction epoch required')
    return dict(halo_callbacks=callbacks,fringe_rules=rules,ground_halo_subtractions=subtractions,native_shielding_accumulators_and_subtractions_verified=True,unsupported_split_callbacks=split,diagnostic_relative_integral_tolerance=5e-13,diagnostic_absolute_integral_tolerance=1e-13,halo_tail_ground_qualified=False,legacy_fringe_ground_qualified=False,pointwise_placement_qualified=False,distributed_wire_R_qualified=False,release_ready=False)
