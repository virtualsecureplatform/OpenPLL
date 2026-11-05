"""Refine a bounded Schur export and guarantee fixed-supply passivity.

The native source is PSD and its floating block has a positive inverse bound.
For symmetric export error E with row sums <= r_i, diag(d)+E is PSD when
 d_i>=r_i. These explicitly numerical shunts retain the total 1e-6 budget.
No floating-charge solve or manufacturing geometry is changed.
"""
import os
if __name__=='__main__':os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse,json,math
from fractions import Fraction as F
from pathlib import Path
import numpy as np
from common_v3 import save,sha,verify
from reduce_prototype_context_floating_C_v1 import prepare
from reduce_prototype_floating_C_v1 import gamma,LD,sparsify
from rebind_prototype_floating_reduction import capacitor_pairs
from bounded_C_diagonal_guard_v2 import coefficient,review as guard_review


def observed_export(s,threshold):
    m=len(s);i,j=np.triu_indices(m,1);wanted=-s[i,j];use=wanted>LD(threshold)
    values_F=np.asarray(wanted[use],dtype=np.float64)*1e-15;values=values_F.astype(LD)*LD(10**15)
    off=np.abs(wanted);off[use]=np.abs(values-wanted[use]);offsum=np.zeros(m,dtype=LD);diagonal=np.zeros(m,dtype=LD)
    np.add.at(offsum,i,off);np.add.at(offsum,j,off);np.add.at(diagonal,i[use],values);np.add.at(diagonal,j[use],values)
    observed=np.abs(diagonal-np.diag(s))+offsum
    observed+=LD(gamma(m+8,float(np.finfo(LD).eps/2)))*(np.abs(diagonal)+offsum+np.abs(np.diag(s)))*8
    return observed


