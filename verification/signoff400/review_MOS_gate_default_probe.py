"""Locate residual terminal response gaps in sealed inheritance controls."""
import argparse,json,os,time
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease
from check_current_generic_poly_models_v3 import numeric
from probe_native_junction_alias_v2 import table


def review(out):
    source=ROOT/'build/signoff400/startup_timing_MOS_gate_default_probe_003';receipt=source/'assessment.json';a=json.loads(receipt.read_text());pins={str(p):sha(p) for p in (receipt,Path(__file__).resolve(),Path(__file__).with_name('check_current_generic_poly_models_v3.py'),Path(__file__).with_name('probe_native_junction_alias_v2.py'))};results={}
    for analysis in ('dc','ac'):
        d=source/analysis;paths=[d/'fixtures.json',d/'ngspice.dat',d/('xyce.cir.prn' if analysis=='dc' else 'xyce.cir.FD.prn')]
        for p in paths:
            pins[str(p)]=sha(p)
            if pins[str(p)]!=a['artifacts'][str(p)]:raise ValueError('sealed native data changed')
        fixtures=json.loads(paths[0].read_text());width=4 if analysis=='dc' else 8;ref=numeric(paths[1],len(fixtures)*width+(2 if analysis=='dc' else 1),7 if analysis=='dc' else 0)
        if analysis=='ac':ref=[r for r in ref if r[0] in (1e6,4e8)]
        native=table(paths[2],len(fixtures)*width,7 if analysis=='dc' else 2);stats={}
        for left,right in zip(ref,native,strict=True):
            coordinate=left[1] if analysis=='dc' else left[0]
            if abs(coordinate-right[1])>1e-12*max(1,abs(coordinate)):raise ValueError('sweep alignment')
            lv=left[2:] if analysis=='dc' else left[1:];rv=right[2:]
            for i,f in enumerate(fixtures):
                pid=f['profile']['profile_id'];s=stats.setdefault(pid,dict(profile_id=pid,model=f['profile']['model'],parameters=f['profile']['parameters'],comparisons=0,screen_exceedances=0,maximum_absolute_difference_A=-1,worst=None))
                for e in range(4):
                    k=i*width+e*(1 if analysis=='dc' else 2);x=complex(lv[k],0 if analysis=='dc' else lv[k+1]);y=complex(rv[k],0 if analysis=='dc' else rv[k+1]);delta=abs(x-y);s['comparisons']+=1;s['screen_exceedances']+=delta>1e-15+1e-8*max(abs(x),abs(y))
                    if delta>s['maximum_absolute_difference_A']:
                        s['maximum_absolute_difference_A']=delta;s['worst']=dict(coordinate=coordinate,electrode=('drain','gate','source','bulk')[e],drain=f['drain'],body=f['body'],gate=f['gate'],excitation=f['excitation'],reference_A=[x.real,x.imag],native_A=[y.real,y.imag],relative_difference=delta/max(abs(x),abs(y),1e-18))
        for old in a['results'][analysis]:
            s=stats[old['profile_id']]
            if s['comparisons']!=old['comparisons'] or s['maximum_absolute_difference_A']!=old['maximum_cross_backend_A']:raise ValueError('native producer aggregates differ')
        results[analysis]=list(stats.values())
    if any(sha(p)!=h for p,h in pins.items()):raise ValueError('review inputs changed')
    save(out/'assessment.json',dict(input_sha256=pins,results=results,producer_aggregates_reproduced=True,diagnostic_screen_is_acceptance_budget=False,MOS_backend_compatibility_qualified=False,release_qualified=False));save(out/'status.json',dict(state='gate_default_residual_review_complete',release_qualified=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,automatic_identical_retry=False));save(out/'status.json',dict(state='waiting_for_shared_resources',release_qualified=False))
    try:
        with lease(1,1,deadline):review(out)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise


if __name__=='__main__':main()
