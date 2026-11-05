"""Bounded Schur reduction of positive, capacitor-only floating components.

All primitive and wire cards remain unchanged. A grounded-path certificate
bounds the floating-block inverse; long-double residuals and roundoff bounds
are retained. Sparse pair export is checked against the energy congruence.
This does not qualify exterior loading or an analog/loop model.
"""
import argparse
import ctypes as ct
from fractions import Fraction as F
import heapq
import json
import math
import os
from pathlib import Path
import subprocess
import time
if __name__=='__main__':os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
from common_v3 import ROOT,save,sha,verify
from inventory_prototype_floating_C_components import components
from prepare_prototype_analog_reference import subcircuits
from prepare_prototype_BBPD_receiver_v3 import header
from resources import lease
from compiled_charge_v2 import execute
from check_prototype_capacitance_paths import certify
from project_prototype_fixed_rail_C_v2 import project,RAILS

LD=np.longdouble
U=2.0**-53

def up(x):return math.nextafter(float(x),math.inf)
def add(a,b):return up(a+b)
def mul(a,b):return up(a*b)
def root(a):return up(math.sqrt(a))
def gamma(n,u):return up((n*u)/(1-n*u))
def ptr(a):return ct.c_void_p(a.ctypes.data)


class Bridge:
    def __init__(self,file):
        self.lib=ct.CDLL(str(file));l=self.lib
        l.floating_long_double_digits.restype=ct.c_int
        self.digits=l.floating_long_double_digits()
        if self.digits<64 or np.finfo(LD).nmant+1!=self.digits:raise ValueError('matching extended-precision ABI required')
        l.floating_create.argtypes=[ct.c_int,ct.c_int,ct.c_int,*([ct.c_void_p]*4),ct.c_int,*([ct.c_void_p]*4),ct.c_int]
        l.floating_create.restype=ct.c_void_p
        l.floating_solve.argtypes=[ct.c_void_p,ct.c_int,ct.c_int,ct.c_void_p];l.floating_solve.restype=ct.c_int
        l.floating_products.argtypes=[ct.c_void_p,*([ct.c_void_p]*4)];l.floating_products.restype=ct.c_int
        l.floating_free.argtypes=[ct.c_void_p]


def coefficient(value):
    exact=F(value)*10**15
    if exact<=0:raise ValueError('floating-component capacitances must be strictly positive')
    double=float(exact);lower=math.nextafter(double,0)
    if not 0<F.from_float(lower)<=exact<=F.from_float(math.nextafter(double,math.inf)):raise ValueError('coefficient enclosure failed')
    # Native source decimals have finite base-10 representations. Parse their
    # exact fF-scaled spelling directly into extended precision.
    from decimal import Decimal,localcontext
    with localcontext() as c:
        c.prec=160;extended=LD(str(Decimal(value)*Decimal(10**15)))
    return double,extended,lower


def prepare(text,top):
    groups,stats=components(text,top)
    if len(groups)!=1 or groups[0]['negative_incident_capacitors']:
        raise ValueError('one positive floating component required')
    floats=groups[0]['nodes'];boundaries=groups[0]['boundaries']
    fi={n:i for i,n in enumerate(floats)};bi={n:i for i,n in enumerate(boundaries)}
    ff=[];fb=[];kept=[];direct_abs=np.zeros(len(boundaries),dtype=LD)
    for line in text.splitlines():
        f=line.split()
        if not f or not f[0].startswith('Cflat'):continue
        a,b=f[1:3]
        if a not in fi and b not in fi:
            kept.append(line)
            value=abs(LD(f[3])*LD(10**15))
            for n in (a,b):
                if n in bi:direct_abs[bi[n]]+=value
            continue
        value,extended,lower=coefficient(f[3])
        if a in fi and b in fi:ff.append((fi[a],fi[b],value,extended,lower))
        else:
            if b in fi:a,b=b,a
            if b not in bi:raise ValueError('unregistered retained boundary')
            fb.append((fi[a],bi[b],value,extended,lower))
    def arrays(rows):
        return (np.array([r[0] for r in rows],dtype=np.int32),np.array([r[1] for r in rows],dtype=np.int32),
                np.array([r[2] for r in rows],dtype=np.float64),np.array([r[3] for r in rows],dtype=LD),
                np.array([r[4] for r in rows],dtype=np.float64))
    return floats,boundaries,arrays(ff),arrays(fb),kept,direct_abs,stats


