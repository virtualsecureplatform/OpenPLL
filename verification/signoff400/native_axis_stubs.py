"""Parameterized passive end-stub construction for continuous native chains.

Existing native resistors are retained numerically. Only uncovered geometric
end strips receive new finite resistors and latent voltages. No R units/PVT,
contact-region interpretation or full physical domain is qualified here.
"""
from collections import defaultdict
from fractions import Fraction as F
from native_axis_basis import axis_template,exact_axis_mass

def augment(box,axis,knots,resistances,sheet_resistance,namespace,refinement=1):
    box=list(map(F,box));knots=[(F(x),str(n)) for x,n in knots];resistances=list(map(F,resistances));sheet_resistance=F(sheet_resistance)
    if axis not in (0,1) or len(knots)<2 or len(resistances)!=len(knots)-1 or not namespace:raise ValueError('complete native axis chain required')
    if refinement not in (1,2,4,8,16):raise ValueError('supported refinement required')
    width=box[3-axis]-box[1-axis]
    if width<=0 or box[axis]>=box[axis+2] or sheet_resistance<=0:raise ValueError('positive geometry and sheet resistance required')
    if knots[0][0]<box[axis] or knots[-1][0]>box[axis+2]:raise ValueError('native chain outside physical tile')
    if any(a[0]>=b[0] for a,b in zip(knots,knots[1:])) or any(r<=0 for r in resistances):raise ValueError('positive native resistors and increasing axis required; zero-R needs its own constraint model')
    native_names={n for _,n in knots}
    extended=list(knots);values=list(resistances);stubs=[]
    if knots[0][0]>box[axis]:
        name=namespace+':lo';r=sheet_resistance*(knots[0][0]-box[axis])/width;extended.insert(0,(box[axis],name));values.insert(0,r);stubs.append(name)
    if knots[-1][0]<box[axis+2]:
        name=namespace+':hi';r=sheet_resistance*(box[axis+2]-knots[-1][0])/width;extended.append((box[axis+2],name));values.append(r);stubs.append(name)
    if native_names&set(stubs):raise ValueError('stub/native identity collision')
    refined=[extended[0]];edges=[];latent=list(stubs)
    for i,((a,na),(b,nb),resistance) in enumerate(zip(extended,extended[1:],values)):
        prior=na
        for k in range(1,refinement+1):
            name=nb if k==refinement else namespace+':edge'+str(i)+':n'+str(refinement)+':'+str(k)
            if name in native_names and name!=nb:raise ValueError('latent/native identity collision')
            point=a+(b-a)*F(k,refinement);refined.append((point,name));edges.append((prior,name,resistance/refinement));prior=name
            if k<refinement:latent.append(name)
    if len(set(latent))!=len(latent) or set(latent)&native_names:raise ValueError('generated voltage identity collision')
    template=axis_template(box,axis,refined);mass=exact_axis_mass(box,axis,refined);conductance=defaultdict(F)
    for a,b,r in edges:
        g=1/r;conductance[a,a]+=g;conductance[b,b]+=g;conductance[a,b]-=g;conductance[b,a]-=g
    return dict(template=template,knots=refined,edges=edges,conductance=dict(conductance),unit_area_mass=mass,native_nodes=sorted(native_names),latent_nodes=latent,end_stub_nodes=stubs,native_edges=[(a[1],b[1],r) for a,b,r in zip(knots,knots[1:],resistances)],native_resistors_preserved_by_series_refinement=True,physical_domain_complete=False,resistance_units_and_PVT_qualified=False,release_qualified=False)

def schur_eliminate(matrix,nodes):
    result=defaultdict(F,matrix)
    for pivot in nodes:
        diagonal=result.get((pivot,pivot),F(0))
        if diagonal<=0:raise ValueError('positive Schur pivot required')
        neighbors={b for a,b in result if a==pivot and b!=pivot and result[a,b]}
        for a in neighbors:
            for b in neighbors:result[a,b]-=result.get((a,pivot),F(0))*result.get((pivot,b),F(0))/diagonal
        result=defaultdict(F,{(a,b):v for (a,b),v in result.items() if a!=pivot and b!=pivot and v})
    return dict(result)

def complex_solve(a,b):
    a=[list(map(complex,row)) for row in a];b=list(map(complex,b));original=[row[:] for row in a];rhs=b[:];n=len(b)
    for k in range(n):
        pivot=max(range(k,n),key=lambda i:abs(a[i][k]));a[k],a[pivot]=a[pivot],a[k];b[k],b[pivot]=b[pivot],b[k]
        if not a[k][k]:raise ValueError('singular RC system')
        for i in range(k+1,n):
            factor=a[i][k]/a[k][k]
            for j in range(k,n):a[i][j]-=factor*a[k][j]
            b[i]-=factor*b[k]
    x=[0j]*n
    for i in range(n-1,-1,-1):x[i]=(b[i]-sum(a[i][j]*x[j] for j in range(i+1,n)))/a[i][i]
    residual=max([abs(sum(row[j]*x[j] for j in range(n))-r)/max(sum(abs(v) for v in row)*max(map(abs,x),default=0)+abs(r),1e-300) for row,r in zip(original,rhs)]+[0.])
    if residual>1e-12:raise ValueError('original RC equations exceed residual criterion')
    return x,residual

def port_admittance(model,port,omega,capacitance_density=1):
    nodes=list(dict.fromkeys(n for _,n in model['knots']));inside=[n for n in nodes if n!=port];s=1j*omega
    def coefficient(a,b):return complex(float(model['conductance'].get((a,b),0)))+s*float(capacitance_density)*float(model['unit_area_mass'].get((a,b),0))
    a=[[coefficient(i,j) for j in inside] for i in inside];b=[-coefficient(i,port) for i in inside];values,residual=complex_solve(a,b)
    return coefficient(port,port)+sum(coefficient(port,n)*v for n,v in zip(inside,values)),residual
