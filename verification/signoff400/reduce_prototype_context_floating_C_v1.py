"""Bounded floating-charge reduction of the complete context-matched reference.

Reuses the controlled numerical kernel while retaining both floating components,
all active terminals and actual supply incidence. Recertifies the complete
fixed-supply operator after export. Does not partition or simulate a domain.
"""
import os
if __name__=='__main__':os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse
import json
from fractions import Fraction as F
from pathlib import Path
import time
import numpy as np
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge_v2 import execute
from inventory_prototype_floating_C_components import components
from prepare_prototype_analog_reference import subcircuits
from project_prototype_fixed_rail_C_v2 import project
from rebind_prototype_floating_reduction import capacitor_pairs
from certify_prototype_parallel_C_paths import certificate,replay
from reduce_prototype_floating_C_v1 import Bridge,coefficient,inverse_certificate,solve,error_bounds,sparsify,LD


def prepare(text,top,expected):
    groups,stats=components(text,top)
    if not groups or any(g['negative_incident_capacitors'] for g in groups):raise ValueError('positive capacitor-only components required')
    floats=sorted(n for g in groups for n in g['nodes'])
    if set(floats)!=set(expected) or len(floats)!=len(expected):raise ValueError('floating subspace differs from the complete context inventory')
    boundaries=sorted({n for g in groups for n in g['boundaries']});fi={n:i for i,n in enumerate(floats)};bi={n:i for i,n in enumerate(boundaries)}
    ff=[];fb=[];base=np.zeros(len(boundaries),dtype=LD)
    for line in text.splitlines():
        f=line.split()
        if not f or not f[0].startswith('Cflat'):continue
        a,b=f[1:3]
        if a not in fi and b not in fi:
            for n in (a,b):
                if n in bi:base[bi[n]]+=abs(LD(f[3])*LD(10**15))
            continue
        value,extended,lower=coefficient(f[3])
        if a in fi and b in fi:ff.append((fi[a],fi[b],value,extended,lower))
        else:
            if b in fi:a,b=b,a
            if b not in bi:raise ValueError('unregistered retained boundary')
            fb.append((fi[a],bi[b],value,extended,lower))
    def arrays(rows):return (np.array([r[0] for r in rows],dtype=np.int32),np.array([r[1] for r in rows],dtype=np.int32),np.array([r[2] for r in rows],dtype=np.float64),np.array([r[3] for r in rows],dtype=LD),np.array([r[4] for r in rows],dtype=np.float64))
    return floats,boundaries,arrays(ff),arrays(fb),base,groups,stats