def inverse_certificate(n,ff,fb):
    graph=[[] for _ in range(n)];distance=[math.inf]*n;parent=[None]*n;queue=[]
    for k,(a,b,c) in enumerate(zip(ff[0],ff[1],ff[4])):
        r=up(1/float(c));graph[int(a)].append((int(b),r,k));graph[int(b)].append((int(a),r,k))
    for k,(a,c) in enumerate(zip(fb[0],fb[4])):
        a=int(a);r=up(1/float(c))
        if r<distance[a]:distance[a]=r;parent[a]=('boundary',k);heapq.heappush(queue,(r,a))
    while queue:
        d,a=heapq.heappop(queue)
        if d!=distance[a]:continue
        for b,r,k in graph[a]:
            candidate=add(d,r)
            if candidate<distance[b]:distance[b]=candidate;parent[b]=('floating',k,a);heapq.heappush(queue,(candidate,b))
    # Verify dyadic path bounds independently of the shortest-path arithmetic.
    for i,p in enumerate(parent):
        if p is None or not math.isfinite(distance[i]):raise ValueError('floating node lacks a retained boundary path')
        if p[0]=='boundary':needed=F(1)/F.from_float(float(fb[4][p[1]]))
        else:
            if distance[p[2]]>=distance[i]:raise ValueError('cyclic path certificate')
            needed=F.from_float(distance[p[2]])+F(1)/F.from_float(float(ff[4][p[1]]))
        if F.from_float(distance[i])<needed:raise ValueError('path resistance bound not outward rounded')
    total=sum((F.from_float(x) for x in distance),F())
    return dict(method='sum of grounded positive-path weighted Cauchy bounds',
        path_resistance_sum_upper_per_fF=str(total),lambda_min_lower_fF=str(1/total),
        parent_edges=parent,path_resistance_upper_per_fF=distance),up(float(total))


def solve(bridge,ff,fb,n,m,threads,output):
    handle=bridge.lib.floating_create(n,m,len(ff[0]),*(ptr(a) for a in ff[:4]),len(fb[0]),*(ptr(a) for a in fb[:4]),threads)
    if not handle:raise ValueError('floating block Cholesky factorization failed')
    h=np.memmap(output/'harmonic_basis.f64',dtype=np.float64,mode='w+',shape=(n,m))
    residual=np.memmap(output/'residual.f64',dtype=np.float64,mode='w+',shape=(n,m))
    q=np.memmap(output/'boundary_product.ld',dtype=LD,mode='w+',shape=(m,m));statistics=np.zeros(2,dtype=LD)
    try:
        for first in range(0,m,64):
            width=min(64,m-first)
            if not bridge.lib.floating_solve(handle,first,width,ptr(h)):raise ValueError('floating harmonic solve failed')
            print('HARMONIC_COLUMNS',first+width,'/',m,flush=True)
        if not np.isfinite(h).all() or h.min()<-1e-8 or h.max()>1+1e-8:raise ValueError('invalid harmonic extension')
        if not bridge.lib.floating_products(handle,ptr(h),ptr(residual),ptr(q),ptr(statistics)):
            raise ValueError('extended-precision residual failed')
    finally:bridge.lib.floating_free(handle)
    h.flush();residual.flush();q.flush()
    if not np.isfinite(residual).all() or not np.isfinite(q).all():raise ValueError('nonfinite capacitor reduction')
    return h,residual,q,statistics


