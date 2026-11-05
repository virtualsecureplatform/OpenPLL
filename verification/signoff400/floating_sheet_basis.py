"""Exact-rational P1 sheet templates on conforming Manhattan grids.

Coordinates may use any common length unit. K is dimensionless unit-sheet
conductance; M is unit-area-density mass in squared coordinate units. Neither
is a selected PDK resistance/PVT model or an assembled physical RC domain.
"""
from collections import Counter,defaultdict
from fractions import Fraction as F

def ring_area(r):return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(r,r[1:]+r[:1])))/2

def inside(point,ring):
    x,y=point;result=False
    for a,b in zip(ring,ring[1:]+ring[:1]):
        if (a[1]>y)!=(b[1]>y):
            crossing=a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1])
            if x<crossing:result=not result
    return result

def mesh(hull,holes=(),refinement=1):
    if refinement not in (1,2,4,8,16):raise ValueError('supported refinement is 1/2/4/8/16')
    rings=[[(F(x),F(y)) for x,y in ring] for ring in [hull,*holes]]
    segments=[]
    for ri,ring in enumerate(rings):
        if len(ring)<4 or len(set(ring))!=len(ring):raise ValueError('simple nondegenerate contours required')
        for i,(a,b) in enumerate(zip(ring,ring[1:]+ring[:1])):
            if a==b or (a[0]!=b[0] and a[1]!=b[1]):raise ValueError('Manhattan nonzero edges required')
            segments.append((ri,i,a,b))
    def intersect(a,b,c,d):
        if max(min(a[0],b[0]),min(c[0],d[0]))>min(max(a[0],b[0]),max(c[0],d[0])) or max(min(a[1],b[1]),min(c[1],d[1]))>min(max(a[1],b[1]),max(c[1],d[1])):return False
        return True # Axis-aligned bounding boxes exactly characterize intersection.
    for j,(r,i,a,b) in enumerate(segments):
        for s,k,c,d in segments[j+1:]:
            adjacent=r==s and ((i-k)%len(rings[r]) in (1,len(rings[r])-1))
            if not adjacent and intersect(a,b,c,d):raise ValueError('intersecting or touching nonadjacent contour edges')
    expected_area=ring_area(rings[0])-sum(map(ring_area,rings[1:]),F(0))
    if expected_area<=0:raise ValueError('positive polygon area required')
    def axis(which):
        values=sorted({p[which] for ring in rings for p in ring})
        return sorted({a+(b-a)*i/refinement for a,b in zip(values,values[1:]) for i in range(refinement+1)})
    xs,ys=axis(0),axis(1);points=[];ids={};triangles=[];stiffness=defaultdict(F);mass=defaultdict(F);edges=Counter();area=F(0)
    def node(p):
        if p not in ids:ids[p]=len(points);points.append(p)
        return ids[p]
    for y0,y1 in zip(ys,ys[1:]):
        for x0,x1 in zip(xs,xs[1:]):
            center=((x0+x1)/2,(y0+y1)/2)
            if not inside(center,rings[0]) or any(inside(center,h) for h in rings[1:]):continue
            ll,lr,ur,ul=[node(p) for p in [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]]
            for tri in [(ll,lr,ur),(ll,ur,ul)]:
                triangles.append(tri);p=[points[i] for i in tri]
                determinant=(p[1][0]-p[0][0])*(p[2][1]-p[0][1])-(p[2][0]-p[0][0])*(p[1][1]-p[0][1])
                if determinant<=0:raise ValueError('positive triangle orientation required')
                area+=determinant/2;b=[p[1][1]-p[2][1],p[2][1]-p[0][1],p[0][1]-p[1][1]];c=[p[2][0]-p[1][0],p[0][0]-p[2][0],p[1][0]-p[0][0]]
                for i in range(3):
                    for j in range(3):
                        stiffness[tri[i],tri[j]]+=(b[i]*b[j]+c[i]*c[j])/(2*determinant)
                        mass[tri[i],tri[j]]+=determinant/(12 if i==j else 24)
                for a,d in zip(tri,tri[1:]+tri[:1]):edges[tuple(sorted((a,d)))]+=1
    if area!=expected_area:raise ValueError('triangle coverage area differs from contour')
    boundary=F(0)
    for (a,b),count in edges.items():
        if count not in (1,2):raise ValueError('nonmanifold triangle edge')
        if count==1:
            p,q=points[a],points[b]
            if p[0]!=q[0] and p[1]!=q[1]:raise ValueError('unexpected diagonal boundary')
            boundary+=abs(p[0]-q[0])+abs(p[1]-q[1])
    perimeter=sum((abs(a[0]-b[0])+abs(a[1]-b[1]) for _,_,a,b in segments),F(0))
    if boundary!=perimeter:raise ValueError('triangle coverage boundary differs from contour')
    return dict(points=points,triangles=triangles,stiffness=dict(stiffness),mass=dict(mass),area=area,perimeter=perimeter)

def energy(matrix,values):return sum((v*values[a]*values[b] for (a,b),v in matrix.items()),F(0))

def certify(template):
    points=template['points'];k=template['stiffness'];m=template['mass'];n=len(points);rows=defaultdict(F);neighbors=[set() for _ in points]
    for (a,b),v in k.items():
        if v!=k.get((b,a),F(0)):raise ValueError('asymmetric sheet matrix')
        rows[a]+=v
        if a!=b:
            if v>0:raise ValueError('positive off-diagonal sheet coefficient')
            if v<0:neighbors[a].add(b)
    if any(rows.values()) or any(k.get((i,i),F(0))<=0 for i in range(n)):raise ValueError('invalid floating nullspace or diagonal')
    visited={0};pending=[0]
    while pending:
        for b in neighbors[pending.pop()]-visited:visited.add(b);pending.append(b)
    if len(visited)!=n:raise ValueError('disconnected sheet conductance')
    if energy(m,[F(1)]*n)!=template['area']:raise ValueError('constant mass differs from area')
    for a,b,c in [(F(1),F(0),F(0)),(F(0),F(1),F(0)),(F(3,2),F(-5,3),F(7))]:
        v=[a*x+b*y+c for x,y in points]
        if energy(k,v)!=template['area']*(a*a+b*b):raise ValueError('linear sheet energy differs from exact continuum integral')
    return dict(exact_area_and_boundary=True,exact_constant_nullspace=True,connected_nonnegative_edge_conductances=True,exact_linear_voltage_energies=True,exact_constant_mass=True,nodes=n,triangles=len(template['triangles']),finite_R_discretization_control_passed=True,capacitance_attachment_qualified=False,resistance_units_and_PVT_qualified=False,finite_R_basis_qualified=False,release_qualified=False)
