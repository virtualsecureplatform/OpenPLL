#!/usr/bin/env python3
"""Bound all nonterminal RC states without a resistor-degree restriction.

Keep every device terminal and physical point port. Include branching mesh
vertices as well as paths. Use the actual native-formula nominal R export,
rather than the earlier rounded branch ledger. For grounded internal conductance
Gii and Cii, Gii^-1 is nonnegative and

  rho(Gii^-1 Cii) <= ||Gii^-1 abs(Cii)||_inf.

This analysis computes that bound and counts conservative fast subsets. Removing
slow vertices from the candidate set only decreases this positive comparison
bound. No state is removed, and no oscillator-frequency error is inferred.
"""
from collections import Counter
import json
import os
from pathlib import Path
import signal
import time
import numpy as np
from scipy.sparse import coo_matrix,load_npz
from scipy.sparse.linalg import splu
from compile_local_C_operators_v2 import digest,save


def main():
    base=Path(__file__).resolve().parents[2]/'build/timing400/release_001'
    owner=base/'distributed_RC_model_qualification_001/owner.json'
    deadline=json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    signal.alarm(max(1,int(deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    family=base/'DCO_complete_domain_model_primitives_001'
    matrix=base/'DCO_local_C_matrix_nom_no_substrate_G_001'
    check=base/'DCO_local_C_matrix_nom_no_substrate_G_checks_001/assessment.json'
    assert json.loads(check.read_text())['signed_global_passivity_numerical_check_passed']
    names=json.loads((matrix/'nodes.json').read_text())
    lookup={n:i for i,n in enumerate(names)}
    devices_path=family/'device_connections.json'
    terminal={n for r in json.loads(devices_path.read_text()).values() for n in r['private_terminals']}
    boundary=base/'DCO_direct_native_planes_and_boundaries_001/boundary_connections.json'
    terminal.update(r['private_node'] for r in json.loads(boundary.read_text()))
    terminal.add('_dco_substrate_reference')
    degree=Counter()
    rr,cc,vv=[],[],[]
    rfolder=base/'DCO_domain_R_corners_002'
    rproof=rfolder/'assessment.json'
    assert json.loads(rproof.read_text())['all166286_nominal_values_reproduce_native_float32_formulas_exactly']
    rsource=rfolder/'nom_wire_R_unqualified.spice'
    branch_count=0
    for text in rsource.open():
        words=text.split()
        if not words or words[0].startswith('*'):continue
        assert len(words)==4 and words[0].upper().startswith('R')
        _,a,b,value=words
        ia,ib=lookup[a],lookup[b]
        degree[a]+=1
        degree[b]+=1
        g=1./float(value)
        assert g>0 and np.isfinite(g)
        rr.extend([ia,ib,ia,ib]);cc.extend([ia,ib,ib,ia]);vv.extend([g,g,-g,-g])
        branch_count+=1
    assert branch_count==166286
    indices=np.array([i for i,n in enumerate(names) if n not in terminal and degree[n]>=1],dtype=np.int64)
    assert len(indices)>0
    out=base/'DCO_all_internal_R_node_analysis_001'
    out.mkdir(exist_ok=False)
    save(out/'status.json',dict(state='factoring_all_nonterminal_internal_R_vertices',runner_pid=os.getpid(),
        candidate_states=len(indices),deadline_uptime=deadline))
    G=coo_matrix((vv,(rr,cc)),shape=(len(names),len(names))).tocsr()
    Gii=G[indices][:,indices].tocsc()
    C=load_npz(matrix/'C_native_units.npz').tocsr()*1e-18
    mass=np.asarray(abs(C[indices][:,indices]).sum(axis=1)).ravel()
    factor=splu(Gii)
    bound=factor.solve(mass)
    residual=Gii@bound-mass
    relative=float(max(abs(residual))/max(max(abs(mass)),1e-300))
    assert np.isfinite(bound).all() and min(bound)>=-1e-12*max(bound) and relative<1e-8
    limits=[1e-17,1e-16,1e-15,1e-14,1e-13,1e-12]
    counts={str(limit):int(np.count_nonzero(bound<=limit)) for limit in limits}
    nodes={r['private_id']:r for r in json.loads((family/'nodes.json').read_text())}
    worst=np.argsort(bound)[-20:][::-1]
    details=[dict(node=names[indices[i]],comparison_time_constant_s=float(bound[i]),
        R_degree=degree[names[indices[i]]],geometry=nodes[names[indices[i]]]) for i in worst]
    np.savez(out/'candidate_comparison_bounds.npz',node_indices=indices,upper_bounds_s=bound)
    save(out/'largest_comparison_bounds.json',details)
    inputs=[Path(__file__).resolve(),owner,check,matrix/'nodes.json',matrix/'C_native_units.npz',
        family/'nodes.json',rsource,rproof,devices_path,boundary]
    result=dict(candidate_nonterminal_states=len(indices),retained_device_and_point_vertices=len(terminal),
        degree_restriction_applied=False,native_formula_R_branches=branch_count,
        candidate_counts_by_R_degree={str(k):sum(degree[names[i]]==k for i in indices) for k in sorted(set(degree[names[i]] for i in indices))},
        maximum_internal_time_constant_comparison_bound_s=float(max(bound)),
        conservative_fast_subset_counts_by_time_constant_s=counts,
        grounded_R_linear_solve_relative_residual=relative,
        independent_state_or_network_changed=False,oscillator_frequency_error_qualified=False,
        finite_R_model_condensation_qualified=False,runtime_model_eligible=False,release_qualified=False,adopted=False,
        deadline_uptime=deadline,input_sha256={str(p.resolve()):digest(p) for p in inputs},
        artifacts={str(p.resolve()):digest(p) for p in [out/'candidate_comparison_bounds.npz',out/'largest_comparison_bounds.json']})
    save(out/'assessment.json',result)
    save(out/'status.json',dict(state='completed',candidate_states=len(indices)))
    print(json.dumps({k:v for k,v in result.items() if k not in ['input_sha256','artifacts']},indent=2))


if __name__=='__main__':main()