def error_bounds(h,residual,stats,ff,fb,resistance_sum,digits):
    n,m=h.shape;uld=2.0**(-digits)
    degree=np.zeros(n,dtype=np.int64);row=np.zeros(n,dtype=LD);fbrow=np.zeros(n,dtype=LD)
    upperff=np.nextafter(ff[2],np.inf).astype(LD);upperfb=np.nextafter(fb[2],np.inf).astype(LD)
    for indices in (ff[0],ff[1]):np.add.at(degree,indices,1);np.add.at(row,indices,2*upperff)
    np.add.at(degree,fb[0],1);np.add.at(row,fb[0],upperfb);np.add.at(fbrow,fb[0],upperfb)
    hmax=up(max(abs(float(h.min())),abs(float(h.max()))));rmax=up(float(stats[1]))
    row_upper=np.nextafter(np.asarray(row*(1+LD(gamma(int(degree.max())+4,uld))),dtype=np.float64),np.inf)
    fb_upper=np.nextafter(np.asarray(fbrow*(1+LD(gamma(int(degree.max())+4,uld))),dtype=np.float64),np.inf)
    # Products are evaluated as sums of c*(h_i-h_j), using original extended
    # coefficients. This includes decimal conversion and double-result casting.
    e=np.array([add(mul(gamma(3*int(d)+12,uld),add(mul(float(a),hmax),float(b))),mul(gamma(2,U),rmax))
                for d,a,b in zip(degree,row_upper,fb_upper)])
    r2=mul(up(float(stats[0])),up(1+gamma(2*n*m+100,uld)))
    e2=sum((F.from_float(float(x))**2 for x in e),F())
    residual_norm=add(root(r2),root(mul(m,up(float(e2)))))
    energy=mul(mul(residual_norm,residual_norm),resistance_sum)
    energy_row=mul(root(m),energy)
    ah=np.abs(h);mass=np.nextafter(np.asarray(ah.sum(axis=0),dtype=np.float64)*(1+gamma(n+2,U)),np.inf)
    error_product=ah.T@e;error_product=np.nextafter(error_product*(1+gamma(n+2,U)),np.inf)
    correction=(m*error_product+math.fsum(error_product))/2
    correction+=gamma(n+3,U)*rmax*(m*mass+math.fsum(mass))/2
    count=np.zeros(m,dtype=np.int64);weight=np.zeros(m,dtype=LD)
    np.add.at(count,fb[1],1);np.add.at(weight,fb[1],upperfb)
    weight*=1+LD(gamma(int(count.max())+4,uld))
    qerror=np.array([mul(gamma(2*int(k)+8,uld),mul(up(float(w)),hmax)) for k,w in zip(count,weight)])
    arithmetic=(m*qerror+math.fsum(qerror))/2+correction
    arithmetic+=np.asarray([mul(gamma(int(k)+8,uld),up(float(w))) for k,w in zip(count,weight)])
    wu=np.nextafter(np.asarray(weight,dtype=np.float64),np.inf)
    arithmetic+=gamma(16,uld)*((m*wu+math.fsum(wu))*hmax+(m*mass+math.fsum(mass))*rmax+wu)
    bound=np.nextafter((arithmetic+energy_row)*(1+gamma(64,U)),np.inf)
    return bound,dict(extended_mantissa_bits=digits,positive_path_inverse_bound_used=True,
        residual_Frobenius_norm_upper_fF=residual_norm,energy_congruence_error_spectral_upper_fF=energy,
        energy_congruence_error_row_upper_fF=energy_row,max_roundoff_and_solve_row_bound_fF=float(bound.max()),
        residual_entry_roundoff_upper_max_fF=float(e.max()),source_coefficient_units='fF')


