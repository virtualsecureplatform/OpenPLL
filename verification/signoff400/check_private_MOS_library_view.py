"""Paired native equivalence/timing controls for a conservative library view."""
import argparse,json,os,time
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease
from compiled_charge import execute
from check_current_generic_poly_models_v3 import numeric
from probe_native_junction_alias_v2 import table


def work(out,view,deadline):
    source=ROOT/'build/signoff400/startup_timing_MOS_backend_batch_control_001';receipt=source/'assessment.json';a=json.loads(receipt.read_text());vp=view/'view/assessment.json';v=json.loads(vp.read_text());library=Path(v['library']);original=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice');ng=ROOT/'build/tools/ngspice47/install/bin/ngspice';xy=Path('/opt/xyce/bin/Xyce');pins={**a['input_sha256'],**v['input_sha256'],**v['artifacts']}
    for p in (receipt,vp,Path(__file__).resolve(),Path(__file__).with_name('prepare_MOS_library_view.py'),Path(__file__).with_name('check_current_generic_poly_models_v3.py'),Path(__file__).with_name('probe_native_junction_alias_v2.py')):pins[str(p)]=sha(p)
    if not set(a['models'])<=set(v['requested_wrappers']):raise ValueError('all actual benchmark model families retained')
    if any(sha(p)!=h for p,h in pins.items()):raise ValueError('sealed model/view/engine input changed')
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1');results=[];artifacts=[]
    for analysis in ('dc','ac'):
        fixtures=a['results'][analysis]['fixtures'];width=4 if analysis=='dc' else 8
        for engine,binary in (('ngspice',ng),('Xyce',xy)):
            old_deck=source/analysis/('ngspice.cir' if engine=='ngspice' else 'xyce.cir');old_data=source/analysis/('ngspice.dat' if engine=='ngspice' else ('xyce.cir.prn' if analysis=='dc' else 'xyce.cir.FD.prn'))
            for p in (old_deck,old_data):
                pins[str(p)]=sha(p)
                if pins[str(p)]!=a['artifacts'][str(p)]:raise ValueError('sealed native benchmark changed')
            def read(path):
                rows=numeric(path,fixtures*width+(2 if analysis=='dc' else 1),7 if analysis=='dc' else 0) if engine=='ngspice' else table(path,fixtures*width,7 if analysis=='dc' else 2)
                if analysis=='ac' and engine=='ngspice':
                    rows=[r for r in rows if r[0] in (1e6,4e8)]
                    if [r[0] for r in rows]!=[1e6,4e8]:raise ValueError('exact AC frequency coverage')
                return rows
            retained=read(old_data);waves={};times={};original_text=old_deck.read_text();prefix='.lib "'+str(original)+'" tt'
            if original_text.count(prefix)!=1:raise ValueError('one exact library-selection directive')
            # Alternate pair order across DC/AC; observations remain nonisolated.
            for label in (('baseline','private') if analysis=='dc' else ('private','baseline')):
                where=out/(analysis+'_'+engine+'_'+label);where.mkdir();deck=where/(engine+'.cir');data=where/('ngspice.dat' if engine=='ngspice' else (engine+'.cir'+('.prn' if analysis=='dc' else '.FD.prn')));text=original_text
                if label=='private':text=text.replace(prefix,'.lib "'+str(library)+'" tt')
                before='wrdata '+str(old_data)+' '
                if engine=='ngspice':
                    if text.count(before)!=1:raise ValueError('one reference output relocation')
                    text=text.replace(before,'wrdata '+str(data)+' ')
                restored=text.replace('.lib "'+str(library)+'" tt',prefix) if label=='private' else text
                if engine=='ngspice':restored=restored.replace('wrdata '+str(data)+' ',before)
                if restored!=original_text:raise ValueError('only library selection/output path may differ')
                deck.write_text(text);pins[str(deck)]=sha(deck);save(out/'input_manifest.json',dict(input_sha256=pins,library_definitions_only_omitted=True,all_physical_fixture_tokens_identical=True,release_qualified=False));save(out/'status.json',dict(state='running_'+analysis+'_'+engine+'_'+label,release_qualified=False));start=time.monotonic();execute([binary,'-b',deck] if engine=='ngspice' else [binary,'-linsolv','KLU','-quiet','-o',deck,deck],where/'native.log',deadline,4);times[label]=time.monotonic()-start;waves[label]=read(data);artifacts.extend([deck,data,where/'native.log'])
            maximum_replica=maximum_private=0;replica_failures=private_failures=0;comparisons=0
            for old,base,pruned in zip(retained,waves['baseline'],waves['private'],strict=True):
                index=1 if engine=='Xyce' or analysis=='dc' else 0;coordinate=old[index]
                if any(abs(row[index]-coordinate)>1e-12*max(1,abs(coordinate)) for row in (base,pruned)):raise ValueError('native comparison coordinates differ')
                start=2 if engine=='Xyce' or analysis=='dc' else 1
                for i in range(fixtures*4):
                    k=start+i*(1 if analysis=='dc' else 2)
                    def phasor(row):return complex(row[k],0 if analysis=='dc' else row[k+1])
                    x,y,z=map(phasor,(old,base,pruned));replica=abs(x-y);delta=abs(y-z);maximum_replica=max(maximum_replica,replica);maximum_private=max(maximum_private,delta);replica_failures+=replica>1e-20+1e-12*max(abs(x),abs(y));private_failures+=delta>1e-20+1e-12*max(abs(y),abs(z));comparisons+=1
            if comparisons!=a['results'][analysis]['terminal_response_comparisons']:raise ValueError('complete retained fixture coverage')
            results.append(dict(analysis=analysis,engine=engine,terminal_response_comparisons=comparisons,baseline_vs_retained_max_A=maximum_replica,private_vs_fresh_baseline_max_A=maximum_private,baseline_screen_exceedances=replica_failures,private_screen_exceedances=private_failures,native_wall_s_nonisolated=times,observed_baseline_over_private_wall_ratio=times['baseline']/times['private']))
    if any(sha(p)!=h for p,h in pins.items()):raise ValueError('view/engine input changed during comparison')
    passed=all(not r['baseline_screen_exceedances'] and not r['private_screen_exceedances'] for r in results)
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in artifacts},results=results,scope='TT27 first 16 actual profiles, all five MOS families, both simulators DC/AC',tested_native_responses_match=passed,all_PVT_and_profile_equivalence_verified=False,performance_observations_nonisolated=True,repeated_throughput_benchmark_complete=False,private_library_selected_for_release=False,MOS_backend_compatibility_qualified=False,release_qualified=False));save(out/'status.json',dict(state='private_MOS_library_native_controls_complete',response_controls_pass=passed,release_qualified=False))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);parser.add_argument('--view',required=True,type=Path);parser.add_argument('--inside',action='store_true');parser.add_argument('--deadline',type=float);args=parser.parse_args();out=args.output.resolve();view=args.view.resolve()
    if args.inside:return work(out,view,args.deadline)
    out.mkdir(parents=True,exist_ok=False);owner=json.loads((view/'owner.json').read_text());save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),producer_pid=owner['pid'],producer_birth=owner['birth'],wait_deadline_uptime=owner['deadline_uptime'],automatic_identical_retry=False));save(out/'status.json',dict(state='waiting_for_exact_private_library_view',release_qualified=False))
    try:
        while not (view/'view/assessment.json').exists():
            if identity(owner['pid'])!=owner['birth'] or time.clock_gettime(time.CLOCK_BOOTTIME)>=owner['deadline_uptime']:raise RuntimeError('library preparation terminal without assessment')
            time.sleep(2)
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',ROOT/'build/apptainer/openpll-release-modern.sif','/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',Path(__file__).resolve(),'--inside','--deadline',str(deadline),'--view',view,'--output',out],out/'controller.log',deadline,4)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise


if __name__=='__main__':main()
