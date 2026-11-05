#!/usr/bin/env python3
"""Bound lumped wire capacitance while eliminating floating nodes by KCL.

For one boundary at1V and the other active-device/rail boundaries at0V, floating
potentials minimize the positive capacitor-network energy. Solve their KCL with
CG, retaining an a-posteriori energy/residual bracket. No floating electrode is
grounded as an approximation. Zero-wire-R and fixed other-boundary voltages are
explicit diagnostic assumptions; nonlinear device charge is excluded.

If D*y=b and0<=y<=1, Q(x)=Ctt-2*b'x+x'Dx is an upper bound on Ceff.
Q(x)-Ceff=r'(y-x)<=sum(max(r,0)*(1-x)+max(-r,0)*x), r=b-D*x,
for any clipped trial0<=x<=1. The certificate includes conservative IEEE754
coefficient/assembly/matvec/summation bounds; CG convergence is not the proof.
"""
import argparse
from array import array
from collections import Counter
from datetime import datetime,timezone
from functools import lru_cache
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import signal
import sys
import time
import numpy as np
import scipy
from scipy import sparse
from scipy.sparse import csgraph
from scipy.sparse.linalg import cg,LinearOperator
from audit_parent_capacitance_network import value
from check_bbpd_repair_identity import design
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


@lru_cache(maxsize=262144)
def femtofarads(raw):
    c=value(raw)*1e15
    assert math.isfinite(c) and c>0,raw
    return c


def ports(fields):
    kind=fields[0][0]
    if kind in ['M','D','R']:
        return fields[1:5] if kind=='M' else fields[1:3]
    assert kind=='X'
    indices=[i for i,f in enumerate(fields) if f.startswith('sky130_fd_pr__')]
    assert len(indices)==1 and indices[0] in [3,5],fields
    return fields[1:indices[0]]


def build_graph(path,targets,extra_boundaries=(),progress=lambda **fields:None):
    targets=list(targets)
    assert targets and len(set(targets))==len(targets)
    boundary={'0','VGND','VPWR','VSUBS',*extra_boundaries,*targets}
    ids={};order_digest=hashlib.sha256()
    diag=array('d');anchor=array('d');degree=array('I')
    rhs=[array('d') for _ in targets]
    rows=array('I');cols=array('I');weights=array('d')
    direct=[[] for _ in targets];ctt=[[] for _ in targets]
    target_index={name:i for i,name in enumerate(targets)}
    counts=Counter();sums=[];block=[]
    def node(name):
        if name not in ids:
            index=len(ids);assert index<2**32
            ids[name]=index;order_digest.update(name.encode()+b'\0')
            diag.append(0);anchor.append(0);degree.append(0)
            for b in rhs:b.append(0)
        return ids[name]
    with Path(path).open() as stream:
        first=None
        for line in stream:
            if line.startswith('C'):
                first=line;break
            if line[:1] in ['M','D','R','X']:
                boundary.update(ports(line.split()));counts['device_cards']+=1
        assert first is not None
        for line in itertools.chain([first],stream):
            if line[:1] in ['M','D','R','X']:
                raise AssertionError('active device follows capacitor records')
            if not line.startswith('C'):continue
            fields=line.split();a,b=fields[1:3];c=femtofarads(fields[3]);counts['capacitors']+=1
            if a==b:
                counts['self_loops_zero_energy']+=1
                continue
            block.append(c)
            if len(block)==100000:sums.append(math.fsum(block));block.clear()
            ab,bb=a in boundary,b in boundary
            for name,other in [(a,b),(b,a)]:
                if name in target_index:ctt[target_index[name]].append(c)
            if ab and bb:
                counts['boundary_boundary']+=1
                if a in target_index:direct[target_index[a]].append(c)
                if b in target_index:direct[target_index[b]].append(c)
            elif ab or bb:
                fixed,floating=(a,b) if ab else (b,a)
                i=node(floating);diag[i]+=c;anchor[i]+=c;degree[i]+=1
                if fixed in target_index:rhs[target_index[fixed]][i]+=c
                counts['boundary_floating']+=1
            else:
                i,j=node(a),node(b)
                diag[i]+=c;diag[j]+=c;degree[i]+=1;degree[j]+=1
                rows.append(i);cols.append(j);weights.append(c)
                counts['floating_floating']+=1
            if counts['capacitors']%5000000==0:
                progress(capacitors=counts['capacitors'],floating_nodes=len(ids),phase='reading_graph')
    sums.append(math.fsum(block))
    n=len(ids)
    assert n>0 and max(degree)>0
    ii=np.asarray(rows,dtype=np.int32);jj=np.asarray(cols,dtype=np.int32)
    cc=np.asarray(weights,dtype=np.float64)
    diagonal=np.asarray(diag,dtype=np.float64)
    anch=np.asarray(anchor,dtype=np.float64)
    off=sparse.coo_matrix((-cc,(ii,jj)),shape=(n,n)).tocsr()
    matrix=(off+off.T+sparse.diags(diagonal,format='csr')).tocsr()
    del off
    assert matrix.shape==(n,n) and np.all(matrix.diagonal()>0)
    components,labels=csgraph.connected_components(matrix,directed=False)
    anchored=np.bincount(labels,weights=anch,minlength=components)>0
    keep=anchored[labels]
    # Unanchored C-only components have no connection to any active boundary;
    # omitting them changes no port charge and fixes no physical potential.
    reduced=matrix[keep,:][:,keep].tocsr()
    return dict(targets=targets,n=n,matrix=reduced,keep=keep,anchor=anch,rhs=[np.asarray(b) for b in rhs],
        ii=ii,jj=jj,cc=cc,direct=[math.fsum(v) for v in direct],ctt=[math.fsum(v) for v in ctt],
        total_capacitance_ff=math.fsum(sums),maximum_incident_degree=max(degree),counts=dict(counts),
        floating_node_order_sha256=order_digest.hexdigest(),declared_boundaries=len(boundary),
        floating_components=components,unanchored_components=int(np.count_nonzero(~anchored)),
        unanchored_nodes=int(np.count_nonzero(~keep)))


