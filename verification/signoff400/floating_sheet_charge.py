"""Exact-rational reference integration of uniform area/line C operators.

P1 sheets retain spatial voltage variation and explicit reference fields.
Unsupported spatial support raises; no extrapolation or ideal-conductor
fallback is used. This is a reference oracle, not the full-layout runtime.
"""
from collections import defaultdict
from fractions import Fraction as F

def constant(node):return dict(constant=node)
def sheet(template,prefix):
    patches=[]
    for tri in template['triangles']:
        points=[template['points'][i] for i in tri]
        determinant=(points[1][0]-points[0][0])*(points[2][1]-points[0][1])-(points[2][0]-points[0][0])*(points[1][1]-points[0][1])
        if determinant<=0:raise ValueError('positive basis triangle required')
        coefficients={}
        for i in range(3):
            a,b=points[(i+1)%3],points[(i+2)%3]
            coefficients[prefix+str(tri[i])]=((a[0]*b[1]-b[0]*a[1])/determinant,(a[1]-b[1])/determinant,(b[0]-a[0])/determinant)
        patches.append((points,coefficients))
    return dict(patches=patches)
def cross(a,b,p):return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
def clip_polygon(polygon,triangle):
    result=polygon
    for a,b in zip(triangle,triangle[1:]+triangle[:1]):
        if not result:break
        clipped=[]
        for p,q in zip(result,result[1:]+result[:1]):
            vp,vq=cross(a,b,p),cross(a,b,q);ip,iq=vp>=0,vq>=0
            if ip:clipped.append(p)
            if ip!=iq:
                t=vp/(vp-vq);clipped.append((p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
        result=[]
        for p in clipped:
            if not result or p!=result[-1]:result.append(p)
        if len(result)>1 and result[0]==result[-1]:result.pop()
    return result

def moments(polygon):
    result=[F(0)]*6
    if len(polygon)<3:return result
    for i in range(1,len(polygon)-1):
        points=[polygon[0],polygon[i],polygon[i+1]];area=cross(*points)/2
        if area<0:raise ValueError('negative integration polygon orientation')
        xs=[p[0] for p in points];ys=[p[1] for p in points]
        result[0]+=area;result[1]+=area*sum(xs)/3;result[2]+=area*sum(ys)/3
        result[3]+=area*(sum(x*x for x in xs)+sum(xs[a]*xs[b] for a,b in ((0,1),(0,2),(1,2))))/6
        result[4]+=area*(sum(xs)*sum(ys)+sum(x*y for x,y in points))/12
        result[5]+=area*(sum(y*y for y in ys)+sum(ys[a]*ys[b] for a,b in ((0,1),(0,2),(1,2))))/6
    return result

def difference(a,b):
    result=defaultdict(lambda:[F(0)]*3)
    for sign,values in ((1,a),(-1,b)):
        for node,v in values.items():
            for i,x in enumerate(v):result[node][i]+=sign*x
    return {node:tuple(v) for node,v in result.items() if any(v)}
def patches(basis,polygon):
    if 'constant' in basis:return [(polygon,{basis['constant']:(F(1),F(0),F(0))})]
    result=[]
    for triangle,values in basis['patches']:
        part=clip_polygon(polygon,triangle)
        if moments(part)[0]:result.append((part,values))
    return result

def area(source,target,rectangle,density=1):
    x0,y0,x1,y1=map(F,rectangle);density=F(density)
    if x0>x1 or y0>y1:raise ValueError('ordered area support required')
    if x0==x1 or y0==y1:return {}
    rectangle=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)];matrix=defaultdict(F);covered=F(0)
    for polygon,source_values in patches(source,rectangle):
        for polygon2,target_values in patches(target,polygon):
            m=moments(polygon2);covered+=m[0];values=difference(source_values,target_values)
            for a,(ac,ax,ay) in values.items():
                for b,(bc,bx,by) in values.items():
                    matrix[a,b]+=density*(ac*bc*m[0]+(ac*bx+ax*bc)*m[1]+(ac*by+ay*bc)*m[2]+ax*bx*m[3]+(ax*by+ay*bx)*m[4]+ay*by*m[5])
    if covered!=(x1-x0)*(y1-y0):raise ValueError('area operator extends outside or overlaps basis support')
    return {key:v for key,v in matrix.items() if v}

def edge(edge):
    x0,y0,x1,y1=map(F,edge)
    if (x0!=x1 and y0!=y1) or x0>x1 or y0>y1:raise ValueError('ordered axis-aligned line required')
    return (x0,y0),(x1-x0,y1-y0),(x1-x0)+(y1-y0)
def line_patches(basis,origin,delta):
    if 'constant' in basis:return [(F(0),F(1),{basis['constant']:(F(1),F(0))})]
    result=[]
    for triangle,coefficients in basis['patches']:
        lo,hi=F(0),F(1)
        for a,b in zip(triangle,triangle[1:]+triangle[:1]):
            at=cross(a,b,origin);slope=(b[0]-a[0])*delta[1]-(b[1]-a[1])*delta[0]
            if slope>0:lo=max(lo,-at/slope)
            elif slope<0:hi=min(hi,-at/slope)
            elif at<0:hi=lo
        if lo>=hi:continue
        values={node:(c+x*origin[0]+y*origin[1],x*delta[0]+y*delta[1]) for node,(c,x,y) in coefficients.items()}
        result.append((lo,hi,{node:v for node,v in values.items() if any(v)}))
    return result

def restricted_at(parts,point):
    candidates=[v for lo,hi,v in parts if lo<point<hi]
    if not candidates:raise ValueError('line operator extends outside basis support')
    if any(v!=candidates[0] for v in candidates[1:]):raise ValueError('inconsistent continuous basis on shared line')
    return candidates[0]

def line(source,target,source_edge,target_edge,density=1):
    so,sd,length=edge(source_edge);to,td,other_length=edge(target_edge);density=F(density)
    if length!=other_length:raise ValueError('unequal native line lengths')
    if not length:return {}
    sp,tp=line_patches(source,so,sd),line_patches(target,to,td)
    cuts=sorted({F(0),F(1),*[v for parts in (sp,tp) for lo,hi,_ in parts for v in (lo,hi)]});matrix=defaultdict(F)
    for lo,hi in zip(cuts,cuts[1:]):
        source_values=restricted_at(sp,(lo+hi)/2);target_values=restricted_at(tp,(lo+hi)/2);values=defaultdict(lambda:[F(0),F(0)])
        for sign,coefficients in ((1,source_values),(-1,target_values)):
            for node,v in coefficients.items():
                for i,x in enumerate(v):values[node][i]+=sign*x
        m0=hi-lo;m1=(hi*hi-lo*lo)/2;m2=(hi**3-lo**3)/3
        for a,(ac,ax) in values.items():
            for b,(bc,bx) in values.items():matrix[a,b]+=density*length*(ac*bc*m0+(ac*bx+ax*bc)*m1+ax*bx*m2)
    return {key:v for key,v in matrix.items() if v}