def sparsify(s,base,arithmetic,relative):
    m=len(s);i,j=np.triu_indices(m,1);wanted=-s[i,j]
    scale=base+np.abs(np.diag(s));scale=np.maximum(scale,LD('1e-30'))
    attempts=[]
    for threshold in (1e-3,1e-4,1e-5,1e-6,1e-7,1e-8,1e-9,1e-10,1e-11,1e-12,1e-13,1e-14,1e-15,0):
        use=wanted>LD(threshold);values_F=np.asarray(wanted[use],dtype=np.float64)*1e-15
        values=values_F.astype(LD)*LD(10**15)
        off=np.abs(wanted);off[use]=np.abs(values-wanted[use])
        offsum=np.zeros(m,dtype=LD);diagonal=np.zeros(m,dtype=LD)
        np.add.at(offsum,i,off);np.add.at(offsum,j,off)
        np.add.at(diagonal,i[use],values);np.add.at(diagonal,j[use],values)
        observed=np.abs(diagonal-np.diag(s))+offsum
        # Include positive summation and final decimal/IEEE coefficient spelling.
        observed+=LD(gamma(m+8,float(np.finfo(LD).eps/2)))*(np.abs(diagonal)+offsum+np.abs(np.diag(s)))*8
        total=observed+arithmetic.astype(LD)
        normalized=np.max(total/scale)
        attempts.append(dict(threshold_fF=threshold,pairs=int(use.sum()),maximum_normalized_row_error=float(normalized)))
        print('SPARSE_THRESHOLD',threshold,'PAIRS',int(use.sum()),'ROW_ERROR',float(normalized),flush=True)
        if normalized<=relative:
            return i[use],j[use],values_F,total,scale,attempts
    raise ValueError('no sparse export meets the requested numerical row-error budget')


