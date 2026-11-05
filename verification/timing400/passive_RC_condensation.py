"""DC-exact path elimination with an energy-preserving capacitance projection.

No device/interface vertex may be removed. Only degree-one/two R vertices are
eligible. T reconstructs their DC harmonic voltage; G'=T.T G T is the exact
resistor Schur complement and C'=T.T C T keeps the full field energy, including
its variance. Dynamic error requires a separate bound and validation.
"""
from decimal import Decimal
import numpy as np
from scipy.sparse import coo_matrix


def conductance(size,branches):
    rr,cc,vv=[],[],[]
    for a,b,resistance in branches:
        g=1./float(resistance)
        assert a!=b and np.isfinite(g) and g>0
        rr.extend([a,b,a,b]);cc.extend([a,b,b,a]);vv.extend([g,g,-g,-g])
    return coo_matrix((vv,(rr,cc)),shape=(size,size)).tocsr()


def harmonic_paths(size,branches,eliminated,protected):
    removed=set(map(int,eliminated));protected=set(map(int,protected))
    if removed & protected:raise ValueError('Device/interface vertex cannot be eliminated')
    if not removed<=set(range(size)):raise ValueError('Unknown vertex')
    adjacency=[[] for _ in range(size)]
    for serial,(a,b,r) in enumerate(branches):
        value=Decimal(str(r))
        assert a!=b and value>0
        adjacency[a].append((b,serial,value));adjacency[b].append((a,serial,value))
    if any(not 1<=len(adjacency[n])<=2 for n in removed):
        raise ValueError('Only internal degree-one/two vertices may be eliminated')
    kept=np.array([n for n in range(size) if n not in removed],dtype=np.int64)
    lookup={int(n):i for i,n in enumerate(kept)}
    rr=list(map(int,kept));cc=list(range(len(kept)));vv=[1.]*len(kept)
    reduced=[];provenance=[];covered=set()
    for i,(a,b,r) in enumerate(branches):
        if a not in removed and b not in removed:
            reduced.append((lookup[a],lookup[b],str(r)))
            provenance.append(dict(kind='unchanged',original_branch_indices=[i],original_endpoints=[a,b]))
            covered.add(i)
    pending=set(removed)
    while pending:
        first=min(pending);component={first};stack=[first];pending.remove(first)
        while stack:
            for n,_,_ in adjacency[stack.pop()]:
                if n in pending:
                    pending.remove(n);component.add(n);stack.append(n)
        anchors=sorted({n for a in component for n,_,_ in adjacency[a] if n not in removed})
        serials={i for a in component for _,i,_ in adjacency[a]}
        assert not covered & serials
        covered.update(serials)
        if len(anchors)==1:
            for a in sorted(component):
                rr.append(a);cc.append(lookup[anchors[0]]);vv.append(1.)
            provenance.append(dict(kind='one_boundary_no_DC_current',original_branch_indices=sorted(serials),
                removed_vertices=sorted(component),original_endpoints=anchors))
        elif len(anchors)==2:
            left,right=anchors
            starts=[edge for edge in adjacency[left] if edge[0] in component]
            assert len(starts)==1
            previous=None;current=left;distance=Decimal(0);positions={};walk=[]
            while current!=right:
                choices=[e for e in adjacency[current] if e[0]!=previous and (e[0] in component or e[0]==right)]
                if current==left:choices=starts
                assert len(choices)==1
                target,serial,r=choices[0]
                distance+=r;walk.append(serial)
                previous,current=current,target
                if current!=right:positions[current]=distance
                assert len(walk)<=len(component)+1
            assert set(positions)==component and set(walk)==serials
            for a,x in sorted(positions.items()):
                fraction=float(x/distance)
                assert 0<fraction<1
                rr.extend([a,a]);cc.extend([lookup[left],lookup[right]]);vv.extend([1.-fraction,fraction])
            reduced.append((lookup[left],lookup[right],str(distance)))
            provenance.append(dict(kind='exact_series_resistance',original_branch_indices=walk,
                removed_vertices=sorted(component),original_endpoints=anchors,resistance_ohm=str(distance)))
        else:
            raise ValueError(f'Internal path has {len(anchors)} boundary vertices')
    assert covered==set(range(len(branches)))
    T=coo_matrix((vv,(rr,cc)),shape=(size,len(kept))).tocsr()
    assert max(abs(np.asarray(T.sum(axis=1)).ravel()-1.))<1e-15
    assert np.min(T.data)>0
    return T,kept,reduced,provenance