def run(source,output,threads,relative,owner):
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    for key in ('complete_native_C_operator_identity_independently_reparsed','all_primitive_cards_and_named_ports_independently_reparsed','complete_fixed_supply_passivity_certificate_bound','actual_supply_capacitor_incidence_preserved'):
        if not r.get(key):raise ValueError('complete context reference proof missing: '+key)
    if r['unprojected_negative_pairs_incident_to_floating_nodes']:raise ValueError('positive floating-block method is not applicable')
    deadline=json.loads(owner.read_text())['deadline_uptime']
    if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('original checkpoint deadline expired')
    model=source/'context.spice';nodes=source/'nodes.json';metadata=json.loads(nodes.read_text())
    text=model.read_text();blocks=subcircuits(text)
    if set(blocks)!={r['top']}:raise ValueError('one complete flat context required')
    output.mkdir(parents=True,exist_ok=False)
    save(output/'status.json',dict(state='preparing_complete_context_floating_operator',release_ready=False))
    inputs={str(p):sha(p) for p in (receipt,model,nodes,owner,Path(__file__).resolve(),ROOT/'verification/signoff400/reduce_prototype_floating_C_v1.py',ROOT/'tools/floating_schur/cholmod_bridge.cpp',ROOT/'verification/signoff400/certify_prototype_parallel_C_paths.py',ROOT/'verification/signoff400/inventory_prototype_floating_C_components.py',ROOT/'verification/signoff400/project_prototype_fixed_rail_C_v2.py')}
    floats,boundaries,ff,fb,base,groups,stats=prepare(text,r['top'],metadata['capacitor_only_nodes']);n=len(floats);m=len(boundaries)
    save(output/'node_inventory.json',dict(floating_nodes=floats,retained_boundaries=boundaries,components=[dict(nodes=len(g['nodes']),boundaries=len(g['boundaries'])) for g in groups],**stats))
    path_proof,inverse=inverse_certificate(n,ff,fb);save(output/'grounded_paths.json',path_proof)
    binary=output/'cholmod_bridge.so';cpp=ROOT/'tools/floating_schur/cholmod_bridge.cpp'
    execute(['g++','-std=c++20','-O3','-fPIC','-shared','-fopenmp','-fno-fast-math','-ffp-contract=off','-I/usr/include/suitesparse',cpp,'-lcholmod','-o',binary],output/'build.log',deadline,4)
    inputs[str(binary)]=sha(binary)
    bridge=Bridge(binary);save(output/'status.json',dict(state='solving_complete_context_floating_charge',release_ready=False))
    h,residual,q,norm=solve(bridge,ff,fb,n,m,threads,output)
    bound,details=error_bounds(h,residual,norm,ff,fb,inverse,bridge.digits)
    correction=h.T@residual
    weight=np.zeros(m,dtype=LD);np.add.at(weight,fb[1],fb[3])
    s=-(q+q.T)/2+(correction.astype(LD)+correction.T.astype(LD))/2;s[np.diag_indices(m)]+=weight
    if not np.isfinite(s).all():raise ValueError('nonfinite energy congruence')
    np.save(output/'energy_boundary_fF.npy',s)
    ii,jj,values,total,scale,attempts=sparsify(s,base,bound,relative)
    floating_set=set(floats);lines=[]
    for line in text.splitlines():
        f=line.split()
        if f and f[0].startswith('Cflat') and (f[1] in floating_set or f[2] in floating_set):continue
        if f and f[0].lower()=='.ends':lines.extend('Ckron'+str(k)+' '+boundaries[int(a)]+' '+boundaries[int(b)]+' '+format(float(c),'.17e') for k,(a,b,c) in enumerate(zip(ii,jj,values)))
        lines.append(line)
    reduced='\n'.join(lines)+'\n';target=output/'context.spice';target.write_text(reduced)
    if [l for l in text.splitlines() if l.startswith(('Xflat','Rwire'))]!=[l for l in reduced.splitlines() if l.startswith(('Xflat','Rwire'))]:raise ValueError('active primitive or alias cards changed')
    fixed={metadata['original_to_emitted'][n] for n in metadata['original_fixed_supply_nodes'] if n in metadata['original_to_emitted']}|{'0'}
    dynamic=project(capacitor_pairs(reduced),fixed)
    save(output/'reduction_bounds.json',dict(**details,relative_row_tolerance=relative,attempts=attempts,maximum_normalized_row_error=float(np.max(total/scale)),row_node_names=boundaries,row_error_upper_fF=list(map(float,total)),row_reference_scale_fF=list(map(float,scale))))
    save(output/'status.json',dict(state='recertifying_complete_reduced_context',release_ready=False))
    proof=certificate(dynamic);checked=replay(dynamic,proof) if proof['passivity_certified'] else None
    save(output/'fixed_rail_passivity.json',proof)
    if checked is None:raise ValueError('exported reduced context lacks a complete passivity certificate')
    verify(inputs)
    save(output/'assessment.json',dict(input_sha256=inputs,artifacts={str(p):sha(p) for p in output.iterdir() if p.is_file() and p.name not in ('assessment.json','status.json')},
        assembled_candidate_gds_sha256=r['assembled_candidate_gds_sha256'],top=r['top'],
        bounded_complete_context_floating_C_reduction_verified=True,eliminated_capacitor_only_nodes=n,retained_boundary_nodes=m,
        capacitor_only_components=len(groups),all_active_primitive_and_port_alias_cards_unchanged=True,
        actual_supply_terminal_identity_preserved=True,supply_capacitor_currents_retained_within_reduction_error=True,
        complete_reduced_fixed_supply_C_passivity_certified=True,
        rational_passivity_witnesses_independently_replayed=True,maximum_normalized_row_error=float(np.max(total/scale)),relative_row_error_budget=relative,
        numerical_reduction_with_explicit_error_bound=True,exact_full_operator_identity_claimed=False,
        domain_partition_performed=False,domain_stimuli_supplied=False,distributed_wire_R_added=False,
        FOM_fill_electrical_coverage_complete=False,neighborhood_convergence_verified=False,
        loaded_native_model_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='bounded_complete_context_reduction_complete_domain_models_pending',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','output','deadline-owner'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--threads',type=int,default=8);p.add_argument('--relative-row-tolerance',type=float,default=1e-6);a=p.parse_args()
    if not 1<=a.threads<=16 or not 0<a.relative_row_tolerance<=1e-5:p.error('bounded resources and numerical tolerance required')
    deadline=json.loads(a.deadline_owner.read_text())['deadline_uptime']
    os.environ.update(OMP_NUM_THREADS=str(a.threads),OMP_THREAD_LIMIT=str(a.threads),OPENBLAS_NUM_THREADS='1')
    with lease(a.threads,48,deadline):run(a.source.resolve(),a.output.resolve(),a.threads,a.relative_row_tolerance,a.deadline_owner.resolve())
