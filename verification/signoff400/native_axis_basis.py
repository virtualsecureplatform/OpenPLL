"""Strict axis-tile controls with explicit native private-node identities.

This handles fully covered axis chains. It refuses open-end extrapolation,
outside endpoints or incomplete identity maps; it does not select snapshots or
qualify device/contact/zero-R domains.
"""
from collections import defaultdict
from fractions import Fraction as F
from floating_sheet_charge import sheet

def axis_template(box,axis,knots):
    box=list(map(F,box));knots=[(F(p),str(n)) for p,n in knots]
    if axis not in (0,1) or len(knots)<2 or box[0]>=box[2] or box[1]>=box[3]:raise ValueError('positive axis tile required')
    if knots[0][0]!=box[axis] or knots[-1][0]!=box[axis+2]:raise ValueError('native axis chain must cover exact tile bounds without clamp')
    if any(a[0]>=b[0] for a,b in zip(knots,knots[1:])):raise ValueError('native axis chain must increase strictly')
    if any(not n for _,n in knots):raise ValueError('native private-node identity required')
    points=[];names=[];lookup={};triangles=[]
    def node(point,name):
        if point not in lookup:lookup[point]=len(points);points.append(point);names.append(name)
        index=lookup[point]
        if names[index]!=name:raise ValueError('shared geometric point has inconsistent native identity')
        return index
    for (a,na),(b,nb) in zip(knots,knots[1:]):
        if axis==0:vertices=[(a,box[1]),(b,box[1]),(b,box[3]),(a,box[3])];ids=[na,nb,nb,na]
        else:vertices=[(box[0],a),(box[2],a),(box[2],b),(box[0],b)];ids=[na,na,nb,nb]
        ll,lr,ur,ul=[node(p,n) for p,n in zip(vertices,ids)];triangles.extend([(ll,lr,ur),(ll,ur,ul)])
    return dict(points=points,triangles=triangles,point_nodes=names)
def named_sheet(template):
    reference=sheet(template,'index:');result=[]
    for polygon,coefficients in reference['patches']:
        merged=defaultdict(lambda:[F(0)]*3)
        for key,values in coefficients.items():
            name=template['point_nodes'][int(key.split(':')[1])]
            for i,v in enumerate(values):merged[name][i]+=v
        result.append((polygon,{n:tuple(v) for n,v in merged.items() if any(v)}))
    return dict(patches=result)
def exact_axis_mass(box,axis,knots,reference='REF'):
    box=list(map(F,box));knots=[(F(p),n) for p,n in knots];width=box[3-axis]-box[1-axis];matrix=defaultdict(F)
    for (a,na),(b,nb) in zip(knots,knots[1:]):
        h=b-a;factor=width*h
        for i,n in enumerate((na,nb)):
            for j,m in enumerate((na,nb)):matrix[n,m]+=factor*(F(1,3) if i==j else F(1,6))
            matrix[n,reference]-=factor/2;matrix[reference,n]-=factor/2
        matrix[reference,reference]+=factor
    return {k:v for k,v in matrix.items() if v}
