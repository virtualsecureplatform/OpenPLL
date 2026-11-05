"""Bounded independent-parameter MOS DC/admittance comparison, without model adoption."""
import argparse,json,os,time,math
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease
from compiled_charge import execute
from model_preparation_fast import model_closure
from probe_native_junction_alias_v2 import table
from check_current_generic_poly_models_v3 import numeric


def fixtures(profiles,grid,analysis):
    rows=[]
    for p in profiles:
        for di,drain in enumerate(grid['drain_source_bias_magnitudes_v']):
            for bi,body in enumerate(grid['reverse_body_bias_magnitudes_v']):
                gates=[None] if analysis=='dc' else grid['AC_gate_source_bias_magnitudes_v']
                excitations=[None] if analysis=='dc' else grid['AC_terminal_excitations']
                for gi,gate in enumerate(gates):
                    for ei,excitation in enumerate(excitations):
                        rows.append(dict(name=f'p{p["profile_id"]}d{di}b{bi}g{gi}e{ei}',profile=p,drain=drain,body=body,gate=gate,excitation=excitation))
    return rows


def deck_body(profiles,grid,analysis):
    rows=fixtures(profiles,grid,analysis);lines=['Vdrive ctrl 0 DC 0 AC 1'];quantities=['V(ctrl)'] if analysis=='dc' else [];reference=['v(ctrl)'] if analysis=='dc' else []
    if analysis=='dc':lines.append('BPG pctrl 0 V={1.8-V(ctrl)}')
    for r in rows:
        p=r['profile'];name=r['name'];pfet='pfet_' in p['model']
        if not pfet and 'nfet_' not in p['model']:raise ValueError('explicit MOS polarity required')
        rail=1.8 if pfet else 0;sign=-1 if pfet else 1
        for terminal in ('D','G','S','B'):
            node=terminal.lower()+name;source='V'+terminal+name
            bias={'D':rail+sign*r['drain'],'S':rail,'B':rail-sign*r['body'],'G':None if analysis=='dc' else rail+sign*r['gate']}[terminal]
            if terminal=='G' and analysis=='dc':lines.append(f'{source} {node} '+('pctrl' if pfet else 'ctrl')+' 0')
            else:
                stimulated={'D':'drain','G':'gate','S':'source','B':'bulk'}[terminal]==r['excitation'];lines.append(f'{source} {node} 0 DC {bias:.17g} AC {int(stimulated)}')
            if analysis=='dc':quantities.append(f'I({source})');reference.append(f'i({source})')
            else:quantities.extend([f'IR({source})',f'II({source})']);reference.extend([f'real(i({source}))',f'imag(i({source}))'])
        lines.append(' '.join(['X'+name,*[t+name for t in ('d','g','s','b')],p['model'],*[k+'='+v for k,v in p['parameters'].items()]]))
    return rows,lines,quantities,reference


