#!/usr/bin/env python3
"""Check captured RHS identities and retain paired integrated-solver results."""
import json
from pathlib import Path
import numpy as np
from scipy.sparse import load_npz
from compile_local_C_operators_v2 import digest, save

root = Path(__file__).resolve().parents[2]; base = root/'build/timing400/release_001'
synthetic = base/'native_parallel_reuse_probe_checks_001'
native = base/'native_parallel_rhs_probe_checks_001'
inputs = base/'native_adapter_probe_inputs_001'
out = base/'parallel_solver_probe_comparison_audit_001'; out.mkdir(exist_ok=False)
pins = {str(Path(__file__).resolve()):digest(Path(__file__).resolve())}
proofs = []
for folder, count in ((synthetic,48),(native,10)):
    proof_path = folder/'assessment.json'; proof = json.loads(proof_path.read_text())
    assert proof['all_original_equation_residual_checks_passed'] and len(proof['checks']) == count
    for name, sha in proof['input_sha256'].items(): assert digest(Path(name)) == sha, name
    pins[str(proof_path)] = digest(proof_path); proofs.append(proof)
a_path = base/'DCO_native_linear_system_capture_002/native_Jacobian.npz'
a = load_npz(a_path).tocsr(); n=a.shape[0]
scale = 1/np.asarray(abs(a).max(axis=1).toarray()).reshape(-1)
original_native = np.fromfile(inputs/'native_Newton_RHS.bin',dtype='<f8')
known_rhs = np.fromfile(inputs/'known_solution.bin',dtype='<f8')
native_norm = np.linalg.norm(scale*original_native)
known_norm = np.linalg.norm(scale*known_rhs)
perturbation = .001*native_norm/known_norm*known_rhs
rhs_checks = []
for record in proofs[1]['checks']:
    name=record['case']; p=native/(name+'.rhs.bin');rhs=np.fromfile(p,dtype='<f8')
    if name.endswith('perturbed_native'):
        expected=original_native+perturbation
        forward=8*n*np.finfo(float).eps*(abs(original_native)+abs(perturbation))
        assert np.all(abs(rhs-expected)<=forward)
    else:
        expected=known_rhs if name.endswith(('known_solution','known_repeat')) else original_native
        assert np.array_equal(rhs,expected)
    rhs_checks.append(dict(case=name, original_input_RHS_identity_verified=True))
    pins[str(p)]=digest(p)
comparisons=[]
for folder,proof,reference,candidate in ((synthetic,proofs[0],'bounded_','parallel_'),
                                       (native,proofs[1],'baseline_','warm_')):
    records={c['case']:c for c in proof['checks']}
    for name in records:
        if not name.startswith(reference):continue
        other=candidate+name[len(reference):]
        left=folder/(name+'.bin');right=folder/(other+'.bin')
        x=np.fromfile(left,dtype='<f8');y=np.fromfile(right,dtype='<f8')
        assert x.shape==y.shape==(n,) and np.isfinite(x).all() and np.isfinite(y).all()
        rhs_left=folder/(name+'.rhs.bin');rhs_right=folder/(other+'.rhs.bin')
        assert rhs_left.read_bytes()==rhs_right.read_bytes()
        comparisons.append(dict(case=name[len(reference):],group=folder.name,
             maximum_absolute_solution_difference=float(max(abs(x-y))),
             bitwise_equal=np.array_equal(x,y),
             reference_wall_s=records[name]['measured_adapter_wall_s'],
             candidate_wall_s=records[other]['measured_adapter_wall_s']))
        for p in (left,right,rhs_left,rhs_right):pins[str(p)]=digest(p)
assert len(comparisons)==21
aggregates={}
for group in (synthetic.name,native.name):
    selected=[c for c in comparisons if c['group']==group]
    reference=sum(c['reference_wall_s'] for c in selected)
    candidate=sum(c['candidate_wall_s'] for c in selected)
    aggregates[group]=dict(reference_wall_s=reference,candidate_wall_s=candidate,
         candidate_time_reduction_fraction=1-candidate/reference,
         maximum_absolute_solution_difference=max(c['maximum_absolute_solution_difference'] for c in selected))
for p in (a_path,inputs/'native_Newton_RHS.bin',inputs/'known_solution.bin'):pins[str(p)]=digest(p)
save(out/'assessment.json',dict(input_sha256=pins,RHS_identity_checks=rhs_checks,
     paired_solution_comparisons=comparisons,aggregate_observations=aggregates,
     original_equation_residual_checks_passed=58,original_RHS_identity_checks_passed=10,
     cross_solver_solution_difference_acceptance_threshold_selected=False,
     actual_nonlinear_RHS_sequence_tested=False,full_DCO_performance_qualified=False,
     native_waveform_controls_passed=False,live_simulator_modified=False,
     release_qualified=False,adopted=False))
print(json.dumps(aggregates))
