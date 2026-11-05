"""Resume the failed certificate review without repeating a floating-charge solve.

Audit source identity, primitive/C export bytes and stored numerical products;
then run a new exact passivity certificate. Numerical kernel products are reused,
not claimed to have been independently recomputed by this review.
"""
import os
if __name__=='__main__':os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse,json,shutil
from pathlib import Path
import numpy as np
from common_v3 import save,sha,verify
from reduce_prototype_context_floating_C_v1 import prepare
from reduce_prototype_floating_C_v1 import inverse_certificate,LD
from rebind_prototype_floating_reduction import capacitor_pairs
from project_prototype_fixed_rail_C_v2 import project
from certify_prototype_parallel_C_paths_v2 import certificate,replay


def run(source,products,launch,output):
    sr=source/'assessment.json';r=json.loads(sr.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    origin=launch/'launch.json';o=json.loads(origin.read_text());verify(o['input_sha256'])
    state=json.loads((launch/'status.json').read_text())['state'];log=launch/'worker.log'
    if state!='stopped_without_qualification' or 'Exceeds the limit (4300 digits)' not in log.read_text():raise ValueError('only the recorded integer-reporting failure is resumable here')
    if not r['complete_native_C_operator_identity_independently_reparsed'] or not r['complete_fixed_supply_passivity_certificate_bound']:
        raise ValueError('complete certified native context reference required')
    original=source/'context.spice';candidate=products/'context.spice';nodes=source/'nodes.json';bounds=products/'reduction_bounds.json';inventory=products/'node_inventory.json';sfile=products/'energy_boundary_fF.npy'
    dependencies=('reduce_prototype_context_floating_C_v1.py','reduce_prototype_floating_C_v1.py','certify_prototype_parallel_C_paths_v2.py','project_prototype_fixed_rail_C_v2.py','rebind_prototype_floating_reduction.py')
    paths=[sr,origin,launch/'status.json',log,original,candidate,nodes,bounds,inventory,sfile,products/'grounded_paths.json',products/'harmonic_basis.f64',products/'residual.f64',products/'boundary_product.ld',products/'cholmod_bridge.so',Path(__file__).resolve(),*[Path(__file__).with_name(n) for n in dependencies]]
    pins={str(p):sha(p) for p in paths}
    metadata=json.loads(nodes.read_text());old=json.loads(bounds.read_text());saved=json.loads(inventory.read_text());text=original.read_text();target=candidate.read_text()
    floats,boundaries,ff,fb,base,groups,stats=prepare(text,r['top'],metadata['capacitor_only_nodes'])
    if floats!=saved['floating_nodes'] or boundaries!=saved['retained_boundaries']:raise ValueError('stored numerical subspace differs from source')
    paths_proof,_=inverse_certificate(len(floats),ff,fb)
    if paths_proof!=json.loads((products/'grounded_paths.json').read_text()):raise ValueError('positive inverse certificate differs from source')
    n,m=len(floats),len(boundaries)
    for filename,size in (('harmonic_basis.f64',n*m*8),('residual.f64',n*m*8),('boundary_product.ld',m*m*np.dtype(LD).itemsize)):
        if (products/filename).stat().st_size!=size:raise ValueError('stored numerical product shape differs')
    h=np.memmap(products/'harmonic_basis.f64',dtype=np.float64,mode='r',shape=(n,m))
    if not np.isfinite(h).all() or h.min() < -1e-8 or h.max()>1+1e-8:raise ValueError('invalid harmonic extension')
    s=np.load(sfile)
    if s.shape!=(m,m) or not np.isfinite(s).all():raise ValueError('invalid stored energy operator')
    if not old['positive_path_inverse_bound_used'] or not 0<old['relative_row_tolerance']<=1e-6:raise ValueError('bounded numerical certificate required')
    row=np.nextafter(np.asarray(old['row_error_upper_fF']),np.inf)
    scale=np.nextafter(np.asarray(old['row_reference_scale_fF']),0.)
    if len(row)!=m or len(scale)!=m or not np.isfinite(row).all() or not np.isfinite(scale).all() or np.any(row<0) or np.any(scale<=0):raise ValueError('invalid source coefficient row bounds')
    relative=float(np.max(row/scale))
    if relative>old['relative_row_tolerance']:raise ValueError('stored numerical bound exceeds budget')
    ii,jj=np.triu_indices(m,1);wanted=-s[ii,jj];threshold=LD(old['attempts'][-1]['threshold_fF']);use=wanted>threshold
    values=np.asarray(wanted[use],dtype=np.float64)*1e-15
    kron=['Ckron'+str(k)+' '+boundaries[int(a)]+' '+boundaries[int(b)]+' '+format(float(c),'.17e') for k,(a,b,c) in enumerate(zip(ii[use],jj[use],values))]
    floating=set(floats);expected=[]
    for line in text.splitlines():
        f=line.split()
        if f and f[0].startswith('Cflat') and (f[1] in floating or f[2] in floating):continue
        if f and f[0].lower()=='.ends':expected.extend(kron)
        expected.append(line)
    if '\n'.join(expected)+'\n'!=target:raise ValueError('candidate export differs from source and stored energy operator')
    matrix=np.zeros((m,m),dtype=LD);ids={node:i for i,node in enumerate(boundaries)}
    for line in kron:
        f=line.split();a,b=ids[f[1]],ids[f[2]];c=LD(f[3])*LD(10**15)
        matrix[a,a]+=c;matrix[b,b]+=c;matrix[a,b]-=c;matrix[b,a]-=c
    observed=np.sum(np.abs(matrix-s),axis=1,dtype=LD)
    if np.any(observed>row.astype(LD)):raise ValueError('independent export row error exceeds stored numerical bound')
    fixed={metadata['original_to_emitted'][name] for name in metadata['original_fixed_supply_nodes'] if name in metadata['original_to_emitted']}|{'0'}
    dynamic=project(capacitor_pairs(target),fixed)
    output.mkdir(parents=True,exist_ok=False)
    save(output/'status.json',dict(state='recertifying_completed_context_operator',release_ready=False))
    proof=certificate(dynamic);checked=replay(dynamic,proof) if proof['passivity_certified'] else None
    save(output/'fixed_rail_passivity.json',proof)
    save(output/'reviewed_numerical_bounds.json',dict(source_bound_receipt=str(bounds),row_node_names=boundaries,row_error_upper_fF=list(map(float,row)),row_reference_scale_lower_fF=list(map(float,scale)),maximum_normalized_row_error=relative,relative_row_error_budget=old['relative_row_tolerance'],coefficient_export_independently_replayed=True,numerical_kernel_products_independently_recomputed=False))
    verify(pins);shutil.copyfile(candidate,output/'context.spice')
    if sha(output/'context.spice')!=pins[str(candidate)]:raise ValueError('completed model bytes changed during copy')
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in output.iterdir() if p.name not in ('assessment.json','status.json')},
        assembled_candidate_gds_sha256=r['assembled_candidate_gds_sha256'],top=r['top'],
        completed_numerical_products_reused_after_certificate_reporting_failure=True,floating_charge_kernel_reexecuted=False,
        source_inverse_bound_and_model_export_replayed=True,numerical_kernel_products_independently_recomputed=False,
        bounded_complete_context_floating_C_reduction_verified=True,eliminated_capacitor_only_nodes=n,retained_boundary_nodes=m,capacitor_only_components=len(groups),
        all_active_primitive_and_port_alias_cards_unchanged=True,actual_supply_terminal_identity_preserved=True,
        complete_reduced_fixed_supply_C_passivity_certified=proof['passivity_certified'],rational_passivity_witnesses_independently_replayed=checked is not None,
        maximum_normalized_row_error=relative,relative_row_error_budget=old['relative_row_tolerance'],
        numerical_reduction_with_explicit_error_bound=True,exact_full_operator_identity_claimed=False,
        domain_partition_performed=False,domain_stimuli_supplied=False,distributed_wire_R_added=False,
        FOM_fill_electrical_coverage_complete=False,neighborhood_convergence_verified=False,loaded_native_model_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='complete_reduced_context_passive_domain_models_pending' if checked else 'reduced_context_sufficient_certificate_inconclusive',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','products','launch','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.products.resolve(),a.launch.resolve(),a.output.resolve())
