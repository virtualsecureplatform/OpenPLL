"""High-precision reference oracle for projected P1 arctangent fringe energy.

Geometry partition and polynomial coefficients are exact rational values.
Decimal arctan/log moments retain the recorded Lorentzian normal density.
This control oracle supplies no full-layout integration-error qualification.
"""
from collections import defaultdict
from decimal import Decimal as D,localcontext
from fractions import Fraction as F
from floating_sheet_charge import edge,line_patches,restricted_at,patches,clip_polygon,moments,difference

def decimal(value):
    v=F(value);return D(v.numerator)/D(v.denominator)
def atan_positive(value):
    if value<0:raise ValueError('positive arctangent required')
    factor=1
    while value>D('0.125'):
        value=value/(1+(1+value*value).sqrt());factor*=2
    power=value;square=-value*value;result=value;denominator=1
    while True:
        power*=square;denominator+=2;updated=result+power/denominator
        if updated==result:return result*factor
        result=updated

def lorentz_moments(near,far,mult,precision=80):
    if not 0<=near<=far or mult<0:raise ValueError('native fringe distance/multiplier')
    if near==far or mult==0:return (D(0),)*4
    with localcontext() as ctx:
        ctx.prec=precision+20;n,f,m=map(decimal,(near,far,mult));z=m*max(abs(n),abs(f))
        # Low-multiplier higher moments subtract terms differing by O(z^2).
        ctx.prec=precision+20+max(0,-2*z.adjusted())
        n,f,m=map(decimal,(near,far,mult));delta=f-n
        m0=atan_positive(m*delta/(1+m*m*f*n))
        m1=((1+m*m*f*f)/(1+m*m*n*n)).ln()/(2*m)
        m2=delta/m-m0/(m*m)
        m3=(f*f-n*n)/(2*m)-m1/(m*m)
        return m0,m1,m2,m3

def add(a,b):
    result=[F(0)]*max(len(a),len(b))
    for i,v in enumerate(a):result[i]+=v
    for i,v in enumerate(b):result[i]+=v
    return result
def multiply(a,b):
    result=[F(0)]*(len(a)+len(b)-1)
    for i,x in enumerate(a):
        for j,y in enumerate(b):result[i+j]+=x*y
    return result
def scale(a,value):return [v*value for v in a]
def subtract(a,b):return add(a,scale(b,-1))
def integrated_tangent_product(a,b,lower,upper):
    ac,ad,au=a;bc,bd,bu=b;av=[ac,ad];bv=[bc,bd]
    result=multiply(multiply(av,bv),subtract(upper,lower))
    result=add(result,scale(multiply(add(scale(av,bu),scale(bv,au)),subtract(multiply(upper,upper),multiply(lower,lower))),F(1,2)))
    return add(result,scale(subtract(multiply(multiply(upper,upper),upper),multiply(multiply(lower,lower),lower)),au*bu/3))

def slices(polygon,normal,origin,sign):
    along=1-normal;poly=[(sign*(p[normal]-origin),p[along]) for p in polygon];cuts=sorted({p[0] for p in poly})
    for lo,hi in zip(cuts,cuts[1:]):
        if lo<0:raise ValueError('fringe polygon crosses native source plane')
        mid=(lo+hi)/2;bounds=[]
        for a,b in zip(poly,poly[1:]+poly[:1]):
            if min(a[0],b[0])<mid<max(a[0],b[0]):
                slope=(b[1]-a[1])/(b[0]-a[0]);bounds.append([a[1]-slope*a[0],slope])
        if len(bounds)!=2:raise ValueError('convex fringe slice needs two boundaries')
        bounds.sort(key=lambda p:p[0]+p[1]*mid);yield lo,hi,*bounds

def fringe(source,target,source_edge,rectangle,direction,density,mult,precision=80):
    if direction not in (1,2,4,8):raise ValueError('native fringe direction')
    if precision<40:raise ValueError('reference precision must be at least 40 digits')
    origin,delta,length=edge(source_edge);normal=0 if direction in (1,4) else 1;along=1-normal;sign=-1 if direction in (1,8) else 1
    if delta[normal] or delta[along]<=0:raise ValueError('source edge orientation disagrees with fringe direction')
    box=list(map(F,rectangle));density,mult=F(density),F(mult)
    if mult<0:raise ValueError('negative native fringe multiplier')
    if sign>0:box[normal]=max(box[normal],origin[normal])
    else:box[normal+2]=min(box[normal+2],origin[normal])
    if box[0]>box[2] or box[1]>box[3]:raise ValueError('invalid clipped native fringe box')
    if box[0]==box[2] or box[1]==box[3]:return {}
    rectangle=[(box[0],box[1]),(box[2],box[1]),(box[2],box[3]),(box[0],box[3])];parts=line_patches(source,origin,delta)
    cuts=sorted({F(0),F(1),*[v for lo,hi,_ in parts for v in (lo,hi)]});covered=F(0)
    with localcontext() as ctx:
        ctx.prec=precision;matrix=defaultdict(D);factor=decimal(density)*D(float(.6366))
        for lo,hi in zip(cuts,cuts[1:]):
            strip=list(box);strip[along]=max(strip[along],origin[along]+lo*delta[along]);strip[along+2]=min(strip[along+2],origin[along]+hi*delta[along])
            if strip[along]>=strip[along+2]:continue
            values=restricted_at(parts,(lo+hi)/2);source_values={}
            for node,(c,s) in values.items():
                gradient=s/delta[along];entry=[c-gradient*origin[along],F(0),F(0)];entry[along+1]=gradient;source_values[node]=entry
            strip_polygon=[(strip[0],strip[1]),(strip[2],strip[1]),(strip[2],strip[3]),(strip[0],strip[3])]
            for polygon,target_values in patches(target,strip_polygon):
                covered+=moments(polygon)[0];vector=difference(source_values,target_values)
                transformed={node:(v[0]+v[normal+1]*origin[normal],sign*v[normal+1],v[along+1]) for node,v in vector.items()}
                for near,far,lower,upper in slices(polygon,normal,origin[normal],sign):
                    mm=lorentz_moments(near,far,mult,precision)
                    for a,av in transformed.items():
                        for b,bv in transformed.items():
                            polynomial=integrated_tangent_product(av,bv,lower,upper)
                            matrix[a,b]+=factor*sum((decimal(c)*m for c,m in zip(polynomial,mm)),D(0))
        if covered!=(box[2]-box[0])*(box[3]-box[1]):raise ValueError('fringe operator extends outside or overlaps basis support')
        return {key:float(v) for key,v in matrix.items() if v}
