"""Review complete terminal KCL and frequency-scaled MOS AC residuals."""
import argparse,json,math,os,time
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease
from check_current_generic_poly_models_v3 import numeric
from probe_native_junction_alias_v2 import table


def review(out):
    source=ROOT/'build/signoff400/startup_timing_MOS_body_response_001';receipt=source/'assessment.json';a=json.loads(receipt.read_text());d=source/'ac';paths=[d/'fixtures.json',d/'ngspice.dat',d/'xyce.cir.FD.prn'];pins={str(p):sha(p) for p in [receipt,Path(__file__).resolve(),Path(__file__).with_name('check_current_generic_poly_models_v3.py'),Path(__file__).with_name('probe_native_junction_alias_v2.py'),*paths]}
    if any(pins[str(p)]!=a['artifacts'][str(p)] for p in paths):raise ValueError('sealed AC data changed')
    fixtures=json.loads(paths[0].read_text());ref=numeric(paths[1],len(fixtures)*8+1,0);ref=[r for r in ref if r[0] in (1e6,4e8)];native=table(paths[2],len(fixtures)*8,2)
    if [r[0] for r in ref]!=[1e6,4e8]:raise ValueError('both exact frequencies required')
    stats={};samples={};kcl={engine:dict(maximum_absolute_A=0,maximum_scaled=0,screen_exceedances=0,fixture_frequency_checks=0) for engine in ('ngspice','Xyce')}
    for left,right in zip(ref,native,strict=True):
        frequency=left[0]
        if frequency!=right[1]:raise ValueError('AC frequency alignment')
        lv=left[1:];rv=right[2:];omega=2*math.pi*frequency
        for i,f in enumerate(fixtures):
            pid=f['profile']['profile_id'];x=[complex(lv[i*8+e*2],lv[i*8+e*2+1]) for e in range(4)];y=[complex(rv[i*8+e*2],rv[i*8+e*2+1]) for e in range(4)]
            for engine,values in (('ngspice',x),('Xyce',y)):
                error=abs(sum(values));scale=sum(map(abs,values));r=kcl[engine];r['fixture_frequency_checks']+=1;r['maximum_absolute_A']=max(r['maximum_absolute_A'],error);r['maximum_scaled']=max(r['maximum_scaled'],error/max(scale,1e-18));r['screen_exceedances']+=error>1e-15+1e-8*scale
            s=stats.setdefault(pid,dict(profile_id=pid,model=f['profile']['model'],parameters=f['profile']['parameters'],by_frequency={},maximum_frequency_normalized_imaginary_residual_change_F=0))
            point=s['by_frequency'].setdefault(str(int(frequency)),dict(comparisons=0,maximum_absolute_current_difference_A=-1,worst=None))
            for e,(u,v) in enumerate(zip(x,y,strict=True)):
                delta=v-u;point['comparisons']+=1
                detail=dict(electrode=('drain','gate','source','bulk')[e],drain=f['drain'],body=f['body'],gate=f['gate'],excitation=f['excitation'],reference_A=[u.real,u.imag],native_A=[v.real,v.imag],native_minus_reference_admittance_S=[delta.real,delta.imag],imaginary_residual_over_omega_F=delta.imag/omega)
                if abs(delta)>point['maximum_absolute_current_difference_A']:point['maximum_absolute_current_difference_A']=abs(delta);point['worst']=detail
                key=(i,e)
                if frequency==1e6:samples[key]=delta.imag/omega
                else:s['maximum_frequency_normalized_imaginary_residual_change_F']=max(s['maximum_frequency_normalized_imaginary_residual_change_F'],abs(delta.imag/omega-samples[key]))
    if len(stats)!=10 or any(sum(p['comparisons'] for p in s['by_frequency'].values())!=432 for s in stats.values()):raise ValueError('all ten profile alternatives and terminal responses required')
    for old in a['results']['ac']:
        if max(r['maximum_absolute_current_difference_A'] for r in stats[old['profile_id']]['by_frequency'].values())!=old['maximum_cross_backend_A']:raise ValueError('producer aggregate mismatch')
    if any(sha(p)!=h for p,h in pins.items()):raise ValueError('review input changed')
    save(out/'assessment.json',dict(input_sha256=pins,results=list(stats.values()),terminal_KCL=kcl,producer_aggregates_reproduced=True,unit_AC_excitation_V=1,imaginary_residual_over_omega_is_observed_admittance_not_physical_capacitance_bound=True,diagnostic_KCL_screen=dict(absolute_A=1e-15,relative_L1=1e-8),MOS_backend_compatibility_qualified=False,release_qualified=False));save(out/'status.json',dict(state='body_admittance_review_complete',release_qualified=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,automatic_identical_retry=False));save(out/'status.json',dict(state='waiting_for_shared_resources',release_qualified=False))
    try:
        with lease(1,1,deadline):review(out)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise


if __name__=='__main__':main()