def run(models,attachment,output,threads,relative,deadline_owner):
    mr=models/'assessment.json';record=json.loads(mr.read_text());verify(record['input_sha256']);verify(record['artifacts'])
    if not record['each_fixed_supply_dynamic_C_operator_passivity_certified']:raise ValueError('passive source model required')
    source=models/(attachment+'.spice');text=source.read_text();blocks=subcircuits(text)
    if len(blocks)!=1:raise ValueError('one complete flat model required')
    top=next(iter(blocks));deadline=json.loads(deadline_owner.read_text())['deadline_uptime']
    output.mkdir(parents=True,exist_ok=False)
    save(output/'status.json',dict(state='preparing_positive_floating_graph',release_ready=False))
    floats,boundaries,ff,fb,kept,base,stats=prepare(text,top);n=len(floats);m=len(boundaries)
    proof,inverse=inverse_certificate(n,ff,fb);save(output/'grounded_paths.json',proof)
    save(output/'node_inventory.json',dict(floating_nodes=floats,retained_boundaries=boundaries,**stats))
    cpp=ROOT/'tools/floating_schur/cholmod_bridge.cpp';binary=output/'cholmod_bridge.so'
    command=['g++','-std=c++20','-O3','-fPIC','-shared','-fopenmp','-fno-fast-math','-ffp-contract=off',
             '-I/usr/include/suitesparse',str(cpp),'-lcholmod','-o',str(binary)]
    execute(command,output/'build.log',deadline,4)
    bridge=Bridge(binary);save(output/'status.json',dict(state='factoring_and_solving_floating_charge_equations',release_ready=False))
    h,r,q,norm=solve(bridge,ff,fb,n,m,threads,output)
    bounds,details=error_bounds(h,r,norm,ff,fb,inverse,bridge.digits)
    print('FLOATING_SOLVE_BOUNDS',json.dumps(details),flush=True)
    correction=h.T@r
    weights=np.zeros(m,dtype=LD);np.add.at(weights,fb[1],fb[3])
    s=-(q+q.T)/2+(correction.astype(LD)+correction.T.astype(LD))/2
    s[np.diag_indices(m)]+=weights
    if not np.isfinite(s).all():raise ValueError('nonfinite reduced capacitor operator')
    np.save(output/'energy_boundary_fF.npy',s)
    ii,jj,values,total,scale,attempts=sparsify(s,base,bounds,relative)
    lines=[];floating_set=set(floats)
    for line in text.splitlines():
        f=line.split()
        if f and f[0].startswith('Cflat') and (f[1] in floating_set or f[2] in floating_set):continue
        if f and f[0].lower()=='.ends':
            lines.extend('Ckron'+str(k)+' '+boundaries[int(a)]+' '+boundaries[int(b)]+' '+format(float(c),'.17e')
                         for k,(a,b,c) in enumerate(zip(ii,jj,values)))
        lines.append(line)
    model='\n'.join(lines)+'\n';target=output/(attachment+'.spice');target.write_text(model)
    before=[line for line in text.splitlines() if line.startswith(('Xflat','Rwire'))]
    after=[line for line in model.splitlines() if line.startswith(('Xflat','Rwire'))]
    if before!=after:raise ValueError('retained primitive or wire cards changed')
    pairs={}
    for line in model.splitlines():
        f=line.split()
        if f and f[0].startswith(('Cflat','Ckron')):
            key=tuple(sorted(f[1:3]));pairs[key]=pairs.get(key,F())+F(f[3])
    passive=certify(project(pairs,set(RAILS)));save(output/'fixed_rail_passivity.json',passive)
    if not passive['passivity_certified']:raise ValueError('reduced capacitor operator lacks an exact passivity certificate')
    save(output/'reduction_bounds.json',dict(**details,relative_row_tolerance=relative,attempts=attempts,
        maximum_normalized_row_error=float(np.max(total/scale)),row_error_upper_fF=list(map(float,total)),
        row_reference_scale_fF=list(map(float,scale)),capacitor_pairs_after=len(pairs)))
    inputs={str(p):sha(p) for p in (mr,source,deadline_owner,cpp,binary,Path(__file__).resolve(),
        Path(__file__).with_name('inventory_prototype_floating_C_components.py'),
        Path(__file__).with_name('check_prototype_capacitance_paths.py'),Path(__file__).with_name('project_prototype_fixed_rail_C_v2.py'))}
    verify(inputs)
    save(output/'assessment.json',dict(input_sha256=inputs,
        artifacts={str(p):sha(p) for p in output.iterdir() if p.is_file() and p.name not in ('assessment.json','status.json')},
        candidate_gds_sha256=record['candidate_gds_sha256'],assembled_candidate_gds_sha256=record['assembled_candidate_gds_sha256'],
        attachment=attachment,eliminated_capacitor_only_nodes=n,retained_boundary_nodes=m,
        bounded_floating_C_terminal_reduction_verified=True,all_primitive_and_wire_cards_unchanged=True,
        each_fixed_supply_dynamic_C_operator_passivity_certified=True,relative_row_error_budget=relative,
        maximum_normalized_row_error=float(np.max(total/scale)),
        capacitance_lifts_are_exact_matrix_congruences=False,zero_wire_R_topology_and_capacitance_operator_identity_verified=False,
        numerical_reduction_with_explicit_error_bound=True,ideal_constant_supply_assumption=True,
        native_reduced_model_correlation_complete=False,parent_loading_complete=False,
        FOM_fill_electrical_coverage_complete=False,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='bounded_floating_C_reduction_complete_native_validation_pending',release_ready=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('models','output','deadline-owner'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--attachment',choices=('driver','farthest'),required=True)
    parser.add_argument('--threads',type=int,default=8);parser.add_argument('--relative-row-tolerance',type=float,default=1e-6)
    a=parser.parse_args()
    if not 1<=a.threads<=16 or not 0<a.relative_row_tolerance<=1e-5:parser.error('bounded resources and numerical tolerance required')
    os.environ.update(OMP_NUM_THREADS=str(a.threads),OPENBLAS_NUM_THREADS='1')
    with lease(a.threads,48,json.loads(a.deadline_owner.read_text())['deadline_uptime']):
        run(a.models.resolve(),a.attachment,a.output.resolve(),a.threads,a.relative_row_tolerance,a.deadline_owner.resolve())
