"""Isolate PBSWGD default inheritance using reversible private model copies."""
import argparse,json,os,re,time
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease
from compiled_charge import execute
from model_preparation_fast import model_closure,line_edits
from run_MOS_backend_case_v2 import deck_body
from check_current_generic_poly_models_v3 import numeric
from probe_native_junction_alias_v2 import table


def work(out,deadline):
    base=ROOT/'build/signoff400/startup_timing_MOS_backend_profiles_001';ledger=base/'profiles.jsonl';plan=base/'comparison_plan.json';all_profiles=list(map(json.loads,ledger.read_text().splitlines()));profiles=[]
    for p in all_profiles:
        if p['model'] not in {q['model'] for q in profiles}:profiles.append(p)
    if len(profiles)!=5:raise ValueError('all five used MOS families')
    pdk=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A');library=pdk/'libs.tech/ngspice/sky130.lib.spice';ng=ROOT/'build/tools/ngspice47/install/bin/ngspice';xy=Path('/opt/xyce/bin/Xyce');grid=json.loads(plan.read_text());files=[ledger,plan,ng,xy,Path(__file__).resolve(),Path(__file__).with_name('run_MOS_backend_case_v2.py'),Path(__file__).with_name('model_preparation_fast.py'),Path(__file__).with_name('check_current_generic_poly_models_v3.py'),Path(__file__).with_name('probe_native_junction_alias_v2.py'),*model_closure(library,deadline)];pins={str(p):sha(p) for p in files};copies=[];pairs=[];artifacts=[]
    for index,p in enumerate(profiles):
        name=p['model'];source=pdk/'libs.ref/sky130_fd_pr/spice'/(name+'__tt.pm3.spice');text=source.read_text()
        if re.search(r'\bpbswgd\s*=',text,re.I) or re.search(r'^\s*\.(include|inc|lib)\s',text,re.M|re.I):raise ValueError('flat TT model with omitted PBSWGD required')
        clone='openpll_gate_default_'+str(index)+('_pfet_' if 'pfet_' in name else '_nfet_');wrappers=re.findall(r'^\s*\.subckt\s+(\S+)',text,re.M|re.I);mapping={n:clone if n==name else clone+'_aux_'+str(i) for i,n in enumerate(wrappers)}
        if wrappers.count(name)!=1 or len(wrappers)!=len(set(wrappers)):raise ValueError('unique wrapper names')
        renamed=text.replace(name+'__model',clone+'__model')
        for old,new in mapping.items():renamed=re.sub(r'(?<![A-Za-z0-9_])'+re.escape(old)+r'(?![A-Za-z0-9_])',new,renamed)
        pattern=r'(?im)^(\+\s*pbswgs\s*=\s*([^\s]+)[^\n]*)$';matches=list(re.finditer(pattern,renamed))
        bins=len(re.findall(r'(?im)^\s*\.model\s+',renamed))
        if not matches or len(matches)!=bins:raise ValueError('one explicit PBSWGS per model bin')
        changed=re.sub(pattern,lambda m:m[1]+'\n+ pbswgd = '+m[2],renamed)
        if re.sub(r'(?im)^\+ pbswgd = [^\n]+\n','',changed)!=renamed:raise ValueError('only PBSWGD additions permitted')
        restored=renamed
        for old,new in mapping.items():restored=re.sub(r'(?<![A-Za-z0-9_])'+re.escape(new)+r'(?![A-Za-z0-9_])',old,restored)
        if restored.replace(clone+'__model',name+'__model')!=text:raise ValueError('exact reversible identifier edits')
        target=out/(clone+'.spice');target.write_text(changed);patch=out/(clone+'.edits.json');save(patch,line_edits(text.encode(),changed.encode()));pins[str(target)]=sha(target);artifacts.extend([target,patch]);copies.append(target)
        alternate=dict(p,profile_id=1000+p['profile_id'],model=clone);pairs.append((p,alternate));
    selected=[p for pair in pairs for p in pair];results={};os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    for analysis in ('dc','ac'):
        rows,body,quantities,reference=deck_body(selected,grid,analysis);where=out/analysis;where.mkdir();save(where/'fixtures.json',rows);common=[f'.lib "{library}" tt',*[f'.include "{p}"' for p in copies],*body];data=where/'ngspice.dat';ngdeck=where/'ngspice.cir';ngdeck.write_text('\n'.join(['* Diagnostic PBSWGD inheritance only.',*common,'.temp -40','.options reltol=1e-10 abstol=1e-20 gmin=1e-18','.control','set wr_singlescale','set wr_vecnames','set numdgt=17','dc Vdrive 0 1.8 0.3' if analysis=='dc' else 'ac lin 3 1e6 7.99e8','wrdata '+str(data)+' '+' '.join(reference),'quit','.endc','.end'])+'\n');xydeck=where/'xyce.cir';xydeck.write_text('\n'.join(['* Diagnostic PBSWGD inheritance only.',*common,'.options device temp=-40 gmin=1e-18','.options nonlin reltol=1e-10 abstol=1e-20','.dc Vdrive 0 1.8 0.3' if analysis=='dc' else '.ac lin 2 1e6 4e8',f'.print {analysis} precision=16 '+' '.join(quantities),'.end'])+'\n')
        pins.update({str(p):sha(p) for p in (ngdeck,xydeck)});save(out/'input_manifest.json',dict(input_sha256=pins,diagnostic_models_only=True,release_qualified=False));save(out/'status.json',dict(state='running_gate_sidewall_default_'+analysis,release_qualified=False));execute([ng,'-b',ngdeck],where/'ngspice.log',deadline,4);execute([xy,'-linsolv','KLU','-quiet','-o',xydeck,xydeck],where/'xyce.log',deadline,4);wave=Path(str(xydeck)+('.prn' if analysis=='dc' else '.FD.prn'));ref=numeric(data,len(reference)+1,7 if analysis=='dc' else 0)
        if analysis=='ac':ref=[r for r in ref if r[0] in (1e6,4e8)]
        native=table(wave,len(quantities)-(analysis=='dc'),7 if analysis=='dc' else 2);width=4 if analysis=='dc' else 8;metrics={}
        for left,right in zip(ref,native,strict=True):
            coordinate=left[1] if analysis=='dc' else left[0]
            if abs(coordinate-right[1])>1e-12*max(1,abs(coordinate)):raise ValueError('sweep alignment')
            lv=left[2:] if analysis=='dc' else left[1:];rv=right[2:]
            for i,r in enumerate(rows):
                pid=r['profile']['profile_id'];stat=metrics.setdefault(pid,dict(profile_id=pid,model=r['profile']['model'],maximum_cross_backend_A=0,maximum_ng_intervention_A=0,comparisons=0))
                for e in range(4):
                    k=i*width+e*(1 if analysis=='dc' else 2);x=complex(lv[k],0 if analysis=='dc' else lv[k+1]);y=complex(rv[k],0 if analysis=='dc' else rv[k+1]);stat['maximum_cross_backend_A']=max(stat['maximum_cross_backend_A'],abs(x-y));stat['comparisons']+=1
                    if pid>=1000:
                        original_index=i-(6 if analysis=='dc' else 54);j=original_index*width+e*(1 if analysis=='dc' else 2);z=complex(lv[j],0 if analysis=='dc' else lv[j+1]);stat['maximum_ng_intervention_A']=max(stat['maximum_ng_intervention_A'],abs(x-z))
        results[analysis]=list(metrics.values());artifacts.extend([where/'fixtures.json',ngdeck,xydeck,data,wave,where/'ngspice.log',where/'xyce.log'])
    if any(sha(p)!=h for p,h in pins.items()):raise ValueError('input changed during probe')
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in artifacts},results=results,scope='TT -40C, five first-used profiles, independent DC/AC biases; PBSWGD explicitly equals foundry PBSWGS in private copies',foundry_files_modified=False,diagnostic_models_selected_for_release=False,causal_effect_generalized_to_all_PVT=False,MOS_backend_compatibility_qualified=False,release_qualified=False));save(out/'status.json',dict(state='gate_sidewall_default_probe_complete',release_qualified=False))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);parser.add_argument('--inside',action='store_true');parser.add_argument('--deadline',type=float);args=parser.parse_args();out=args.output.resolve()
    if args.inside:return work(out,args.deadline)
    out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,automatic_identical_retry=False));save(out/'status.json',dict(state='waiting_for_shared_resources',release_qualified=False))
    try:
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',ROOT/'build/apptainer/openpll-release-modern.sif','/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',Path(__file__).resolve(),'--inside','--deadline',str(deadline),'--output',out],out/'controller.log',deadline,4)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise


if __name__=='__main__':main()