def run(source,products,audited,output,budget):
    receipts=[p/'assessment.json' for p in (source,audited)]
    sr,ar=[json.loads(p.read_text()) for p in receipts]
    for r in (sr,ar):verify(r['input_sha256']);verify(r['artifacts'])
    if not ar['source_inverse_bound_and_model_export_replayed'] or not ar['bounded_complete_context_floating_C_reduction_verified']:
        raise ValueError('completed numerical products and independently replayed export required')
    if not sr['complete_fixed_supply_passivity_certificate_bound']:raise ValueError('PSD native context source required')
    source_proofs=[]
    for p in sr['input_sha256']:
        if p.endswith('/assessment.json'):
            r=json.loads(Path(p).read_text())
            if r.get('complete_context_geometric_operator_passivity_certified'):source_proofs.append((Path(p),r))
    if len(source_proofs)!=1 or not source_proofs[0][1]['rational_allocation_witnesses_independently_replayed']:
        raise ValueError('one independently replayed native context PSD proof required')
    verify(source_proofs[0][1]['input_sha256']);verify(source_proofs[0][1]['artifacts'])
    original=source/'context.spice';metadata_path=source/'nodes.json';bounds=products/'reduction_bounds.json';sfile=products/'energy_boundary_fF.npy'
    if ar['input_sha256'].get(str(original))!=sha(original) or ar['input_sha256'].get(str(bounds))!=sha(bounds) or ar['input_sha256'].get(str(sfile))!=sha(sfile):
        raise ValueError('audited products differ from the requested source')
    dependencies=('reduce_prototype_context_floating_C_v1.py','reduce_prototype_floating_C_v1.py','bounded_C_diagonal_guard_v2.py','rebind_prototype_floating_reduction.py')
    paths=[*receipts,source_proofs[0][0],original,metadata_path,bounds,sfile,products/'grounded_paths.json',audited/'reviewed_numerical_bounds.json',Path(__file__).resolve(),*[Path(__file__).with_name(n) for n in dependencies]]
    pins={str(p):sha(p) for p in paths}
    old=json.loads(bounds.read_text());metadata=json.loads(metadata_path.read_text());text=original.read_text()
    floats,boundaries,ff,fb,base,groups,stats=prepare(text,sr['top'],metadata['capacitor_only_nodes'])
    if boundaries!=old['row_node_names']:raise ValueError('numerical boundary order differs')
    s=np.load(sfile);m=len(boundaries)
    if s.shape!=(m,m) or not np.isfinite(s).all():raise ValueError('invalid stored energy matrix')
    observed=observed_export(s,old['attempts'][-1]['threshold_fF'])
    # Recover an upper enclosure of the producer's arithmetic bound A from
    # fl_LD(observed+A). Binary-rational arithmetic includes positive-addition
    # rounding and the source JSON's float conversion.
    digits=np.finfo(LD).nmant+1
    if old['extended_mantissa_bits']!=digits:raise ValueError('source numerical precision differs')
    u=F(1,2**digits);arithmetic=[]
    for total,o in zip(old['row_error_upper_fF'],observed):
        total_up=F.from_float(math.nextafter(float(total),math.inf))
        exact_o=F(*o.as_integer_ratio());a=total_up/(1-u)-exact_o
        if a<0:raise ValueError('replayed producer error decomposition is inconsistent')
        upper=math.nextafter(float(a),math.inf)
        if F.from_float(upper)<a:raise ValueError('arithmetic enclosure rounded downward')
        arithmetic.append(upper)
    arithmetic=np.asarray(arithmetic)
    ii,jj,values,total,scale,attempts=sparsify(s,base,arithmetic,budget*.49)
    # Enclose the new positive addition before sizing guards. Named supplies
    # are fixed, so only dynamic rows need the diagonal PSD compensation.
    errors={}
    scales={}
    for i,node in enumerate(boundaries):
        exact=F(*total[i].as_integer_ratio())/(1-u)
        upper=math.nextafter(float(exact),math.inf)
        errors[node]=F.from_float(upper)
        scales[node]=F.from_float(math.nextafter(float(scale[i]),0.))
    fixed={metadata['original_to_emitted'][n] for n in metadata['original_fixed_supply_nodes'] if n in metadata['original_to_emitted']}|{'0'}
    if set(floats)&fixed:raise ValueError('a fixed supply was included in the eliminated subspace')
    guards={};lower_guards={};guard_cards=[];detail=[]
    for node in boundaries:
        if node in fixed:continue
        spelling,decimal_value=coefficient(errors[node]);binary_value=F.from_float(float(spelling))
        minimum,maximum=min(decimal_value,binary_value),max(decimal_value,binary_value)
        if minimum*10**15<errors[node]:raise ValueError('emitted decimal/binary guard insufficient')
        guards[node]=maximum;lower_guards[node]=minimum
        guard_cards.append('CkronGuard'+str(len(guard_cards))+' '+node+' 0 '+spelling)
        detail.append(dict(node=node,error_upper_fF=str(errors[node]),reference_scale_lower_fF=str(scales[node]),
            emitted_capacitance_F=spelling,coefficient_lower_F=str(minimum),coefficient_upper_F=str(maximum)))
    # Check both dominance and final error with exact fractions. The lower
    # coefficient proves PSD; the upper coefficient bounds model departure.
    guard_review(errors,scales,lower_guards,fixed,F(str(budget)))
    theorem=guard_review(errors,scales,guards,fixed,F(str(budget)))
    floating=set(floats);lines=[]
    kron=['Ckron'+str(k)+' '+boundaries[int(a)]+' '+boundaries[int(b)]+' '+format(float(c),'.17e') for k,(a,b,c) in enumerate(zip(ii,jj,values))]
    for line in text.splitlines():
        f=line.split()
        if f and f[0].startswith('Cflat') and (f[1] in floating or f[2] in floating):continue
        if f and f[0].lower()=='.ends':lines.extend(kron);lines.extend(guard_cards)
        lines.append(line)
    model='\n'.join(lines)+'\n'
    if [l for l in text.splitlines() if l.startswith(('Xflat','Rwire'))]!=[l for l in model.splitlines() if l.startswith(('Xflat','Rwire'))]:raise ValueError('active primitive or port alias changed')
    # Independent capacitor-card reparse includes the CkronGuard records.
    parsed_pairs=capacitor_pairs(model)
    parsed_guards=capacitor_pairs('\n'.join(guard_cards))
    for node,minimum in lower_guards.items():
        if parsed_guards.get(tuple(sorted((node,'0'))),F())<minimum:raise ValueError('numerical guard absent after capacitor reparse')
    verify(pins);output.mkdir(parents=True,exist_ok=False)
    target=output/'context.spice';target.write_text(model)
    save(output/'guards.json',detail)
    save(output/'passivity_certificate.json',dict(method=__doc__,source_native_PSD_certificate=str(source_proofs[0][0]),
        source_native_PSD_certificate_sha256=sha(source_proofs[0][0]),floating_block_positive_inverse_certificate=str(products/'grounded_paths.json'),
        source_and_export_error_enclosures_verified=True,guard_coefficients_dominate_dynamic_symmetric_row_errors=True,
        fixed_supply_projection_commutes_with_floating_elimination=True,**theorem))
    save(output/'numerical_bounds.json',dict(relative_row_error_budget=budget,maximum_normalized_final_row_error=theorem['maximum_normalized_final_row_error'],
        sparse_attempts=attempts,maximum_recovered_arithmetic_row_bound_fF=float(arithmetic.max()),
        numerical_guard_capacitors=len(guards),maximum_guard_capacitance_F=str(max(guards.values(),default=F())),
        total_guard_capacitance_F=str(sum(guards.values(),F())),row_bounds_and_guards=detail))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in output.iterdir()},
        assembled_candidate_gds_sha256=sr['assembled_candidate_gds_sha256'],top=sr['top'],
        bounded_complete_context_floating_C_reduction_verified=True,complete_reduced_fixed_supply_C_passivity_certified=True,
        passivity_method='source Schur PSD plus exact symmetric-row-error diagonal domination',
        eliminated_capacitor_only_nodes=len(floats),retained_boundary_nodes=m,capacitor_only_components=len(groups),
        all_active_primitive_and_port_alias_cards_unchanged=True,actual_supply_terminal_identity_preserved=True,
        numerical_guard_capacitors_explicitly_added=True,numerical_guards_included_in_error_budget=True,
        maximum_normalized_final_row_error=theorem['maximum_normalized_final_row_error'],relative_row_error_budget=budget,
        floating_charge_solve_reexecuted=False,numerical_reduction_with_explicit_error_bound=True,exact_full_operator_identity_claimed=False,
        domain_partition_performed=False,domain_stimuli_supplied=False,distributed_wire_R_added=False,
        FOM_fill_electrical_coverage_complete=False,neighborhood_convergence_verified=False,
        loaded_native_model_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','products','audited','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--relative-row-error',type=float,default=1e-6);a=p.parse_args()
    if not 0<a.relative_row_error<=1e-6:p.error('total error budget must remain at most 1e-6')
    run(a.source.resolve(),a.products.resolve(),a.audited.resolve(),a.output.resolve(),a.relative_row_error)
