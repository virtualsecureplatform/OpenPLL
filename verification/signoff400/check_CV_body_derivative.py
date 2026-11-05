"""Differentiate the retained CTM Vdseff expression independently of simulators."""
import argparse,json,os,time
from decimal import Decimal,localcontext
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease


def check(out):
    native=ROOT/'build/timing400/release_001/wire_preconditioned_Xyce_001/source/src/DeviceModelPKG/OpenModels/N_DEV_MOSFET_B4p61.C';ng=ROOT/'build/tools/ngspice47/tmpsndfibtf/src/spicelib/devices/bsim4v5/b4v5ld.c';later=ng.parent.parent/'bsim4v6/b4v6ld.c';paths=[native,ng,later,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths};texts=[p.read_text() for p in (native,ng,later)]
    nx=texts[0].split('// Charge-Thickness capMod (CTM) begins',1)[1].split('}  // End of CTM',1)[0];nr=texts[1].split('/* Charge-Thickness capMod (CTM) begins */',1)[1].split('}  /* End of CTM */',1)[0]
    if 'dVdseffCV_dVb = dT0_dVb * (T4 - T5) + T5 * dT1_dVb;' not in nx or 'dVdseffCV_dVb = dT0_dVb * (1.0 - T5) + T5 * dT1_dVb;' not in nr or 'dVdseffCV_dVb = dT0_dVb * (T4 - T5) + T5 * dT1_dVb;' not in texts[2]:raise ValueError('exact audited source branches required')
    rows=[];max_error=Decimal(0);min_reference_error=None
    with localcontext() as context:
        context.prec=90;delta=Decimal('.02');h=Decimal('1e-24')
        def value(s,v):
            x=s-v-delta;r=(x*x+4*delta*s).sqrt();return s*(1-2*delta/(r-x))
        for sv in ('.01','.05','.1','.2','.5','.8'):
            for vv in ('.1','.3','.9','1.8'):
                s,v=Decimal(sv),Decimal(vv);x=s-v-delta
                if x>=0:continue
                r=(x*x+4*delta*s).sqrt();t3=2*delta/(r-x);t4=1-t3;t5=s*t3/(r-x);drds=(x+2*delta)/r
                for ratev in ('-.7','-.03','0','.2','1'):
                    rate=Decimal(ratev);fd=(value(s+rate*h,v)-value(s-rate*h,v))/(2*h);native_derivative=rate*(t4-t5)+t5*drds*rate;reference_derivative=rate*(1-t5)+t5*drds*rate;error=abs(native_derivative-fd);ref_error=abs(reference_derivative-fd);max_error=max(max_error,error)
                    if error>Decimal('1e-38') or abs((reference_derivative-native_derivative)-rate*t3)>Decimal('1e-80'):raise ValueError('analytic/finite difference identity failed')
                    if rate:
                        min_reference_error=ref_error if min_reference_error is None else min(min_reference_error,ref_error)
                        if ref_error<Decimal('1e-6'):raise ValueError('nonzero missing derivative term was not exercised')
                    rows.append(dict(VdsatCV=sv,Vds=vv,dVdsatCV_dVb=ratev,finite_difference=str(fd),native_expression=str(native_derivative),ngspice_v5_expression=str(reference_derivative),native_absolute_error=str(error),ngspice_v5_absolute_error=str(ref_error),expected_reference_minus_native=str(rate*t3)))
    if any(sha(p)!=h for p,h in pins.items()):raise ValueError('derivative source changed')
    save(out/'controls.json',rows);save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(out/'controls.json'):sha(out/'controls.json')},controls=len(rows),decimal_precision=90,central_difference_step='1e-24',maximum_native_vs_finite_difference_error=str(max_error),minimum_nonzero_rate_ngspice_v5_error=str(min_reference_error),native_T4_expression_matches_independent_derivative=True,ngspice_v5_one_expression_has_extra_rate_times_T3=True,later_ngspice_v6_uses_T4_expression=True,scope='CTM T0<0 scalar VdseffCV derivative only; independently varied operating parameters, not a full device or PVT proof',local_Xyce_source_bound_to_image_binary=False,observed_MOS_current_gap_fully_explained=False,reference_simulator_modified=False,MOS_backend_compatibility_qualified=False,release_qualified=False));save(out/'status.json',dict(state='CV_body_derivative_controls_complete',release_qualified=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,automatic_identical_retry=False))
    try:
        with lease(1,1,deadline):check(out)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise


if __name__=='__main__':main()
