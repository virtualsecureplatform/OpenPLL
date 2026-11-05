#!/usr/bin/env python3
"""Build a protected-terminal, numerical DC-equivalent mesh prototype.

Use only the precomputed fast subset, recompute its internal time-constant
comparison bound, retain all device/interface nodes, and project C by congruence.
No native circuit is started or selected and no oscillator error is qualified.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import time
import numpy as np
from scipy.sparse import coo_matrix,load_npz,save_npz
from scipy.sparse.linalg import splu
from passive_RC_condensation import conductance
from passive_RC_mesh_condensation import harmonic_mesh
from compile_local_C_operators_v2 import digest,save


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tau-fs',type=float,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert np.isfinite(args.tau_fs) and args.tau_fs>0
    base=Path(__file__).resolve().parents[2]/'build/timing400/release_001'
    owner=base/'distributed_RC_model_qualification_001/owner.json'
    deadline=json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    signal.alarm(max(1,int(deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    controls=base/'passive_RC_mesh_controls_001/assessment.json'
    assert json.loads(controls.read_text())['independent_rational_branching_RC_controls_passed']
    assert json.loads(controls.read_text())['signed_quadratic_energy_controls_passed']
    matrix=base/'DCO_local_C_matrix_nom_no_substrate_G_001'
    matrix_check=base/'DCO_local_C_matrix_nom_no_substrate_G_checks_001/assessment.json'
    assert json.loads(matrix_check.read_text())['signed_global_passivity_numerical_check_passed']
    analysis=base/'DCO_adaptive_fast_internal_R_selection_nom_1fs_002'
    family=base/'DCO_complete_domain_model_primitives_001'
    names=json.loads((matrix/'nodes.json').read_text());index={n:i for i,n in enumerate(names)}
    original={r['private_id']:r['original_conductor'] for r in json.loads((family/'nodes.json').read_text())}
    original['_dco_substrate_reference']='VGND'
    devices=family/'device_connections.json'
    boundary=base/'DCO_direct_native_planes_and_boundaries_001/boundary_connections.json'
    protected={index[n] for r in json.loads(devices.read_text()).values() for n in r['private_terminals']}
    protected.update(index[r['private_node']] for r in json.loads(boundary.read_text()))
    protected.add(0)
    assert json.loads((analysis/'assessment.json').read_text())['selection_converged']
    bounds=np.load(analysis/'selected_comparison_bounds.npz')
    tau_limit=args.tau_fs*1e-15
    removed=bounds['node_indices'][bounds['upper_bounds_s']<=tau_limit*(1-1e-10)]
    assert len(removed)>0 and not set(map(int,removed)) & protected
    branches=[]
    rsource=base/'DCO_domain_R_corners_002/nom_wire_R_unqualified.spice'
    for text in rsource.open():
        words=text.split()
        if not words or words[0].startswith('*'):continue
        assert len(words)==4 and words[0].startswith('R')
        _,a,b,r=words
        assert original[a]==original[b]
        branches.append((index[a],index[b],r))
    assert len(branches)==166286
    args.output.mkdir(exist_ok=False)
    def status(state,**more):
        save(args.output/'status.json',dict(state=state,runner_pid=os.getpid(),deadline_uptime=deadline,**more))
    status('building_general_R_mesh_projection',removed_states=len(removed))
    T,kept,reduced_R,provenance=harmonic_mesh(len(names),branches,removed,protected)
    assert set(protected)<=set(map(int,kept)) and kept[0]==0
    for i in removed:
        targets=T.indices[T.indptr[i]:T.indptr[i+1]]
        assert all(original[names[i]]==original[names[kept[j]]] for j in targets)
    G=conductance(len(names),branches)
    Gr=conductance(len(kept),reduced_R)
    projected_G=(T.T@G@T).tocsr()
    delta_G=Gr-projected_G
    G_scale=np.maximum(np.asarray(abs(Gr).sum(axis=1)).ravel(),1e-30)
    relative_G=float(max(np.asarray(abs(delta_G).sum(axis=1)).ravel()/G_scale))
    assert relative_G<1e-10,relative_G
    C=load_npz(matrix/'C_native_units.npz').tocsr()
    Gii=G[removed][:,removed].tocsc()
    Wii=T[removed]
    harmonic_residual=Gii@Wii+G[removed][:,kept]
    scale=np.asarray(abs(G[removed]).sum(axis=1)).ravel()
    harmonic_error=float(max(np.asarray(abs(harmonic_residual).sum(axis=1)).ravel()/scale))
    assert harmonic_error<1e-11,harmonic_error
    Cii=C[removed][:,removed]*1e-18
    mass=np.asarray(abs(Cii).sum(axis=1)).ravel()
    comparison=splu(Gii).solve(mass)
    assert min(comparison)>=-1e-12*max(comparison)
    tau=float(max(comparison));assert tau<=tau_limit*(1+1e-9),(tau,tau_limit)
    status('projecting_complete_C_energy',retained_states=len(kept),internal_comparison_bound_s=tau)
    projected_C=(T.T@C@T).tocsr()
    antisymmetric=projected_C-projected_C.T
    absolute_projection=(abs(T).T@abs(C)@abs(T)).tocsr()
    contribution_scale=np.maximum(np.asarray(absolute_projection.sum(axis=1)).ravel(),1e-30)
    antisymmetry=float(max(np.asarray(abs(antisymmetric).sum(axis=1)).ravel()/contribution_scale))
    assert antisymmetry<1e-12
    # Average only symmetric roundoff, never voltage fields or physical energy.
    Cr=((projected_C+projected_C.T)*.5).tocsr();Cr.eliminate_zeros()
    charge=float(max(abs(np.asarray(Cr.sum(axis=1)).ravel())/contribution_scale))
    assert charge<1e-10,charge
    conductors=sorted(set(original.values()));net_index={n:i for i,n in enumerate(conductors)}
    def collapse(ns):
        return coo_matrix((np.ones(len(ns)),([net_index[original[n]] for n in ns],np.arange(len(ns)))),
            shape=(len(conductors),len(ns))).tocsr()
    A=collapse(names);B=collapse([names[i] for i in kept])
    old_collapsed=(A@C@A.T).tocsr();new_collapsed=(B@Cr@B.T).tocsr()
    error=new_collapsed-old_collapsed
    collapse_error=max(abs(error.data),default=0.)
    collapse_scale=max(abs(old_collapsed.data),default=1.)
    assert collapse_error<1e-10*collapse_scale,(collapse_error,collapse_scale)
    save_npz(args.output/'projection_T.npz',T)
    save_npz(args.output/'C_native_units.npz',Cr)
    save_npz(args.output/'G_S.npz',Gr)
    np.savez(args.output/'selection_and_bound.npz',kept_indices=kept,removed_indices=removed,comparison_bound_s=comparison)
    save(args.output/'nodes.json',[names[i] for i in kept])
    save(args.output/'R_mesh_provenance.json',provenance)
    with (args.output/'equivalent_R_unqualified.spice').open('x') as stream:
        stream.write('* Numerically DC-equivalent condensed R mesh; dynamic reduction is not qualified.\n')
        for i,(a,b,r) in enumerate(reduced_R,1):stream.write(f'RCMESH_{i} {names[kept[a]]} {names[kept[b]]} {r}\n')
    inputs=[Path(__file__).resolve(),Path(__file__).with_name('passive_RC_condensation.py'),
        Path(__file__).with_name('passive_RC_mesh_condensation.py'),owner,controls,matrix_check,
        matrix/'nodes.json',matrix/'C_native_units.npz',analysis/'assessment.json',analysis/'selected_comparison_bounds.npz',
        family/'nodes.json',rsource,devices,boundary]
    artifacts=[p for p in args.output.iterdir() if p.is_file() and p.name!='status.json']
    result=dict(passive_mesh_condensation_prototype_built=True,source_full_states=len(names),retained_states=len(kept),
        removed_states=len(removed),protected_device_and_point_vertices=len(protected),all_protected_vertices_retained=True,
        original_R_branches=len(branches),condensed_R_branches=len(reduced_R),all_equivalent_R_positive=True,
        source_C_nonzeros=C.nnz,projected_C_nonzeros=Cr.nnz,projected_C_scalar_branches=int((Cr.nnz-np.count_nonzero(Cr.diagonal()))//2),
        selected_tau_limit_s=tau_limit,recomputed_internal_time_constant_comparison_bound_s=tau,
        DC_harmonic_projection_maximum_scaled_residual=harmonic_error,
        equivalent_R_Schur_maximum_relative_difference=relative_G,
        symmetric_projection_roundoff_relative_to_absolute_contributions=antisymmetry,
        charge_residual_relative_to_absolute_contributions=charge,
        zero_wire_R_capacitance_maximum_change_native_units=float(collapse_error),
        capacitance_unit_F=1e-18,numerical_passivity_check_pending=True,
        physical_model_or_oscillator_frequency_error_qualified=False,runtime_model_eligible=False,
        release_qualified=False,adopted=False,deadline_uptime=deadline,
        input_sha256={str(p.resolve()):digest(p) for p in inputs},
        artifacts={str(p.resolve()):digest(p) for p in artifacts})
    save(args.output/'assessment.json',result);status('completed_prototype_validation_pending')
    print(json.dumps({k:v for k,v in result.items() if k not in ['input_sha256','artifacts']},indent=2))


if __name__=='__main__':main()
