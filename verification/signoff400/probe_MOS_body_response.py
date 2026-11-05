"""Diagnostic body-network intervention after explicit junction inheritance."""
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
    source=ROOT/'build/signoff400/startup_timing_MOS_gate_default_probe_003';receipt=source/'assessment.json';a=json.loads(receipt.read_text());fixture=source/'ac/fixtures.json';plan=ROOT/'build/signoff400/startup_timing_MOS_backend_profiles_001/comparison_plan.json';grid=json.loads(plan.read_text());library=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice');ng=ROOT/'build/tools/ngspice47/install/bin/ngspice';xy=Path('/opt/xyce/bin/Xyce');paths=[receipt,fixture,plan,ng,xy,ROOT/'build/apptainer/openpll-release-modern.sif',Path(__file__).resolve(),*[Path(__file__).with_name(n) for n in ('model_preparation_fast.py','run_MOS_backend_case_v2.py','check_current_generic_poly_models_v3.py','probe_native_junction_alias_v2.py')],*model_closure(library,deadline)];pins={str(p):sha(p) for p in paths}
    if pins[str(fixture)]!=a['artifacts'][str(fixture)]:raise ValueError('sealed fixture lineage')
    for name,h in a['input_sha256'].items():
        if name in pins and pins[name]!=h:raise ValueError('native engine/model/grid changed')
    selected={}
    for row in json.loads(fixture.read_text()):
        p=row['profile']
        if p['profile_id']>=1000:selected[p['profile_id']]=p
    if len(selected)!=5:raise ValueError('five corrected profiles required')
    copies=[];artifacts=[];edits=[]
    for original in sorted(source.glob('openpll_gate_default_*.spice')):
        text=original.read_text();pins[str(original)]=sha(original)
        if pins[str(original)]!=a['artifacts'][str(original)]:raise ValueError('sealed explicit-inheritance model changed')
        renamed=text.replace('openpll_gate_default_','openpll_body_disabled_');values=[]
        def disable(m):
            if float(m[2])!=1:raise ValueError('original body selector must equal one')
            values.append(m[2]);return m[1]+'0'
        changed,count=re.subn(r'(\brbodymod\s*=\s*)(\S+)',disable,renamed,flags=re.I)
        if count!=len(re.findall(r'(?im)^\s*\.model\s+',text)):raise ValueError('all and only model bins changed')
        restore=iter(values);restored=re.sub(r'(\brbodymod\s*=\s*)(\S+)',lambda m:m[1]+next(restore),changed,flags=re.I).replace('openpll_body_disabled_','openpll_gate_default_')
        if restored!=text:raise ValueError('exact reversible body/identifier intervention')
        target=out/original.name.replace('openpll_gate_default_','openpll_body_disabled_');target.write_text(changed);patch=target.with_suffix('.edits.json');save(patch,line_edits(text.encode(),changed.encode()));pins[str(target)]=sha(target);copies.extend([original,target]);artifacts.extend([target,patch]);edits.append(dict(original=str(original),diagnostic=str(target),body_selectors_changed=count))
    profiles=[]
    for p in selected.values():profiles.extend([p,dict(p,profile_id=p['profile_id']+1000,model=p['model'].replace('openpll_gate_default_','openpll_body_disabled_'))])
    results={};os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    for analysis in ('dc','ac'):
        rows,body,quantities,reference=deck_body(profiles,grid,analysis);where=out/analysis;where.mkdir();save(where/'fixtures.json',rows);common=[f'.lib "{library}" tt',*[f'.include "{p}"' for p in copies],*body];data=where/'ngspice.dat';ngdeck=where/'ngspice.cir';ngdeck.write_text('\n'.join(['* Diagnostic body network only; explicit PBSWGD in both alternatives.',*common,'.temp -40','.options reltol=1e-10 abstol=1e-20 gmin=1e-18','.control','set wr_singlescale','set wr_vecnames','set numdgt=17','dc Vdrive 0 1.8 0.3' if analysis=='dc' else 'ac lin 3 1e6 7.99e8','wrdata '+str(data)+' '+' '.join(reference),'quit','.endc','.end'])+'\n');xydeck=where/'xyce.cir';xydeck.write_text('\n'.join(['* Diagnostic body network only; explicit PBSWGD in both alternatives.',*common,'.options device temp=-40 gmin=1e-18','.options nonlin reltol=1e-10 abstol=1e-20','.dc Vdrive 0 1.8 0.3' if analysis=='dc' else '.ac lin 2 1e6 4e8',f'.print {analysis} precision=16 '+' '.join(quantities),'.end'])+'\n');pins.update({str(p):sha(p) for p in (ngdeck,xydeck)});save(out/'input_manifest.json',dict(input_sha256=pins,interventions=edits,diagnostic_models_only=True,release_qualified=False));save(out/'status.json',dict(state='running_body_response_'+analysis,release_qualified=False));execute([ng,'-b',ngdeck],where/'ngspice.log',deadline,4);execute([xy,'-linsolv','KLU','-quiet','-o',xydeck,xydeck],where/'xyce.log',deadline,4);wave=Path(str(xydeck)+('.prn' if analysis=='dc' else '.FD.prn'));ref=numeric(data,len(reference)+1,7 if analysis=='dc' else 0)
        if analysis=='ac':
            ref=[r for r in ref if r[0] in (1e6,4e8)]
            if [r[0] for r in ref]!=[1e6,4e8]:raise ValueError('exact AC frequency coverage')
        native=table(wave,len(quantities)-(analysis=='dc'),7 if analysis=='dc' else 2);width=4 if analysis=='dc' else 8;metrics={}
        for left,right in zip(ref,native,strict=True):
            coordinate=left[1] if analysis=='dc' else left[0]
            if abs(coordinate-right[1])>1e-12*max(1,abs(coordinate)):raise ValueError('sweep alignment')
            lv=left[2:] if analysis=='dc' else left[1:];rv=right[2:]
            for i,r in enumerate(rows):
                pid=r['profile']['profile_id'];stat=metrics.setdefault(pid,dict(profile_id=pid,model=r['profile']['model'],body_model_selector=1 if pid<2000 else 0,comparisons=0,screen_exceedances=0,maximum_cross_backend_A=-1,worst=None))
                for e in range(4):
                    k=i*width+e*(1 if analysis=='dc' else 2);x=complex(lv[k],0 if analysis=='dc' else lv[k+1]);y=complex(rv[k],0 if analysis=='dc' else rv[k+1]);delta=abs(x-y);stat['comparisons']+=1;stat['screen_exceedances']+=delta>1e-15+1e-8*max(abs(x),abs(y))
                    if delta>stat['maximum_cross_backend_A']:
                        stat['maximum_cross_backend_A']=delta;stat['worst']=dict(coordinate=coordinate,electrode=('drain','gate','source','bulk')[e],drain=r['drain'],body=r['body'],gate=r['gate'],excitation=r['excitation'],reference_A=[x.real,x.imag],native_A=[y.real,y.imag],relative_difference=delta/max(abs(x),abs(y),1e-18))
        results[analysis]=list(metrics.values());artifacts.extend([where/'fixtures.json',ngdeck,xydeck,data,wave,where/'ngspice.log',where/'xyce.log'])
    if any(sha(p)!=h for p,h in pins.items()):raise ValueError('probe input changed')
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in artifacts},results=results,interventions=edits,scope='TT -40C five profiles; explicit PBSWGD in all; paired original/disabled internal body resistance',foundry_files_modified=False,diagnostic_models_selected_for_release=False,body_network_disabled_for_release=False,physical_junction_parameters_selected=False,MOS_backend_compatibility_qualified=False,release_qualified=False));save(out/'status.json',dict(state='body_response_probe_complete',release_qualified=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--inside',action='store_true');p.add_argument('--deadline',type=float);args=p.parse_args();out=args.output.resolve()
    if args.inside:return work(out,args.deadline)
    out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,automatic_identical_retry=False));save(out/'status.json',dict(state='waiting_for_shared_resources',release_qualified=False))
    try:
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',ROOT/'build/apptainer/openpll-release-modern.sif','/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',Path(__file__).resolve(),'--inside','--deadline',str(deadline),'--output',out],out/'controller.log',deadline,4)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise


if __name__=='__main__':main()
