"""Conditional static-charge coordinate invariance; never assign physical ICs.

For constant C, GZ=0 and F(V+Za,t)=F(V,t), a time-constant shift Za
preserves C Vdot+GV+F=0. Floating total charges shift by H a, H=Z^T C Z.
If H is SPD, any total-charge representative can be selected without
changing attached voltages or internal conductor gradients. This does not
identify initial internal gradients or validate the physical C model.
"""
import argparse,json,os,time
from fractions import Fraction as Q
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease


def mv(a,x):return [sum((u*v for u,v in zip(row,x,strict=True)),Q(0)) for row in a]
def add(a,b):return [u+v for u,v in zip(a,b,strict=True)]
def solve(a,b):
    m=[list(map(Q,row))+[Q(v)] for row,v in zip(a,b,strict=True)];n=len(b)
    for k in range(n):
        pivot=next(i for i in range(k,n) if m[i][k]);m[k],m[pivot]=m[pivot],m[k];v=m[k][k];m[k]=[x/v for x in m[k]]
        for i in range(n):
            if i!=k:
                v=m[i][k];m[i]=[x-v*y for x,y in zip(m[i],m[k],strict=True)]
    return [row[-1] for row in m]


def check(out):
    base=ROOT/'build/signoff400';names=('startup_timing_G_components_001','startup_timing_G_component_roles_001','startup_timing_G_edge_operator_controls_002','startup_timing_weighted_C_diagonal_dominance_001');paths=[base/n/'assessment.json' for n in names];pins={str(p):sha(p) for p in [*paths,Path(__file__).resolve()]};topology,roles,operator,coarse=[json.loads(p.read_text()) for p in paths]
    if not topology['exact_edge_graph_kernel_is_original_conductor_constant_subspace'] or not roles['every_graph_component_classified_against_all_devices_ports_and_floating_basis'] or not operator['all_conductor_constant_modes_annihilated_exactly'] or not coarse['grounded_ideal_conductor_SPD_certified']:raise ValueError('actual supporting audits required')
    if roles['results']['other_native_R_components_without_device_or_port']!=0:raise ValueError('unexpected unattached component role')
    c=[[Q(0) for _ in range(6)] for _ in range(6)];g=[[Q(0) for _ in range(6)] for _ in range(6)]
    for i in range(6):c[i][i]=i+1
    def edge(matrix,i,j,w):
        matrix[i][i]+=w;matrix[j][j]+=w;matrix[i][j]-=w;matrix[j][i]-=w
    for i in range(6):
        for j in range(i):edge(c,i,j,Q(i+j+1,11))
    for i,j,w in ((0,1,3),(2,3,5),(4,5,7)):edge(g,i,j,Q(w))
    z=[[Q(i in group) for i in range(6)] for group in ((2,3),(4,5))]
    def charge(v):return [sum(a*b for a,b in zip(col,mv(c,v),strict=True)) for col in z]
    def shift(a):return [sum(col[i]*v for col,v in zip(z,a,strict=True)) for i in range(6)]
    h=[[sum(a*b for a,b in zip(col,mv(c,other),strict=True)) for other in z] for col in z]
    if h[0][0]<=0 or h[0][0]*h[1][1]-h[0][1]*h[1][0]<=0 or any(any(mv(g,col)) for col in z):raise ValueError('exact fixture SPD/nullspace')
    def nonlinear(v):return [v[0]**3-v[1],v[1]**3+v[0],Q(0),Q(0),Q(0),Q(0)]
    v=list(map(Q,(1,-2,3,5,-7,11)));source=list(map(Q,(2,-3,0,0,0,0)));dv=solve(c,[-x for x in add(add(mv(g,v),nonlinear(v)),source)]);q=charge(v);rows=[]
    for target in ((Q(0),Q(0)),(Q(3,7),Q(-5,11)),(Q(-13),Q(101))):
        a=solve(h,[u-w for u,w in zip(target,q,strict=True)]);delta=shift(a);changed=add(v,delta);residual=add(add(add(mv(c,dv),mv(g,changed)),nonlinear(changed)),source)
        if any(residual) or charge(changed)!=list(target) or changed[:2]!=v[:2] or changed[2]-changed[3]!=v[2]-v[3] or changed[4]-changed[5]!=v[4]-v[5]:raise ValueError('conditional charge invariance failed')
        if any(sum(col[i]*mv(c,dv)[i] for i in range(6)) for col in z):raise ValueError('floating total charge not conserved')
        rows.append(dict(target_charge=list(map(str,target)),constant_component_shift=list(map(str,a)),attached_voltages_unchanged=True,internal_gradients_unchanged=True,exact_KCL_residual_zero=True))
    delta=shift([Q(1),Q(2)]);changed=add(v,delta);negative={}
    rounded=[row[:] for row in g];rounded[2][2]+=Q(1,10**20);negative['rounded_diagonal_breaks_exact_nullspace']=any(mv(rounded,delta))
    grounded=[row[:] for row in g];grounded[2][2]+=1;negative['grounding_float_breaks_invariance']=any(mv(grounded,delta))
    negative['floating_nonlinear_device_breaks_invariance']=changed[2]**3!=v[2]**3
    negative['voltage_dependent_capacitance_needs_separate_proof']=(changed[2]**2-v[2]**2)*dv[2]!=0
    negative['time_dependent_shift_adds_capacitive_forcing']=any(mv(c,delta))
    gradient=[Q(0),Q(0),Q(1),Q(-1),Q(0),Q(0)];negative['different_internal_gradient_is_not_a_charge_gauge']=any(mv(g,gradient))
    if not all(negative.values()):raise ValueError('invalid gauge assumptions were not rejected')
    if any(sha(p)!=v for p,v in pins.items()):raise ValueError('supporting source changed')
    save(out/'controls.json',dict(exact_charge_representatives=rows,negative_controls=negative,charge_submatrix=list(map(lambda r:list(map(str,r)),h))))
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(out/'controls.json'):sha(out/'controls.json')},conditional_static_charge_coordinate_invariance_controls_pass=True,theorem='constant C, exact GZ=0, nonlinear equations/observations invariant under constant Za; H=Z^T C Z SPD gives arbitrary charge representatives',actual_unattached_floating_components=roles['results']['unextracted_floating_components'],actual_unattached_voltage_states=roles['results']['unextracted_floating_voltage_states'],supporting_G_and_role_audits_pass=True,grounded_ideal_conductor_C_SPD_proved=True,full_spatial_C_collapse_and_maps_verified=False,full_spatial_C_constant_model_physically_qualified=False,actual_runtime_solver_uses_exact_incidence_G=False,physical_initial_internal_gradients_selected=False,physical_floating_initial_charges_selected=False,actual_floating_charge_unknowns_eliminated_for_release=False,native_solver_contract_implemented=False,physical_RC_qualified=False,release_qualified=False));save(out/'status.json',dict(state='conditional_floating_charge_gauge_controls_complete',release_qualified=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,automatic_identical_retry=False))
    try:
        with lease(1,1,deadline):check(out)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise


if __name__=='__main__':main()
