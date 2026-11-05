"""Compare isolated reference binaries against sealed original MOS responses."""
import argparse,json,os,re,time
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease
from compiled_charge import execute
from check_current_generic_poly_models_v3 import numeric
from probe_native_junction_alias_v2 import table


def work(out,build,deadline):
    source=ROOT/'build/signoff400/startup_timing_MOS_body_response_001';receipt=source/'assessment.json';a=json.loads(receipt.read_text());bp=build/'assessment.json';b=json.loads(bp.read_text());binary_paths=[Path(b[k]) for k in ('baseline_binary','diagnostic_binary')];pins=dict(a['input_sha256']);extra=[receipt,bp,Path(__file__).resolve(),Path(__file__).with_name('check_current_generic_poly_models_v3.py'),Path(__file__).with_name('probe_native_junction_alias_v2.py'),*binary_paths]
    for p in binary_paths:
        if sha(p)!=b['artifacts'][str(p)]:raise ValueError('sealed diagnostic binary changed')
    for p in extra:pins[str(p)]=sha(p)
    if any(sha(p)!=h for p,h in pins.items()):raise ValueError('current native/reference model lineage changed')
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1');results={};artifacts=[]
    for analysis in ('dc','ac'):
        d=source/analysis;paths=[d/'fixtures.json',d/'ngspice.dat',d/'ngspice.cir',d/('xyce.cir.prn' if analysis=='dc' else 'xyce.cir.FD.prn')]
        for p in paths:
            pins[str(p)]=sha(p)
            if pins[str(p)]!=a['artifacts'][str(p)]:raise ValueError('sealed raw native data changed')
        fixtures=json.loads(paths[0].read_text());width=4 if analysis=='dc' else 8;columns=len(fixtures)*width+(2 if analysis=='dc' else 1);old=numeric(paths[1],columns,7 if analysis=='dc' else 0);native=table(paths[3],len(fixtures)*width,7 if analysis=='dc' else 2);tables=[]
        for label,binary in zip(('baseline','CTM_derivative'),binary_paths,strict=True):
            where=out/(analysis+'_'+label);where.mkdir();data=where/'ngspice.dat';deck=where/'ngspice.cir';original=paths[2].read_text();before='wrdata '+str(paths[1])+' ';after='wrdata '+str(data)+' '
            if original.count(before)!=1:raise ValueError('one output destination replacement')
            changed=original.replace(before,after)
            if changed.replace(after,before)!=original:raise ValueError('identical physical deck required')
            deck.write_text(changed);pins[str(deck)]=sha(deck);save(out/'input_manifest.json',dict(input_sha256=pins,physical_deck_unchanged=True,diagnostic_reference_only=True,release_qualified=False));save(out/'status.json',dict(state='running_'+analysis+'_'+label,release_qualified=False));execute([binary,'-b',deck],where/'ngspice.log',deadline,4);rows=numeric(data,columns,7 if analysis=='dc' else 0);tables.append(rows);artifacts.extend([deck,data,where/'ngspice.log'])
        if analysis=='ac':old,*tables=[[r for r in rows if r[0] in (1e6,4e8)] for rows in [old,*tables]]
        baseline,changed=tables;stats={};replica_max=0;replica_exceedances=0
        for retained,base,corrected,xy in zip(old,baseline,changed,native,strict=True):
            coordinate=retained[1] if analysis=='dc' else retained[0]
            if any(abs((r[1] if analysis=='dc' else r[0])-coordinate)>1e-12*max(1,abs(coordinate)) for r in (base,corrected)) or abs(xy[1]-coordinate)>1e-12*max(1,abs(coordinate)):raise ValueError('exact aligned native/reference observations')
            start=2 if analysis=='dc' else 1;ov,bv,cv,xv=retained[start:],base[start:],corrected[start:],xy[2:]
            for i,f in enumerate(fixtures):
                pid=f['profile']['profile_id'];s=stats.setdefault(pid,dict(profile_id=pid,model=f['profile']['model'],comparisons=0,baseline_vs_Xyce_max_A=0,corrected_vs_Xyce_max_A=-1,corrected_reference_vs_baseline_max_A=0,worst_corrected=None))
                for e in range(4):
                    k=i*width+e*(1 if analysis=='dc' else 2)
                    def phasor(v):return complex(v[k],0 if analysis=='dc' else v[k+1])
                    o,u,v,x=map(phasor,(ov,bv,cv,xv));replica=abs(o-u);replica_max=max(replica_max,replica);replica_exceedances+=replica>1e-20+1e-12*max(abs(o),abs(u));s['comparisons']+=1;s['baseline_vs_Xyce_max_A']=max(s['baseline_vs_Xyce_max_A'],abs(u-x));s['corrected_reference_vs_baseline_max_A']=max(s['corrected_reference_vs_baseline_max_A'],abs(v-u));error=abs(v-x)
                    if error>s['corrected_vs_Xyce_max_A']:
                        s['corrected_vs_Xyce_max_A']=error;s['worst_corrected']=dict(coordinate=coordinate,electrode=('drain','gate','source','bulk')[e],drain=f['drain'],body=f['body'],gate=f['gate'],excitation=f['excitation'],baseline_reference_A=[u.real,u.imag],corrected_reference_A=[v.real,v.imag],native_A=[x.real,x.imag])
        if len(stats)!=10 or sum(s['comparisons'] for s in stats.values())!=(1680 if analysis=='dc' else 4320):raise ValueError('full declared terminal comparison coverage')
        results[analysis]=dict(baseline_vs_retained_max_A=replica_max,baseline_vs_retained_screen_exceedances=replica_exceedances,profiles=list(stats.values()))
    if any(sha(p)!=h for p,h in pins.items()):raise ValueError('comparison input changed')
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in artifacts},results=results,scope='TT -40C, five profiles, body1/body0, explicit PBSWGD; exact retained physical decks with output destinations relocated',baseline_reproduction_screen=dict(absolute_A=1e-20,relative=1e-12),reference_change_is_diagnostic=True,physical_model_or_release_simulator_changed=False,full_PVT_qualification=False,MOS_backend_compatibility_qualified=False,release_qualified=False));save(out/'status.json',dict(state='CV_derivative_reference_comparison_complete',release_qualified=False))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);parser.add_argument('--build',required=True,type=Path);parser.add_argument('--inside',action='store_true');parser.add_argument('--deadline',type=float);args=parser.parse_args();out=args.output.resolve();build=args.build.resolve()
    if args.inside:return work(out,build,args.deadline)
    out.mkdir(parents=True,exist_ok=False);owner=json.loads((build/'owner.json').read_text());wait_deadline=owner['deadline_uptime']+60;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),producer_pid=owner['pid'],producer_birth=owner['birth'],wait_deadline_uptime=wait_deadline,automatic_identical_retry=False));save(out/'status.json',dict(state='waiting_for_exact_isolated_reference_build',release_qualified=False))
    try:
        while not (build/'assessment.json').exists():
            if identity(owner['pid'])!=owner['birth'] or time.clock_gettime(time.CLOCK_BOOTTIME)>=wait_deadline:raise RuntimeError('reference build terminal without sealed binaries')
            time.sleep(2)
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',ROOT/'build/apptainer/openpll-release-modern.sif','/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',Path(__file__).resolve(),'--inside','--deadline',str(deadline),'--build',build,'--output',out],out/'controller.log',deadline,4)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise


if __name__=='__main__':main()
