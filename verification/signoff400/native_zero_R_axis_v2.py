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
    if chain['state'] not in ('full_tile_chain_with_zero_R','uncovered_tile_ends') or axis not in (0,1) or not namespace or not segments:
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
    first,last=knots[0][0],knots[-1][0]
    if first<box[axis] or last>box[axis+2]:
        raise ValueError('native zero-R chain outside tile bounds')
    if chain['state']=='full_tile_chain_with_zero_R' and (first!=box[axis] or last!=box[axis+2]):
        raise ValueError('full-tile state must cover exact tile bounds')
    if chain['state']=='uncovered_tile_ends' and list(map(F,chain['uncovered_axis_ends_internal']))!=[first-box[axis],box[axis+2]-last]:
        raise ValueError('declared uncovered intervals differ')
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
    basis_knots=list(knots);stubs=[];latent=[];width=box[3-axis]-box[1-axis]
    for lower,start,end,anchor in ((True,box[axis],first,names[0]),(False,last,box[axis+2],names[-1])):
        if start==end:continue
        node=namespace+(':lo' if lower else ':hi')
        if node in names or node==reference:raise ValueError('latent/native voltage collision')
        interval=(start,end);square=(end-start)/width
        stubs.append(dict(new_latent_node=node,anchor=anchor,axis_interval_internal=interval,
                          resistance_squares_exact=square,requires_sheet_model_for_material=chain['raw_material']))
        latent.append(node)
        if lower:basis_knots.insert(0,(start,node))
        else:basis_knots.append((end,node))
    return dict(template=axis_template(box,axis,basis_knots),knots=basis_knots,native_nodes=names,
                latent_nodes=latent,symbolic_end_stub_resistors=stubs,
                native_edges=edges,conductance=dict(conductance),constraints=constraints,
                unit_area_mass=exact_axis_mass(box,axis,basis_knots,reference),
                conductance_units='inverse_native_milliohms',reference=reference,
                native_voltage_identities_preserved=True,epsilon_resistance_added=False,
                native_resistors_rewritten=False,physical_RC_qualified=False,
                resistance_PVT_qualified=False,release_qualified=False)


def dc_matrix(model,sheet_resistance=None):
    """Exact [G B; B^T 0] native DC equations before boundary conditions."""
    result=defaultdict(F,model['conductance'])
    stubs=model['symbolic_end_stub_resistors']
    if stubs:
        if sheet_resistance is None or F(sheet_resistance)<=0:
            raise ValueError('explicit positive sheet parameter required for finite ends')
        for e in stubs:
            a,b=e['new_latent_node'],e['anchor']
            g=1/(F(sheet_resistance)*e['resistance_squares_exact'])
            result[a,a]+=g;result[b,b]+=g;result[a,b]-=g;result[b,a]-=g
    for c in model['constraints']:
        current=c['current_unknown']
        for node,sign in ((c['positive'],F(1)),(c['negative'],F(-1))):
            result[node,current]+=sign;result[current,node]+=sign
    return {k:v for k,v in result.items() if v}