def work(out,case,deadline):
    cfg=json.loads(case.read_text());base=ROOT/'build/signoff400';proof=base/'startup_timing_MOS_backend_profiles_001/assessment.json';a=json.loads(proof.read_text());ledger=proof.parent/'profiles.jsonl';plan=proof.parent/'comparison_plan.json';grid=json.loads(plan.read_text());profiles=[json.loads(l) for l in ledger.read_text().splitlines()][cfg['profile_start']:cfg['profile_start']+cfg['profile_count']]
    if len(profiles)!=cfg['profile_count'] or not 1<=len(profiles)<=16:raise ValueError('bounded exact profile batch')
    if dict(corner=cfg['corner'],temperature_c=cfg['temperature_c'],supply_v=1.8) not in grid['required_PVT']:raise ValueError('required PVT case')
    pdk=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A');library=pdk/'libs.tech/ngspice/sky130.lib.spice';xyce=Path('/opt/xyce/bin/Xyce');ng=ROOT/'build/tools/ngspice47/install/bin/ngspice';ngproof=ROOT/'build/timing400/release_001/hs_diode_geometry_comparison_001/plan.json';np=json.loads(ngproof.read_text());files=[proof,ledger,plan,case,xyce,ng,ngproof,ROOT/'build/apptainer/openpll-release-modern.sif',Path(__file__).resolve(),Path(__file__).with_name('model_preparation_fast.py'),Path(__file__).with_name('check_current_generic_poly_models_v3.py'),Path(__file__).with_name('probe_native_junction_alias_v2.py'),*model_closure(library,deadline)];pins={str(p):sha(p) for p in files}
    if pins[str(ledger)]!=a['artifacts'][str(ledger)] or pins[str(plan)]!=a['artifacts'][str(plan)] or pins[str(ng)]!=np['input_sha256'][str(ng)]:raise ValueError('current profile, grid or simulator changed')
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1');results={};artifacts=[]
    for analysis in ('dc','ac'):
        rows,body,quantities,reference=deck_body(profiles,grid,analysis);where=out/analysis;where.mkdir();save(where/'fixtures.json',rows);common=[f'.lib "{library}" {cfg["corner"]}',*body];ngdeck=where/'ngspice.cir';data=where/'ngspice.dat';command='dc Vdrive 0 1.8 0.3' if analysis=='dc' else 'ac lin 3 1e6 7.99e8';ngdeck.write_text('\n'.join(['* Exact current MOS profiles: independent terminal bias controls.',*common,f'.temp {cfg["temperature_c"]}', '.options reltol=1e-10 abstol=1e-20 gmin=1e-18','.control','set wr_singlescale','set wr_vecnames','set numdgt=17',command,'wrdata '+str(data)+' '+' '.join(reference),'quit','.endc','.end'])+'\n');pins[str(ngdeck)]=sha(ngdeck);save(out/'input_manifest.json',dict(input_sha256=pins,profile_ids=[p['profile_id'] for p in profiles],case=cfg,physical_parameter_set_selected=False,release_qualified=False));save(out/'status.json',dict(state='running_ngspice_'+analysis,profiles=len(profiles),fixtures=len(rows),release_qualified=False));execute([ng,'-b',ngdeck],where/'ngspice.log',deadline,4)
        reference_data=numeric(data,len(reference)+1,7 if analysis=='dc' else 0)
        if analysis=='ac':
            selected=[]
            for frequency in grid['AC_frequencies_hz']:
                match=[r for r in reference_data if abs(r[0]/frequency-1)<1e-12]
                if len(match)!=1:raise ValueError('unique requested reference AC frequency')
                selected.append(match[0])
            reference_data=selected
        xydeck=where/'xyce.cir';xydeck.write_text('\n'.join(['* Exact current MOS profiles: native independent terminal bias controls.',*common,f'.options device temp={cfg["temperature_c"]} gmin=1e-18','.options nonlin reltol=1e-10 abstol=1e-20','.dc Vdrive 0 1.8 0.3' if analysis=='dc' else '.ac lin 2 1e6 4e8',f'.print {analysis} precision=16 '+' '.join(quantities),'.end'])+'\n');pins[str(xydeck)]=sha(xydeck);save(out/'input_manifest.json',dict(input_sha256=pins,profile_ids=[p['profile_id'] for p in profiles],case=cfg,physical_parameter_set_selected=False,release_qualified=False));save(out/'status.json',dict(state='running_Xyce_'+analysis,profiles=len(profiles),fixtures=len(rows),release_qualified=False));execute([xyce,'-linsolv','KLU','-quiet','-o',xydeck,xydeck],where/'xyce.log',deadline,4);wave=Path(str(xydeck)+('.prn' if analysis=='dc' else '.FD.prn'));native=table(wave,len(quantities)-(analysis=='dc'),7 if analysis=='dc' else 2)
        width=4 if analysis=='dc' else 8;maximum=0;maximum_relative=0;worst=None;comparisons=0;significant=0
        for refrow,nativerow in zip(reference_data,native,strict=True):
            coordinate=refrow[1] if analysis=='dc' else refrow[0]
            if abs(coordinate-nativerow[1])>1e-12*max(1,abs(coordinate)):raise ValueError('aligned independent sweeps required')
            refvalues=refrow[2:] if analysis=='dc' else refrow[1:];nativevalues=nativerow[2:]
            for i,r in enumerate(rows):
                for electrode,t in enumerate(('drain','gate','source','bulk')):
                    k=i*width+electrode*(1 if analysis=='dc' else 2)
                    left=refvalues[k] if analysis=='dc' else complex(refvalues[k],refvalues[k+1]);right=nativevalues[k] if analysis=='dc' else complex(nativevalues[k],nativevalues[k+1]);delta=abs(left-right);scale=max(abs(left),abs(right),1e-18);relative=delta/scale;comparisons+=1;maximum_relative=max(maximum_relative,relative);significant+=delta>1e-15+1e-8*max(abs(left),abs(right))
                    if delta>maximum:maximum=delta;worst=dict(profile_id=r['profile']['profile_id'],model=r['profile']['model'],coordinate=coordinate,drain_source_bias_magnitude_v=r['drain'],reverse_body_bias_magnitude_v=r['body'],gate_source_bias_magnitude_v=r['gate'],AC_excitation=r['excitation'],electrode=t,reference_current=[left.real,left.imag] if analysis=='ac' else left,native_current=[right.real,right.imag] if analysis=='ac' else right,absolute_delta_a=delta,scaled_delta=relative)
        result=dict(fixtures=len(rows),terminal_response_comparisons=comparisons,maximum_absolute_current_difference_A=maximum,maximum_scaled_current_difference=maximum_relative,diagnostic_numeric_screen_exceedances=significant,worst_absolute_current_difference=worst);save(where/'comparison.json',result);results[analysis]=result;artifacts.extend([where/'fixtures.json',ngdeck,data,where/'ngspice.log',xydeck,wave,where/'xyce.log',where/'comparison.json'])
    if any(sha(p)!=h for p,h in pins.items()):raise ValueError('MOS backend case input changed')
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in artifacts},case=cfg,profile_ids=[p['profile_id'] for p in profiles],models=sorted({p['model'] for p in profiles}),unresolved_alternative_instances=sorted({n for p in profiles for n in p['unresolved_native_instances']}),results=results,both_simulators_terminal=True,all_declared_finite_biases_and_terminal_excitations_compared=True,diagnostic_numeric_screen=dict(absolute_A=1e-15,relative=1e-8,is_physical_acceptance_budget=False),response_error_enclosure_qualified=False,physical_junction_parameter_set_selected=False,MOS_backend_compatibility_qualified=False,release_qualified=False));save(out/'status.json',dict(state='MOS_backend_case_comparison_complete',release_qualified=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--inside',action='store_true');p.add_argument('--case',type=Path);p.add_argument('--deadline',type=float);p.add_argument('--corner',default='tt');p.add_argument('--temperature-c',type=int,default=27);p.add_argument('--profile-start',type=int,default=0);p.add_argument('--profile-count',type=int,default=16);args=p.parse_args();out=args.output.resolve()
    if args.inside:return work(out,args.case,args.deadline)
    out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600;case=out/'case.json';save(case,dict(corner=args.corner,temperature_c=args.temperature_c,profile_start=args.profile_start,profile_count=args.profile_count));save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),cpu_slots=1,memory_GiB=4,deadline_uptime=deadline,automatic_identical_retry=False));save(out/'status.json',dict(state='waiting_for_shared_resources',release_qualified=False))
    try:
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',ROOT/'build/apptainer/openpll-release-modern.sif','/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',Path(__file__).resolve(),'--inside','--case',case,'--deadline',str(deadline),'--output',out],out/'controller.log',deadline,4)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise

if __name__=='__main__':main()
