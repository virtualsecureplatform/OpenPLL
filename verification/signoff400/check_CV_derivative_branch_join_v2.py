"""Independent smooth-expression checks at the CTM derivative branch join."""
import argparse,json,os,time
from decimal import Decimal,localcontext
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease


def check(out):
    proof=ROOT/'build/signoff400/startup_timing_CV_body_derivative_controls_001/assessment.json';a=json.loads(proof.read_text());pins={str(proof):sha(proof),str(Path(__file__).resolve()):sha(Path(__file__).resolve()),**a['input_sha256']}
    if not a['native_T4_expression_matches_independent_derivative'] or any(sha(p)!=h for p,h in pins.items()):raise ValueError('audited scalar/source lineage required')
    rows=[];joins=[];maximum=Decimal(0)
    with localcontext() as context:
        context.prec=100;delta=Decimal('.02')
        # Algebraically independent symmetric expression; avoids reproducing
        # the simulator's rationalized T0<0 implementation in the oracle.
        def voltage(s,v):return (s+v+delta-((s-v-delta)**2+4*delta*s).sqrt())/2
        for ss in ('.0001','.01','.02','.05','.1','.5','1','2'):
            for vv in ('0','.01','.08','.1','.48','.9','1.8'):
                s,v=Decimal(ss),Decimal(vv);x=s-v-delta;r=(x*x+4*delta*s).sqrt();h=Decimal('1e-30');closed_s=(1-(x+2*delta)/r)/2;closed_v=(1+x/r)/2
                if x>=0:native_s=(1-(x+2*delta)/r)/2;reference_s=native_s
                else:
                    t3=2*delta/(r-x);t4=1-t3;t5=s*t3/(r-x);native_s=t4+t5*((x+2*delta)/r-1);reference_s=1+t5*((x+2*delta)/r-1)
                if v==0:reference_s=Decimal(0)  # Both implementations explicitly override this derivative at Vds=0.
                finite_s=(voltage(s+h,v)-voltage(s-h,v))/(2*h);finite_v=(voltage(s,v+h)-voltage(s,v-h))/(2*h);error=max(abs(native_s-closed_s),abs(native_s-finite_s),abs(closed_v-finite_v));maximum=max(maximum,error)
                if error>Decimal('1e-45') or not 0<=closed_s<=1 or not 0<=closed_v<=1:raise ValueError('smooth-expression derivative controls failed')
                rows.append(dict(VdsatCV=ss,Vds=vv,branch='nonnegative' if x>=0 else 'negative',native_dVdseff_dVdsat=str(native_s),reference_dVdseff_dVdsat=str(reference_s),closed_dVdseff_dVdsat=str(closed_s),finite_dVdseff_dVdsat=str(finite_s),closed_dVdseff_dVds=str(closed_v),finite_dVdseff_dVds=str(finite_v),maximum_absolute_error=str(error)))
        for ss in ('.05','.1','.5','1','2'):
            s=Decimal(ss);v=s-delta;r=(4*delta*s).sqrt();t3=2*delta/r;t5=s*t3/r;negative_native=1-t3+t5*(2*delta/r-1);positive=(1-2*delta/r)/2;negative_reference=1+t5*(2*delta/r-1)
            if abs(negative_native-positive)>Decimal('1e-95') or abs(negative_reference-positive-t3)>Decimal('1e-95'):raise ValueError('branch-join identity failed')
            joins.append(dict(VdsatCV=ss,Vds=str(v),native_negative_side_limit=str(negative_native),native_nonnegative_side_limit=str(positive),reference_negative_side_limit=str(negative_reference),reference_nonnegative_side_limit=str(positive),reference_derivative_jump=str(t3)))
    if any(sha(p)!=h for p,h in pins.items()):raise ValueError('control source changed')
    save(out/'controls.json',dict(points=rows,branch_joins=joins));save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(out/'controls.json'):sha(out/'controls.json')},smooth_expression_controls=len(rows),exact_branch_join_controls=len(joins),maximum_native_closed_form_and_finite_difference_error=str(maximum),native_derivative_matches_smooth_voltage_expression=True,reference_v5_derivative_has_branch_jump=True,reference_jump_formula='sqrt(delta/VdsatCV) at Vds=VdsatCV-delta',scope='scalar CTM effective-voltage derivative; no actual device/PVT operating-state binding',full_current_gap_explained=False,MOS_backend_compatibility_qualified=False,release_qualified=False));save(out/'status.json',dict(state='CV_derivative_branch_join_controls_complete',release_qualified=False))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,automatic_identical_retry=False))
    try:
        with lease(1,1,deadline):check(out)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise


if __name__=='__main__':main()
