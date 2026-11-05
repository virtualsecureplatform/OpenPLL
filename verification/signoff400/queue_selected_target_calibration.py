"""Measure one adaptive target hint after the corner-initialization queue.

A secant hint is never inserted into the DCO table. Original native jobs and
observers retain their own deadlines. Observer failures do not restart or
terminate independently bounded native jobs.
"""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify,source_pins
from resources import identity,lease
from selected_model_registry import validate
from select_calibration_point import choose
from run_selected_corner_initial_states import full_workers
from bind_selected_detector_registry import run as bind_detector
from run_selected_mixed_signal_v3 import run as run_loop


def run(advance,corners,fit,clock,image,output):
    os.sched_setaffinity(0,{19})
    folder=Path(__file__).resolve().parent
    scripts={key:folder/name for key,name in dict(native='run_loaded_startup_260ns.py',
        assessment='follow_selected_calibration.py',registry='advance_selected_calibration.py').items()}
    paths=[Path(__file__).resolve(),advance/'assessment.json',advance/'models.json',advance/'next_point.json',
        corners/'owner.json',fit/'assessment.json',fit/'detector.v',fit/'parameters.json',clock,image,*scripts.values(),
        folder/'selected_model_registry.py',folder/'select_calibration_point.py',folder/'run_selected_corner_initial_states.py',
        folder/'bind_selected_detector_registry.py',folder/'run_selected_mixed_signal_v3.py']
    pins=source_pins();pins.update({str(p):sha(p) for p in paths});verify(pins)
    registry=validate(json.loads((advance/'models.json').read_text()))
    request=json.loads((advance/'next_point.json').read_text())
    if request!=choose(registry['points']) or request['state']!='measurement_needed' or request['coarse']!=20:
        raise ValueError('fresh measured coarse20 target request required')
    code=request['fine']
    if type(code) is not int or not 8<=code<=247 or (20,code) in {(p['coarse'],p['fine']) for p in registry['points']}:
        raise ValueError('one new in-range native measurement required')
    output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    corner_owner=json.loads((corners/'owner.json').read_text());children={};records=[]
    save(output/'inputs.json',dict(input_sha256=pins,request=request,corner_queue_owner=corner_owner,
        max_full_native_cases=1,automatic_identical_retry=False,automatic_next_native_count=1,release_ready=False))
    def spawn(stage,args):
        log=output/(stage+'.log')
        with log.open('x') as stream:
            child=subprocess.Popen(list(map(str,['/usr/bin/python3',scripts[stage],*args])),cwd=ROOT,
                 stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        children[stage]=child;records.append(dict(stage=stage,pid=child.pid,birth=identity(child.pid),log=str(log)))
        save(output/'children.json',dict(records=records,native_jobs_self_bounded=True,release_ready=False))
        return child
    def wait_file(path,child):
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+180
        while not path.exists():
            if child.poll() is not None:raise RuntimeError('child exited before its owner receipt: '+str(path))
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('owner observation deadline; independently bounded child unchanged')
            time.sleep(.2)
    try:
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+172800
        while True:
            state=json.loads((corners/'status.json').read_text())['state']
            if state in ['corner_reset_state_snapshots_captured','stopped_without_qualification']:break
            if identity(corner_owner['pid'])!=corner_owner['birth']:raise RuntimeError('corner queue exited without terminal receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('corner queue observation deadline; original jobs unchanged')
            save(output/'status.json',dict(state='waiting_for_corner_initialization_queue',corner_state=state,release_ready=False));time.sleep(10)
        while full_workers():
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('full-native slot observation deadline; original worker unchanged')
            time.sleep(10)
        verify(pins)
        native=output/'native';assessment=output/'waveform_assessment';attached=output/'registry'
        child=spawn('native',['--fine',code,'--output',native]);wait_file(native/'owner.json',child)
        observer=spawn('assessment',['--native',native,'--output',assessment]);wait_file(assessment/'owner.json',observer)
        spawn('registry',['--registry',advance/'models.json','--base-native',ROOT/'build/signoff400/prototype_v3_loaded_startup_260ns_131',
            '--native',native,'--assessment',assessment,'--output',attached])
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+176400
        for stage,process in children.items():
            while process.poll() is None:
                if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('pipeline observation deadline; independently bounded jobs unchanged')
                save(output/'status.json',dict(state='target_calibration_pipeline_running',waiting_for=stage,fine=code,release_ready=False));time.sleep(10)
            if process.returncode:raise RuntimeError(f'{stage} stage failed; inspect its original log and receipts')
        verify(pins)
        new=validate(json.loads((attached/'models.json').read_text()))
        selected=min((p for p in new['points'] if p['coarse']==20),key=lambda p:(abs(p['frequency_hz']-400e6),p['fine']))
        with lease(1,4,deadline):
            bind_detector(attached/'models.json',fit,clock,output/'selected_interface')
            selected_registry=output/'selected_interface/models.json';r=json.loads(selected_registry.read_text())
            report=run_loop([Path(p['receipt']) for p in r['points']],fit/'detector.v',output/'loop',
                ki=4,kp=0,coarse=20,seed=selected['fine'],polarity=1,scenario=0,phase_ns=0,
                registry_path=selected_registry,clock_timing_path=clock)
        verify(pins)
        artifacts={str(p):sha(p) for p in [attached/'assessment.json',attached/'models.json',attached/'next_point.json',
            output/'selected_interface/assessment.json',output/'selected_interface/models.json',output/'loop/assessment.json']}
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,measured_hint=code,
            seed_selected_only_after_native_measurement=selected,RTL_state=report['state'],measurement_requests=report['measurement_requests'],
            diagnostic=True,physical_models_qualified=False,lock_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='target_native_point_and_selected_seed_RTL_assessed',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),children=records,
             independently_bounded_children_not_restarted_or_terminated=True,release_ready=False));raise

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ['advance','corners','fit','clock','image','output']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    run(*(getattr(args,name).resolve() for name in ['advance','corners','fit','clock','image','output']))
