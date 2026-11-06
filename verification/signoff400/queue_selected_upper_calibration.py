"""Queue one measured upper-range point after the original target calibration.

Native frequency is never predicted or inserted. Full jobs run one at a time;
observation failures leave independently bounded children intact.
"""
import argparse,fcntl,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from selected_physical_rtl import source_pins
from selected_model_registry import validate
from select_selected_upper_guard import choose
from run_selected_corner_initial_states import full_workers
from bind_selected_detector_registry import run as bind_detector
from resources import identity


def run(pipeline,fit,clock,image,output,guard_codes=32):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{28})
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    folder=Path(__file__).resolve().parent;owner=json.loads((pipeline/'owner.json').read_text());original=ROOT/'build/signoff400/prototype_v3_Xyce_full_C_programming_pilot_030'
    scripts={key:folder/name for key,name in dict(native='run_loaded_startup_260ns.py',assessment='follow_selected_calibration.py',registry='advance_selected_calibration.py').items()}
    files=[Path(__file__).resolve(),folder/'select_selected_upper_guard.py',folder/'selected_model_registry.py',folder/'run_selected_corner_initial_states.py',folder/'bind_selected_detector_registry.py',pipeline/'owner.json',fit/'assessment.json',fit/'detector.v',fit/'parameters.json',clock,image,original/'programming.spice',original/'model.spice',*scripts.values()]
    pins=source_pins();pins.update({str(p):sha(p) for p in files});verify(pins)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));save(output/'inputs.json',dict(input_sha256=pins,original_pipeline=str(pipeline),original_owner=owner,guard_codes=guard_codes,max_full_native_cases=1,automatic_next_native_count=1,automatic_identical_retry=False,release_ready=False));records=[]
    def wait_process(stage,args):
        log=output/(stage+'.log')
        with log.open('x') as stream:child=subprocess.Popen(list(map(str,['/usr/bin/python3',scripts[stage],*args])),cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        records.append(dict(stage=stage,pid=child.pid,birth=identity(child.pid),log=str(log)));save(output/'children.json',dict(records=records,children_independently_bounded=True,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+(176400 if stage=='native' else 3600)
        while child.poll() is None:
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('child observation deadline; original child unchanged')
            save(output/'status.json',dict(state='upper_calibration_stage_running',stage=stage,release_ready=False));time.sleep(10)
        if child.returncode:raise RuntimeError(stage+' child stopped; inspect original receipts')
    try:
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+172800;registry=pipeline/'registry/models.json'
        while not registry.exists():
            state=json.loads((pipeline/'status.json').read_text())['state']
            if state=='stopped_without_qualification' or identity(owner['pid'])!=owner['birth']:raise RuntimeError('original pipeline stopped before attaching native target data')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('original calibration observation deadline; native untouched')
            save(output/'status.json',dict(state='waiting_for_original_native_target_registry',release_ready=False));time.sleep(10)
        r=validate(json.loads(registry.read_text()))
        if r['analog']['operating_point']!={'corner':'tt','temperature_c':27,'supply_v':1.8}:raise ValueError('current full runner supports TT coarse20 only')
        pins[str(registry)]=sha(registry);verify(pins);request=choose(r['points'],guard_codes);save(output/'request.json',request)
        if request['state']!='measurement_needed':
            save(output/'status.json',dict(state=request['state'],release_ready=False));return
        # The original runner retains its own 48 h native bound and shared
        # 16-core/64-GiB lease. No existing deck or source file is modified.
        lockpath=ROOT/'build/signoff400/resources/selected_full_native_slot.lock';lockpath.parent.mkdir(parents=True,exist_ok=True)
        with lockpath.open('a+') as lock:
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('full-native slot deadline')
                    time.sleep(10)
            while full_workers():
                if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('full-native process observation deadline')
                save(output/'status.json',dict(state='waiting_for_original_full_native_slot',release_ready=False));time.sleep(10)
            verify(pins);wait_process('native',['--fine',request['fine'],'--output',output/'native'])
        wait_process('assessment',['--native',output/'native','--output',output/'waveform_assessment'])
        wait_process('registry',['--registry',registry,'--base-native',ROOT/'build/signoff400/prototype_v3_loaded_startup_260ns_131','--native',output/'native','--assessment',output/'waveform_assessment','--output',output/'registry'])
        bind_detector(output/'registry/models.json',fit,clock,output/'selected_interface');verify(pins)
        files=[output/'request.json',output/'waveform_assessment/assessment.json',output/'registry/models.json',output/'selected_interface/models.json']
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in files},measured_upper_request=request,interpolation_error_bound_qualified=False,startup_headroom_qualified=False,release_ready=False));save(output/'status.json',dict(state='upper_native_point_attached',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),children=records,independently_bounded_children_not_restarted_or_terminated=True,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['pipeline','fit','clock','image','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--guard-codes',type=int,default=32);a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['pipeline','fit','clock','image','output']),a.guard_codes)