def gamma(n):
    u=float(np.finfo(np.float64).eps)/2
    assert n*u<1
    return n*u/(1-n*u)


def certificate(graph,index,trial):
    x=np.clip(np.asarray(trial,dtype=np.float64),0,1)
    assert len(x)==graph['matrix'].shape[0] and np.all(np.isfinite(x))
    full=np.zeros(graph['n'],dtype=np.float64);full[graph['keep']]=x
    b=graph['rhs'][index]
    delta=full[graph['ii']]-full[graph['jj']]
    ff=math.fsum(graph['cc']*delta*delta)
    ground=np.maximum(graph['anchor']-b,0)
    q=math.fsum([graph['direct'][index],ff,math.fsum(b*(1-full)*(1-full)),math.fsum(ground*full*full)])
    reduced_b=b[graph['keep']]
    residual=reduced_b-graph['matrix'].dot(x)
    l1=math.fsum(np.abs(residual))
    dual=math.fsum(np.maximum(residual,0)*(1-x)+np.maximum(-residual,0)*x)
    k=graph['maximum_incident_degree']
    s=graph['total_capacitance_ff']/(1-gamma(8))
    # Positive summands: diagonal and off-diagonal assembly each contributes
    # at most2*gamma(k)*S; RHS at most gamma(k)*S. CSR dot rows have <=k+1
    # terms. Source decimal-to-binary/scaling error is separately enclosed.
    assembly_residual=5*gamma(k)*s
    matvec_residual=4*(1+gamma(k))*gamma(2*(k+1))*s
    subtraction_residual=gamma(3)*((1+gamma(k))+4*(1+gamma(k))*(1+gamma(2*(k+1))))*s
    underflow=float(64*(graph['matrix'].nnz+graph['n']+1)*np.nextafter(0.,1.))
    residual_round=assembly_residual+matvec_residual+subtraction_residual+underflow
    energy_round=(4*gamma(k)+gamma(8))*s+gamma(8)*q+underflow
    source_round=gamma(8)*s
    dual_upper=dual+gamma(8)*l1+residual_round
    lower=max(0.,q-energy_round-dual_upper-source_round)
    upper=min(graph['ctt'][index]+source_round+gamma(2)*graph['ctt'][index],q+energy_round+source_round)
    assert math.isfinite(lower) and math.isfinite(upper) and 0<=lower<=upper
    return dict(target=graph['targets'][index],wire_capacitance_lower_ff=lower,wire_capacitance_upper_ff=upper,
        interval_width_ff=upper-lower,parsed_incident_diagonal_ff=graph['ctt'][index],trial_energy_ff=q,
        evaluated_residual_l1_ff=l1,maximum_principle_dual_upper_ff=dual_upper,
        floating_point_energy_allowance_ff=energy_round,source_decimal_rounding_allowance_ff=source_round,
        all_trial_floating_potentials_clipped_to_unit_interval=True),full


