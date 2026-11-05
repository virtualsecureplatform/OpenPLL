"""Recompute sealed MOS comparisons by actual native parameter profile."""
import argparse,json,os,time
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease
from check_current_generic_poly_models_v3 import numeric
from probe_native_junction_alias_v2 import table


def review(source,out):
    receipt=source/'assessment.json';a=json.loads(receipt.read_text())
    ledger=ROOT/'build/signoff400/startup_timing_MOS_backend_profiles_001/profiles.jsonl'
    profiles={p['profile_id']:p for p in map(json.loads,ledger.read_text().splitlines())}
    pins={str(p):sha(p) for p in (receipt,ledger,Path(__file__).resolve())}
    if pins[str(ledger)]!=a['input_sha256'][str(ledger)]:raise ValueError('profile ledger lineage')
    results={}
    for analysis in ('dc','ac'):
        directory=source/analysis;fixture=directory/'fixtures.json';reference=directory/'ngspice.dat';native=directory/('xyce.cir.prn' if analysis=='dc' else 'xyce.cir.FD.prn')
        for path in (fixture,reference,native):
            pins[str(path)]=sha(path)
            if pins[str(path)]!=a['artifacts'][str(path)]:raise ValueError('sealed comparison artifact changed')
        fixtures=json.loads(fixture.read_text());width=4 if analysis=='dc' else 8
        refs=numeric(reference,len(fixtures)*width+(2 if analysis=='dc' else 1),7 if analysis=='dc' else 0)
        if analysis=='ac':
            refs=[r for r in refs if r[0] in (1e6,4e8)]
            if [r[0] for r in refs]!=[1e6,4e8]:raise ValueError('exact frequency coverage')
        natives=table(native,len(fixtures)*width,7 if analysis=='dc' else 2)
        per_profile={};global_max=0;total=0;exceedances=0
        for left,right in zip(refs,natives,strict=True):
            coordinate=left[1] if analysis=='dc' else left[0]
            if abs(coordinate-right[1])>1e-12*max(1,abs(coordinate)):raise ValueError('sweep alignment')
            lv=left[2:] if analysis=='dc' else left[1:];rv=right[2:]
            for i,f in enumerate(fixtures):
                pid=f['profile']['profile_id'];p=profiles[pid]
                if any(f['profile'][k]!=p[k] for k in ('model','parameters')):raise ValueError('profile identity')
                stat=per_profile.setdefault(pid,dict(profile_id=pid,model=p['model'],parameters=p['parameters'],native_pre_R_instances=sum(x['phase']=='pre_R' for x in p['native_instance_phases']),native_post_R_instances=sum(x['phase']=='post_R' for x in p['native_instance_phases']),unresolved_alternative_instances=p['unresolved_native_instances'],comparisons=0,screen_exceedances=0,maximum_absolute_difference_A=-1,worst=None))
                for electrode in range(4):
                    k=i*width+electrode*(1 if analysis=='dc' else 2)
                    x=complex(lv[k],0 if analysis=='dc' else lv[k+1]);y=complex(rv[k],0 if analysis=='dc' else rv[k+1]);delta=abs(x-y)
                    screen=delta>1e-15+1e-8*max(abs(x),abs(y));stat['comparisons']+=1;stat['screen_exceedances']+=screen;total+=1;exceedances+=screen;global_max=max(global_max,delta)
                    if delta>stat['maximum_absolute_difference_A']:
                        stat['maximum_absolute_difference_A']=delta;stat['worst']=dict(coordinate=coordinate,electrode=('drain','gate','source','bulk')[electrode],drain=f['drain'],body=f['body'],gate=f['gate'],excitation=f['excitation'],reference_A=[x.real,x.imag],native_A=[y.real,y.imag],relative_difference=delta/max(abs(x),abs(y),1e-18))
        original=a['results'][analysis]
        if total!=original['terminal_response_comparisons'] or exceedances!=original['diagnostic_numeric_screen_exceedances'] or global_max!=original['maximum_absolute_current_difference_A']:raise ValueError('producer aggregate did not reproduce')
        if set(per_profile)!=set(a['profile_ids']):raise ValueError('complete profile batch')
        results[analysis]=dict(comparisons=total,screen_exceedances=exceedances,profiles=sorted(per_profile.values(),key=lambda x:-x['maximum_absolute_difference_A']))
    if any(sha(p)!=h for p,h in pins.items()):raise ValueError('review input changed')
    save(out/'assessment.json',dict(input_sha256=pins,case=a['case'],results=results,producer_aggregates_reproduced=True,diagnostic_screen_is_acceptance_budget=False,MOS_backend_compatibility_qualified=False,release_qualified=False))
    save(out/'status.json',dict(state='MOS_profile_response_review_complete',release_qualified=False))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,automatic_identical_retry=False))
    try:
        with lease(1,1,deadline):review(args.source.resolve(),out)
    except BaseException as error:
        save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(error),release_qualified=False));raise


if __name__=='__main__':main()
