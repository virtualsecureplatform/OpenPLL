"""Diagnostic body-network intervention; never select modified release models."""
import argparse,json,os,re,sys,time,difflib
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease
from compiled_charge import execute
from probe_native_junction_alias_v2 import table
from model_preparation_fast import model_closure,line_edits


def work(out,deadline):
    base=ROOT/'build/signoff400';inventory=base/'startup_timing_native_body_resistance_inventory_001/assessment.json';a=json.loads(inventory.read_text());details=inventory.parent/'model_body_parameters.json';rows=json.loads(details.read_text());delta=base/'startup_timing_native_device_parameter_delta_001/assessment.json';d=json.loads(delta.read_text());cache=delta.parent/'native_device_cards.jsonl';binary=Path('/opt/xyce/bin/Xyce');model=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice')
    if sha(details)!=a['artifacts'][str(details)] or sha(cache)!=d['artifacts'][str(cache)]:raise ValueError('body inventory or native card lineage changed')
    pairs={}
    with cache.open() as f:
        for line in f:
            name,pre,post=json.loads(line)
            if name in ('X14','X52'):pairs[name]=(pre,post)
    if set(pairs)!={'X14','X52'}:raise ValueError('exact native changed-device pair required')
    ordered=[pairs['X14'],pairs['X52']];
    if any(not (pre[1]==pre[3]==pre[4]) for pre,post in ordered):raise ValueError('original D/S/B aliases required')
    files=[inventory,details,delta,cache,binary,ROOT/'build/apptainer/openpll-release-modern.sif',Path(__file__).resolve(),Path(__file__).with_name('probe_native_junction_alias_v2.py'),Path(__file__).with_name('model_preparation_fast.py'),*model_closure(model,deadline)];pins={str(p):sha(p) for p in files}
    for p,h in a['input_sha256'].items():
        if p in pins and pins[p]!=h:raise ValueError('current audited body model/binary changed')
    clones={};patches=[]
    for m,pair in enumerate(ordered):
        name=next(t for t in pair[0] if t.startswith('sky130_fd_pr__'));entry=next(r for r in rows if r['corner']=='tt' and r['model']==name);source=Path(entry['model_file']);text=source.read_text()
        if re.search(r'^\s*\.(include|inc|lib)\s',text,re.M|re.I):raise ValueError('intervention expects a flat model file')
        clone='openpll_diagnostic_body0_'+str(m)
        # Rename only wrapper/model identifiers, leaving global corner parameter references intact.
        wrapper_names=re.findall(r'^\s*\.subckt\s+(\S+)',text,re.M|re.I)
        if wrapper_names.count(name)!=1 or len(wrapper_names)!=len(set(wrapper_names)):raise ValueError('unique flat model wrappers')
        wrapper_map={original:(clone if original==name else clone+'_aux_'+str(i)) for i,original in enumerate(wrapper_names)}
        changed=text.replace(name+'__model',clone+'__model')
        for original,replacement in wrapper_map.items():
            changed=re.sub(r'(?<![A-Za-z0-9_])'+re.escape(original)+r'(?![A-Za-z0-9_])',replacement,changed)
        original_values=[]
        def disable(match):
            if float(match[2])!=1:raise ValueError('audited body selector must equal one')
            original_values.append(match[2]);return match[1]+'0'
        changed,n=re.subn(r'(\brbodymod\s*=\s*)(\S+)',disable,changed,flags=re.I)
        if n!=entry['model_bins']:raise ValueError('every and only audited TT model-bin selector must change')
        restore_values=iter(original_values)
        restored=re.sub(r'(\brbodymod\s*=\s*)(\S+)',lambda x:x[1]+next(restore_values),changed,flags=re.I)
        for original,replacement in wrapper_map.items():
            restored=re.sub(r'(?<![A-Za-z0-9_])'+re.escape(replacement)+r'(?![A-Za-z0-9_])',original,restored)
        restored=restored.replace(clone+'__model',name+'__model')
        if restored!=text:raise ValueError('intervention altered something beyond identifiers/body selector')
        target=out/(clone+'.spice');target.write_text(changed);pins[str(target)]=sha(target);patch=out/(clone+'.patch');save(patch,line_edits(text.encode('utf8'),changed.encode('utf8')));clones[m]=(clone,target);patches.append(dict(native_model=name,diagnostic_model=clone,source=str(source),source_sha256=pins[str(source)],changed_model_bins=n,diagnostic_path=str(target),diagnostic_sha256=sha(target)))
    names=[(m,body,split,version,f'm{m}b{body}s{split}v{version}') for m in range(2) for body in (1,0) for split in (0,1) for version in (0,1)];tables={};artifacts=[p for _,p in clones.values()]
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    save(out/'status.json',dict(state='running_TT27_causal_body_network_controls',release_qualified=False))
    for analysis in ('dc','ac'):
        lines=['* Diagnostic only: original and body-network-disabled devices in one circuit.',f'.lib "{model}" tt',*[f'.include "{p}"' for _,p in clones.values()],'.options device temp=27 gmin=1e-18','.options nonlin reltol=1e-10 abstol=1e-20'];quantities=['V(ctrl)'] if analysis=='dc' else []
        if analysis=='dc':lines.append('Vdrive ctrl 0 0')
        for m,body,split,version,name in names:
            rail=0 if m==0 else 1.8;source=rail+(0.2 if m==0 else -0.2)*split;bulk=f'b{name}' if split else f's{name}'
            if analysis=='dc':lines.extend([f'VG{name} g{name} ctrl 0',f'VS{name} s{name} 0 {source:.17g}']);quantities.extend([f'I(VG{name})',f'I(VS{name})'])
            else:lines.extend([f'VG{name} g{name} 0 DC {1.8 if m==0 else 0} AC {1-split}',f'VS{name} s{name} 0 DC {source:.17g} AC {split}']);quantities.extend([f'IR(VG{name})',f'II(VG{name})',f'IR(VS{name})',f'II(VS{name})'])
            if split:lines.append(f'VB{name} {bulk} 0 {rail}')
            card=ordered[m][version];i=next(i for i,t in enumerate(card) if t.startswith('sky130_fd_pr__'));selected=card[i] if body else clones[m][0];lines.append(' '.join([f'X{name}',f's{name}',f'g{name}',f's{name}',bulk,selected,*card[i+1:]]))
        lines.extend(['.dc Vdrive 0 1.8 0.1' if analysis=='dc' else '.ac lin 2 1e6 4e8',f'.print {analysis} precision=16 '+' '.join(quantities),'.end']);deck=out/(analysis+'.cir');deck.write_text('\n'.join(lines)+'\n');pins[str(deck)]=sha(deck)
        save(out/'input_manifest.json',dict(input_sha256=pins,model_interventions=patches,diagnostic_models_only=True,release_qualified=False))
        execute([binary,'-linsolv','KLU','-quiet','-o',deck,deck],out/(analysis+'.log'),deadline,4);wave=Path(str(deck)+('.prn' if analysis=='dc' else '.FD.prn'));tables[analysis]=table(wave,32 if analysis=='dc' else 64,19 if analysis=='dc' else 2);artifacts.extend([deck,wave,out/(analysis+'.log')])
    lookup={(m,b,s,v):i for i,(m,b,s,v,_) in enumerate(names)};results=[]
    for m in range(2):
        for body in (1,0):
            maximum_absolute=maximum_scaled=0;outside=0;sensitivity=[]
            for analysis,raw in tables.items():
                width=2 if analysis=='dc' else 4
                for row in raw:
                    i=2+lookup[m,body,0,0]*width;j=2+lookup[m,body,0,1]*width
                    for electrode in range(width):
                        left,right=row[i+electrode],row[j+electrode];difference=abs(left-right);scale=max(abs(left),abs(right),1e-18);maximum_absolute=max(maximum_absolute,difference);maximum_scaled=max(maximum_scaled,difference/scale);outside+=difference>1e-24+1e-12*scale
                    if analysis=='ac':
                        i=2+lookup[m,body,1,0]*width+2;j=2+lookup[m,body,1,1]*width+2;sensitivity.append(abs(complex(row[i],row[i+1])-complex(row[j],row[j+1])))
            results.append(dict(model_index=m,native_instance='X14' if m==0 else 'X52',body_model_selector=body,maximum_scalar_alias_current_delta_a=maximum_absolute,maximum_scaled_scalar_alias_delta=maximum_scaled,scalar_alias_comparisons_outside_original_strict_screen=outside,split_source_body_sensitivity_phasor_deltas_a=sensitivity))
    if any(sha(path)!=h for path,h in pins.items()):raise ValueError('causal probe input changed')
    isolation=all(next(r for r in results if r['model_index']==m and r['body_model_selector']==1)['scalar_alias_comparisons_outside_original_strict_screen']>0 and next(r for r in results if r['model_index']==m and r['body_model_selector']==0)['scalar_alias_comparisons_outside_original_strict_screen']==0 for m in range(2))
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in [*artifacts,*out.glob('*.patch')]},model_interventions=patches,results=results,scope='TT27 two affected dummy devices only, DC gate sweep and 1MHz/400MHz AC; diagnostic models never adopted',same_circuit_native_baseline_and_body_disabled_controls=True,only_body_selector_and_private_model_identifiers_changed=True,body_network_isolation_demonstrated_at_tested_point=isolation,old_strict_alias_failure_preserved=True,old_missing_pre_run_model_hashes_recovered=False,foundry_files_modified=False,diagnostic_models_selected_for_release=False,physical_junction_parameter_set_selected=False,spatial_junction_allocation_qualified=False,runtime_model_eligible=False,physical_RC_qualified=False,release_qualified=False));save(out/'status.json',dict(state='TT27_body_network_intervention_complete',release_qualified=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--inside',action='store_true');p.add_argument('--deadline',type=float);args=p.parse_args();out=args.output.resolve()
    if args.inside:return work(out,args.deadline)
    out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),cpu_slots=1,memory_GiB=4,deadline_uptime=deadline,automatic_identical_retry=False));save(out/'status.json',dict(state='waiting_for_shared_resources',release_qualified=False))
    try:
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',ROOT/'build/apptainer/openpll-release-modern.sif','/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',Path(__file__).resolve(),'--inside','--deadline',str(deadline),'--output',out],out/'controller.log',deadline,4)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise

if __name__=='__main__':main()