class SolveBudget(Exception):
    def __init__(self,trial):self.trial=trial


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--positive',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--target',action='append')
    parser.add_argument('--per-target-seconds',type=float,default=600)
    parser.add_argument('--iteration-limit',type=int,default=1200)
    parser.add_argument('--certificate-width-ff',type=float,default=1e-4)
    args=parser.parse_args()
    source=args.positive.resolve();out=args.output.resolve()
    targets=args.target or ['PLLOUT','REFCLK','BBPD_RESET_N']
    assert args.per_target_seconds>0 and args.iteration_limit>0 and args.certificate_width_ff>0
    owner=json.loads((source/'owner.json').read_text());deadline=owner['deadline_uptime']
    left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME);assert left>0
    signal.alarm(max(1,math.floor(left)))
    receipt=verify(source/'assessment.json')
    assert receipt['representation_reduction_exact_for_parsed_network'] and receipt['floating_branches_preserved']
    route=ROOT/'build/timing400/release_001/parent_dco_antenna_targeted_011/route.def'
    _,_,nets=design(route);assert len(nets)==359 and set(targets)<=set(nets)
    network=source/'capacitance_positive.spice'
    paths=[Path(__file__).resolve(),Path(__file__).with_name('audit_parent_capacitance_network.py'),
        source/'assessment.json',source/'owner.json',network,route,Path(np.__file__),Path(scipy.__file__)]
    pins={str(p):sha(p) for p in paths}
    out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(source/'owner.json'),deadline_uptime=deadline,total_budget_restarted=False))
    save(out/'input_manifest.json',dict(input_sha256=pins,numpy_version=np.__version__,scipy_version=scipy.__version__,scope=__doc__))
    def status(**fields):save(out/'status.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False,**fields))
    status(phase='building_lumped_capacitor_graph')
    graph=build_graph(network,targets,nets,progress=status)
    assert graph['counts']['capacitors']==receipt['retained_positive_capacitors']
    matrix=graph['matrix'];inverse=1/matrix.diagonal()
    preconditioner=LinearOperator(matrix.shape,matvec=lambda x:inverse*x,dtype=np.float64)
    results=[]
    for index,target in enumerate(targets):
        iterations=0;until=min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+args.per_target_seconds)
        def callback(x):
            nonlocal iterations
            iterations+=1
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=until:raise SolveBudget(x.copy())
            if iterations%50==0:status(phase='solving_floating_kcl',target=target,iterations=iterations)
        began=time.clock_gettime(time.CLOCK_BOOTTIME)
        try:
            trial,info=cg(matrix,graph['rhs'][index][graph['keep']],M=preconditioner,rtol=1e-10,atol=0,
                maxiter=args.iteration_limit,callback=callback)
        except SolveBudget as error:trial=error.trial;info='per_target_budget'
        result,full=certificate(graph,index,trial)
        result.update(cg_info=info,cg_iterations=iterations,elapsed_seconds=time.clock_gettime(time.CLOCK_BOOTTIME)-began,
            requested_certificate_width_ff=args.certificate_width_ff,
            numerical_width_target_met=result['interval_width_ff']<=args.certificate_width_ff)
        voltage=out/f'trial_{index}.npy';np.save(voltage,full)
        result['trial_potentials_file']=str(voltage)
        results.append(result);save(out/'target_bounds.json',results)
        print(target,result['wire_capacitance_lower_ff'],result['wire_capacitance_upper_ff'],'fF; iterations',iterations,flush=True)
    for p,digest in pins.items():assert sha(p)==digest,p
    graph_metadata={k:graph[k] for k in ['n','total_capacitance_ff','maximum_incident_degree','counts',
        'floating_node_order_sha256','declared_boundaries','floating_components','unanchored_components','unanchored_nodes']}
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name not in ['status.json','owner.json']},
        graph=graph_metadata,targets=results,numpy_version=np.__version__,scipy_version=scipy.__version__,
        all_requested_width_targets_met=all(r['numerical_width_target_met'] for r in results),
        floating_nodes_eliminated_by_zero_incremental_charge_kcl=True,unanchored_components_omitted_with_zero_port_effect=True,
        diagnostic_assumptions=['lumped_zero_wire_resistance','other_active_terminals_and_supplies_fixed_incrementally',
            'positive_linear_extracted_capacitors','IEEE754_binary64_arithmetic','nonlinear_device_charge_excluded'],
        actual_fom_material_enclosure_qualified=False,distributed_rc_qualified=False,
        physical_timing_qualified=False,model_adopted=False,release_qualified=False,scope=__doc__))
    status(phase='terminal_lumped_capacitance_bounds')


if __name__=='__main__':main()
