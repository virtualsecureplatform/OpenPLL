"""Queue one measured FF target holdout after the current TT refinement.

The short conditional result selects a request only. It is never substituted for
full-circuit startup evidence or attached to a TT calibration registry.
"""
import argparse,fcntl,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity
from run_selected_corner_initial_states import full_workers
from queue_selected_target_refinement_v2 import stage_command


def candidate_request(manifest,assessment):
    if manifest['operating_point']!={'corner':'ff','temperature_c':27,'supply_v':1.8}:
        raise ValueError('FF nominal-temperature conditional measurement required')
    controls=manifest['controls']
    if (controls['coarse'],controls['fine'])!=(10,152):raise ValueError('declared measured FF target candidate required')
    if assessment['native_exit_zero']is not True or assessment['all_saved_values_finite']is not True:
        raise ValueError('normally completed finite native waveform required')
    if (assessment['coarse'],assessment['fine'])!=(10,152)or assessment['operating_point']!=manifest['operating_point']:
        raise ValueError('measured operating point differs from request')
    mhz=assessment['frequency']['frequency_mhz']
    if type(mhz)not in(int,float)or not 399.6<=mhz<=400.4:
        raise ValueError('conditional candidate must first measure within 1000 ppm of target')
    return dict(corner='ff',coarse=10,fine=152,conditional_frequency_mhz=mhz,
                frequency_is_request_guidance_only=True,release_ready=False)


def run(after,candidate,image,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{30})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    folder=Path(__file__).resolve().parent
    scripts={'native':folder/'run_full_corner_calibration.py','assessment':folder/'follow_full_corner_calibration.py'}
    records=[]
    try:
        owners={str(p):json.loads((p/'owner.json').read_text())for p in(after,candidate)}
        paths=[Path(__file__).resolve(),folder/'common_v3.py',folder/'resources.py',folder/'queue_selected_target_refinement_v2.py',folder/'run_selected_corner_initial_states.py',image,Path('/usr/bin/apptainer'),*scripts.values(),*(p/'owner.json'for p in(after,candidate))]
        pins={str(p):sha(p)for p in paths};verify(pins)
        save(output/'inputs.json',dict(input_sha256=pins,dependencies=list(owners),max_full_native_cases=1,native_cap_s=172500,
            waiting_cap_s=432000,automatic_identical_retry=False,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+432000
        for dependency in(after,candidate):
            while True:
                status=json.loads((dependency/'status.json').read_text())
                terminal=('real_driver_DCO_diagnostic_complete',)if dependency==candidate else('target_refinement_native_point_attached','measured_nominal_target_observed','adjacent_target_bracket_requires_review')
                if status['state']in terminal and(dependency/'assessment.json').exists():break
                owner=owners[str(dependency)]
                if status['state']=='stopped_without_qualification'or identity(owner['pid'])!=owner['birth']:
                    raise RuntimeError('dependency stopped without a completed assessment: '+str(dependency))
                if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('dependency observation deadline; original jobs unchanged')
                save(output/'status.json',dict(state='waiting_for_prior_calibration',dependency=str(dependency),release_ready=False));time.sleep(10)
            for name in('assessment.json','status.json'):
                p=dependency/name;pins[str(p)]=sha(p)
        if json.loads((candidate/'status.json').read_text())['state']!='real_driver_DCO_diagnostic_complete':
            raise ValueError('normal conditional native completion required')
        for name in('manifest.json','assessment.json'):
            p=candidate/name;pins[str(p)]=sha(p)
        m=json.loads((candidate/'manifest.json').read_text());verify(m['input_sha256'])
        request=candidate_request(m,json.loads((candidate/'assessment.json').read_text()));save(output/'request.json',request)
        save(output/'resolved_inputs.json',dict(input_sha256=pins,request=request,release_ready=False))
        def stage(name,args):
            verify(pins);command=stage_command(scripts[name],args,image)
            with(output/(name+'.log')).open('x')as log:
                child=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            records.append(dict(stage=name,pid=child.pid,birth=identity(child.pid),command=command))
            save(output/'children.json',dict(records=records,independently_bounded=True,release_ready=False))
            bound=time.clock_gettime(time.CLOCK_BOOTTIME)+(176400 if name=='native'else 7200)
            while child.poll()is None:
                if time.clock_gettime(time.CLOCK_BOOTTIME)>=bound:raise TimeoutError('child observation expired; bounded child unchanged')
                save(output/'status.json',dict(state='full_corner_stage_running',stage=name,release_ready=False));time.sleep(10)
            if child.returncode:raise RuntimeError(name+' stage failed; no identical retry')
        lockpath=ROOT/'build/signoff400/resources/selected_full_native_slot.lock';lockpath.parent.mkdir(parents=True,exist_ok=True)
        with lockpath.open('a+')as lock:
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('full slot wait expired')
                    time.sleep(10)
            while full_workers():
                if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('full worker wait expired')
                save(output/'status.json',dict(state='waiting_for_full_native_slot',release_ready=False));time.sleep(10)
            stage('native',['--coarse',request['coarse'],'--fine',request['fine'],'--corner',request['corner'],'--output',output/'native'])
        stage('assessment',['--native',output/'native','--output',output/'waveform_assessment'])
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,request=request,
            artifacts={str(p):sha(p)for p in(output/'waveform_assessment/assessment.json',output/'waveform_assessment/provenance.json',output/'waveform_assessment/operating_point_binding.json')},
            native_measurement_attached_to_TT_registry=False,full_corner_model_family_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='full_corner_target_holdout_assessed',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),bounded_children_unchanged=True,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in('after','candidate','image','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in('after','candidate','image','output')))
