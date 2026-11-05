#!/usr/bin/env python3
"""Independent analytic series-RC and consistent-field RC-line controls.

For Gii positive definite and full C positive semidefinite, the omitted port
admittance is -s^2 H.T(Gii+s Cii)^-1 H. With tau>=rho(Gii^-1 Cii), its
C'-normalized relative capacitive norm is <=omega*tau/sqrt(1+(omega*tau)^2).
The control checks the analytic series-RC response and independent full complex
network solves, including positive FE mass off-diagonals/negative scalar caps.
These mathematical controls alone do not qualify any DCO reduction.
"""
import json
import math
from pathlib import Path
import time
import numpy as np
from scipy.linalg import solve
from passive_RC_condensation import conductance,harmonic_paths
from compile_local_C_operators_v2 import digest,save


def add_mass(C,a,b,cap,reference=0):
    # Exact integral of a linearly varying voltage squared on a uniform segment.
    B=np.zeros((2,len(C)));B[0,a]=1;B[0,reference]-=1;B[1,b]=1;B[1,reference]-=1
    C+=B.T@(cap/6*np.array([[2.,1.],[1.,2.]]))@B


def ports(G,C,p,i,s):
    A=G+s*C
    return A[np.ix_(p,p)]-A[np.ix_(p,i)]@solve(A[np.ix_(i,i)],A[np.ix_(i,p)])


def main():
    base=Path(__file__).resolve().parents[2]/'build/timing400/release_001'
    owner=base/'distributed_RC_model_qualification_001/owner.json'
    deadline=json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    out=base/'passive_RC_condensation_controls_001';out.mkdir(exist_ok=False)
    results=[]
    for label,branches in [('series_RC',[(1,2,'2000')]),('parallel_R_series_C',[(1,2,'3000'),(1,2,'6000')])]:
        C=np.array([[1.,0.,-1.],[0.,0.,0.],[-1.,0.,1.]])*3e-12
        G=conductance(3,branches).toarray()
        T,kept,reduced,proof=harmonic_paths(3,branches,[2],[0,1])
        Td=T.toarray();Gr=conductance(len(kept),reduced).toarray();Cr=Td.T@C@Td
        assert np.max(abs(Gr-Td.T@G@Td))<1e-18
        assert np.allclose(Cr,3e-12*np.array([[1.,-1.],[-1.,1.]]),rtol=1e-14,atol=1e-30)
        tau=2000*3e-12;maximum_error=0.
        for frequency in np.logspace(3,12,41):
            omega=2*np.pi*frequency;s=1j*omega
            actual=ports(G,C,[1],[2],s)[0,0]
            analytic=s*3e-12/(1+s*tau)
            maximum_error=max(maximum_error,float(abs(actual-analytic)/abs(analytic)))
            assert abs(actual-analytic)<2e-12*abs(analytic)
            relative=abs(actual-s*3e-12)/(omega*3e-12)
            envelope=omega*tau/math.hypot(1.,omega*tau)
            assert relative<=envelope*(1+1e-10)+1e-12
        results.append(dict(case=label,analytic_complex_response_passed=True,
            maximum_relative_complex_response_error=maximum_error,frequency_points=41))
    # Uniform distributed RC line: the first port moment is known analytically.
    n=10;branches=[(i,i+1,'10') for i in range(1,9)]
    C=np.zeros((n,n))
    for i in range(1,9):add_mass(C,i,i+1,1e-12)
    G=conductance(n,branches).toarray()
    interior=list(range(2,9));p=[1,9]
    T,kept,reduced,proof=harmonic_paths(n,branches,interior,[0,1,9])
    Td=T.toarray();Gr=conductance(len(kept),reduced).toarray();Cr=Td.T@C@Td
    expected_C=8e-12*np.array([[1.,-.5,-.5],[-.5,1/3,1/6],[-.5,1/6,1/3]])
    expected_G=np.zeros((3,3));expected_G[1:,1:]=np.array([[1.,-1.],[-1.,1.]])/80
    assert np.allclose(Cr,expected_C,rtol=1e-14,atol=1e-27)
    assert np.allclose(Gr,expected_G,rtol=1e-14,atol=1e-17)
    assert np.max(abs(Gr-Td.T@G@Td))<1e-16
    assert np.min(np.linalg.eigvalsh(Cr))>-1e-26
    # Preserve within-field variance: opposite end voltages have nonzero energy.
    voltage=np.array([0.,-1.,1.]);assert abs(voltage@Cr@voltage-8e-12/3)<1e-26
    Gii=G[np.ix_(interior,interior)];Cii=C[np.ix_(interior,interior)]
    tau=float(max(solve(Gii,np.sum(abs(Cii),axis=1))))
    vals,vecs=np.linalg.eigh(Cr[1:,1:]);normalizer=vecs@np.diag(1/np.sqrt(vals))@vecs.T
    maximum_ratio=0.
    for frequency in np.logspace(3,12,61):
        omega=2*np.pi*frequency;s=1j*omega
        actual=ports(G,C,p,interior,s)
        reduced_Y=Gr[1:,1:]+s*Cr[1:,1:]
        relative=float(np.linalg.norm(normalizer@(actual-reduced_Y)@normalizer,2)/omega)
        envelope=omega*tau/math.hypot(1.,omega*tau)
        assert relative<=envelope*(1+1e-8)+1e-9,(frequency,relative,envelope)
        maximum_ratio=max(maximum_ratio,relative/envelope)
    results.append(dict(case='uniform_consistent_mass_RC_line',analytic_DC_and_first_moment_passed=True,
        within_field_voltage_variance_preserved=True,complex_admittance_bound_passed=True,
        maximum_observed_to_envelope_ratio=maximum_ratio,frequency_points=61))
    for removed,protected in [([1],[0,1,9])]:
        try:harmonic_paths(n,branches,removed,protected)
        except ValueError:pass
        else:raise AssertionError('Protected device/interface vertex was removed')
    try:harmonic_paths(4,[(0,1,'1'),(1,2,'1'),(1,3,'1')],[1],[0,2,3])
    except ValueError:pass
    else:raise AssertionError('Branch vertex accepted by path-only elimination')
    inputs=[Path(__file__).resolve(),Path(__file__).with_name('passive_RC_condensation.py'),owner]
    save(out/'assessment.json',dict(analytic_RC_and_consistent_field_controls_passed=True,
        protected_terminal_and_branch_vertex_rejections_passed=True,results=results,
        DCO_condensation_or_oscillator_frequency_error_qualified=False,runtime_model_eligible=False,
        release_qualified=False,adopted=False,deadline_uptime=deadline,
        input_sha256={str(p.resolve()):digest(p) for p in inputs}))
    print(json.dumps(dict(controls_passed=True,results=results),indent=2))


if __name__=='__main__':main()
