"""Prepare/run one full-circuit 260 ns calibration at a declared device corner.

Use the large-case scheduler for execution. Preparation never starts a native
worker. Geometric R/C remains the selected nominal extraction at 27 C.
"""
import argparse,json,os,re,time
from pathlib import Path
from common_v3 import ROOT,PROFILE,save,sha,verify
from selected_physical_rtl import source_pins
from resources import identity,lease
from compiled_charge_v2 import execute
from analyze_xyce_runtime import analyze
from run_selected_corner_initial_states import full_workers
from capture_selected_native_runtime import capture

LIB='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice'

def deck_text(text,template_raw,raw,coarse,fine,corner):
    if type(coarse)is not int or not 0<=coarse<=47 or type(fine)is not int or not 8<=fine<=247:
        raise ValueError('supported integer preset codes required')
    if corner not in ('tt','ff','ss','sf','fs'):raise ValueError('declared device corner required')
    if 'exittime'in text.lower()or text.count(str(template_raw))!=1:raise ValueError('one complete native RAW protocol required')
    if text.splitlines().count('.tran 10p 175n 0 1n')!=1 or text.splitlines().count('.options device temp=27')!=1:
        raise ValueError('reviewed nominal-temperature baseline required')
    lib=f'.lib "{LIB}" tt'
    if text.splitlines().count(lib)!=1 or text.splitlines().count('.end')!=1 or 'DIST STRATEGY'in text:
        raise ValueError('reviewed library and distribution protocol required')
    text=text.replace(str(template_raw),str(raw)).replace(lib,f'.lib "{LIB}" {corner}')
    text=text.replace('.tran 10p 175n 0 1n','.tran 10p 260n 0 10p')
    for port,width,code in (('STARTUP_COARSE',6,coarse),('STARTUP_FINE',8,fine)):
        seen=[]
        def bias(match):
            bit=int(match[1]);seen.append(bit)
            return ' '.join(match[0].split()[:3])+(' 1.8'if code&(1<<bit)else ' 0.0')
        pattern=rf'^Vbias\d+[ \t]+{port}\[(\d+)\][ \t]+0[ \t]+\S+$'
        text=re.sub(pattern,bias,text,flags=re.MULTILINE)
        if sorted(seen)!=list(range(width)):raise ValueError('unique complete preset bit inventory required: '+port)
    return text.replace('.end\n','.options DIST STRATEGY=2\n.end\n')

def supply_csv(text,path):
    sources={}
    for line in text.splitlines():
        f=line.split()
        if len(f)==4 and f[0].lower().startswith('v')and f[1]in('VPWR','VPB','VGND','VNB')and f[2]=='0':
            if f[1]in sources:raise ValueError('unique external rail voltage sources required')
            sources[f[1]]=f[0]
    if set(sources)!={'VPWR','VPB','VGND','VNB'}:raise ValueError('all four external supply/body rails required')
    if text.splitlines().count('.end')!=1 or 'format=csv'in text.lower():raise ValueError('one original native deck without CSV required')
    order=('VPWR','VPB','VGND','VNB')
    statement=f'.print tran format=csv precision=17 file={path} '+' '.join(f'v({n})'for n in order)+' '+' '.join(f'i({sources[n]})'for n in order)
    return text.replace('.end\n',statement+'\n.end\n'),sources


def run(output,coarse,fine,corner,prepare_only=False):
    os.sched_setaffinity(0,{30});output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='preparing_full_corner_calibration',release_ready=False))
    original=ROOT/'build/signoff400/prototype_v3_Xyce_full_C_programming_pilot_030'
    tool=ROOT/'build/tools/xyce_umfpack_value_gather_001';rank=ROOT/'tools/xyce_umfpack/rank_exec.py'
    image=ROOT/'build/apptainer/openpll-release-modern.sif';controls=ROOT/'build/signoff400/value_gather_native_controls_128/assessment.json'
    try:
        if json.loads(controls.read_text())['all_native_controls_complete_and_agree']is not True:raise ValueError('compatible native backend controls required')
        pins=source_pins();snapshot=output/'candidate_snapshot.json'
        save(snapshot,dict(source_sha256={p:d for p,d in pins.items()if p.endswith('.v')},selected_physical_binding_verified=True,qualification_pending=True,release_ready=False))
        deck=output/'profile.spice';text,supplies=supply_csv(deck_text((original/'programming.spice').read_text(),original/'programming.raw',output/'profile.raw',coarse,fine,corner),output/'supply.csv');deck.write_text(text)
        paths=[PROFILE,snapshot,deck,original/'programming.spice',original/'model.spice',tool/'Xyce',tool/'CheckedUMFPACK.h',rank,controls,image,Path(__file__).resolve()]
        paths += [Path(__file__).with_name(n)for n in('common_v3.py','selected_physical_rtl.py','resources.py','compiled_charge_v2.py','analyze_xyce_runtime.py','run_selected_corner_initial_states.py','capture_selected_native_runtime.py')]
        pins.update({str(p):sha(p)for p in paths})
        save(output/'manifest.json',dict(input_sha256=pins,CPUs=list(range(16)),MPI_ranks=16,root_solver_threads=1,root_affinity=[0],memory_GiB=64,
            supply_current_sources=supplies,supply_csv=str(output/'supply.csv'),supply_characterization_scope='full circuit during static-preset startup, not a locked-loop power qualification',startup_coarse=coarse,startup_fine=fine,operating_point=dict(corner=corner,temperature_c=27,supply_v=1.8),
            passive_view='selected nominal geometric R/C',required_end_s=260e-9,measurement_start_s=200e-9,maximum_step_s=10e-12,
            assessment_after_reference_s=180e-9,full_corner_models_qualified=False,qualification_pending=True,release_ready=False))
        verify(pins)
        if prepare_only:
            save(output/'status.json',dict(state='prepared_without_native_execution',release_ready=False));return
        if not Path(LIB).is_file():raise ValueError('execution requires the pinned CAD container PDK namespace')
        if full_workers():raise RuntimeError('full-native slot occupied; use the shared large-case scheduler')
        capture(output,LIB,image,output/'runtime_namespace.json');pins[str(output/'runtime_namespace.json')]=sha(output/'runtime_namespace.json')
        manifest=json.loads((output/'manifest.json').read_text());manifest['input_sha256']=pins;save(output/'manifest.json',manifest)
        os.sched_setaffinity(0,set(range(16)));os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
        start=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=start+172500
        save(output/'status.json',dict(state='running_loaded_startup_260ns',started_uptime=start,native_deadline_uptime=deadline,release_ready=False))
        with lease(16,64,deadline):execute(['/usr/bin/mpirun','--bind-to','none','-np','16','/usr/bin/python3',rank,'--cpus',','.join(map(str,range(16))),'--',tool/'Xyce','-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,48)
        save(output/'timing.json',analyze(output/'native.log'));verify(pins)
        save(output/'status.json',dict(state='native_startup_completed_waveform_assessment_pending',native_elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start,release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--coarse',type=int,default=20);p.add_argument('--fine',type=int,default=111)
    p.add_argument('--corner',choices=('tt','ff','ss','sf','fs'),default='tt');p.add_argument('--prepare-only',action='store_true')
    a=p.parse_args();run(a.output.resolve(),a.coarse,a.fine,a.corner,a.prepare_only)
