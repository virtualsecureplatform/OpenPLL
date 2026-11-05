"""Represent native zero-ohm branches by exact voltage/current constraints.

Native voltage identities and finite resistor values survive. No epsilon R,
ground assignment, sheet calibration or semiconductor interpretation is added.
"""
from collections import defaultdict
from fractions import Fraction as F
from native_axis_basis import axis_template, exact_axis_mass


def prepare(chain, namespace, reference='REF'):
    box=list(map(F,chain['tile_box_internal']))
    axis=chain['flow_axis'];segments=chain['segments'];group=chain['native_group_id']
    if chain['state']!='full_tile_chain_with_zero_R' or axis not in (0,1) or not namespace or not segments:
        raise ValueError('full native zero-R axis chain required')
    if len(box)!=4 or box[0]>=box[2] or box[1]>=box[3]:
        raise ValueError('positive unsplit tile required')
    knots=[];edges=[];branches=set()
    for i,s in enumerate(segments):
        if len(s)!=6:raise ValueError('complete native segment record required')
        lo,hi=map(F,s[:2]);a,b=s[2:4];resistance=F(s[4]);branch=s[5]
        if lo>=hi or resistance<0 or branch in branches:
            raise ValueError('increasing native segment, nonnegative R and distinct branch required')
        if any(not n.startswith('_rmesh_'+group+'_') for n in (a,b)):
            raise ValueError('cross-snapshot native voltage')
        if i and knots[-1]!=(lo,a):raise ValueError('discontinuous native axis chain')
        if not i:knots.append((lo,a))
        knots.append((hi,b));edges.append((a,b,resistance,branch));branches.add(branch)
    names=[n for _,n in knots]
    if knots[0][0]!=box[axis] or knots[-1][0]!=box[axis+2]:
        raise ValueError('native zero-R chain must cover exact tile bounds')
    if len(set(names))!=len(names) or reference in names:
        raise ValueError('distinct native axis voltage identities required')
    conductance=defaultdict(F);constraints=[]
    for i,(a,b,r,branch) in enumerate(edges):
        if r:
            g=1/r
            conductance[a,a]+=g;conductance[b,b]+=g
            conductance[a,b]-=g;conductance[b,a]-=g
        else:
            current=namespace+':current:'+str(i)
            if current in names or current==reference:raise ValueError('constraint/native collision')
            constraints.append(dict(current_unknown=current,positive=a,negative=b,
                                    native_branch=branch,voltage_rhs=F(0)))
    if not constraints:raise ValueError('at least one native zero-ohm branch required')
    return dict(template=axis_template(box,axis,knots),knots=knots,native_nodes=names,
                native_edges=edges,conductance=dict(conductance),constraints=constraints,
                unit_area_mass=exact_axis_mass(box,axis,knots,reference),
                conductance_units='inverse_native_milliohms',reference=reference,
                native_voltage_identities_preserved=True,epsilon_resistance_added=False,
                native_resistors_rewritten=False,physical_RC_qualified=False,
                resistance_PVT_qualified=False,release_qualified=False)


def dc_matrix(model):
    """Exact [G B; B^T 0] native DC equations before boundary conditions."""
    result=defaultdict(F,model['conductance'])
    for c in model['constraints']:
        current=c['current_unknown']
        for node,sign in ((c['positive'],F(1)),(c['negative'],F(-1))):
            result[node,current]+=sign;result[current,node]+=sign
    return {k:v for k,v in result.items() if v}
