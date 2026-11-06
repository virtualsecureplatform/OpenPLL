"""Compare identical DCO circuits with baseline and tighter numerical controls."""
import argparse,json,re
from pathlib import Path
from common_v3 import save,sha,verify
from assess_selected_detector_prefix import read_prefix
from assess_selected_detector_phase_probe_v2 import transitions
from compare_selected_dco_startup_aligned import aligned,metrics


def canonical(path,tight):
    text=path.read_text()
    for name in ['devices','sources']:text,n=re.subn(r'(?m)^\.include "[^"\n]+/'+name+r'\.spice"$',f'.include "<{name}>"',text);assert n==1
    text,n=re.subn(r'(?i)\bfile=\S+','file=<RAW>',text);assert n==1
    old=['.options nonlin reltol=1e-5 abstol=1e-9','.options timeint reltol=1e-5 abstol=1e-9','.tran 10p 60n 0 10p']
    new=['.options nonlin reltol=1e-6 abstol=1e-10','.options timeint reltol=1e-6 abstol=1e-10','.tran 5p 60n 0 5p']
    for a,b in zip(old,new):
        if text.splitlines().count(b if tight else a)!=1:raise ValueError('exact numerical control lines required')
        if tight:text=text.replace(b,a)
    return text


def check(base,target):
    bm,tm=[json.loads((p/'manifest.json').read_text()) for p in [base,target]]
    for m in [bm,tm]:verify(m['input_sha256'])
    if bm['observed_roles']!=tm['observed_roles'] or bm['MPI_ranks']!=tm['MPI_ranks']:raise ValueError('matched observations and solver ranks required')
    for name in ['devices.spice','sources.spice']:
        if (base/name).read_bytes()!=(target/name).read_bytes():raise ValueError('circuit or source values changed')
    if canonical(base/'control.spice',False)!=canonical(target/'control.spice',True):raise ValueError('deck changed beyond tightened numerics')
    return bm,tm


def run(base,target,output,prepare_only=False):
    if output.exists():raise FileExistsError(output)
    bm,tm=check(base,target);files=[Path(__file__).resolve()]
    files += [p/n for p in [base,target] for n in ['manifest.json','devices.spice','sources.spice','control.spice']]
    result=dict(same_circuit_and_source_cards=True,only_solver_tolerances_and_timestep_changed=True,maximum_step_ps=[10,5],reltol=[1e-5,1e-6],abstol=[1e-9,1e-10],full_native_model_convergence_qualified=False,uniform_uncertainty_bound_qualified=False,release_ready=False)
    if not prepare_only:
        waves=[]
        for d,m in [(base,bm),(target,tm)]:
            if json.loads((d/'status.json').read_text())['state']!='real_driver_DCO_diagnostic_complete':raise ValueError('normal native completion required')
            a=json.loads((d/'assessment.json').read_text());verify(a['input_sha256']);verify(a['artifacts']);files += [d/'assessment.json',d/'control.raw']
            rows,info=read_prefix(d/'control.raw',m['observed_roles'])
            if info['incomplete_final_sample_discarded'] or info['declared_samples']!=len(rows) or abs(rows[-1][0]-60e-9)>1e-18:raise ValueError('complete 60 ns native waveform required')
            roles=list(m['observed_roles']);edges,meta=aligned(rows,roles.index('oscillator')+1,roles.index('DCO_reset')+1);waves.append((edges,meta))
        result['frequency_comparisons']=metrics(waves[1][0],waves[0][0],40)
        result['scope']='sampled reduced-circuit sensitivity to combined tightened solver/timestep settings, not separate error attribution'
    result['input_sha256']={str(p):sha(p) for p in files};save(output,result);print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['base','target','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--prepare-only',action='store_true');a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['base','target','output']),a.prepare_only)
