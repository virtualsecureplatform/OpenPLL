"""Export one existing TT target run after normal completion; launch no native jobs."""
import argparse,json,os,subprocess,time
from contextlib import nullcontext
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease


def ready(native_state,assessment_state,has_provenance):
    return native_state=='native_startup_completed_waveform_assessment_pending'and assessment_state in ['calibration_waveform_assessed','calibration_waveform_and_supply_power_assessed']and has_provenance


def state(path):
    try:return json.loads(path.read_text()).get('state')
    except (FileNotFoundError,json.JSONDecodeError):return None


def run(pipeline,output):
    if output.exists():raise FileExistsError(output)
    os.sched_setaffinity(0,{23});output.mkdir(parents=True)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    ownerpath=pipeline/'owner.json';owner=json.loads(ownerpath.read_text());native=pipeline/'native';reference=pipeline/'waveform_assessment';folder=Path(__file__).resolve().parent
    image=ROOT/'build/apptainer/openpll-release-modern.sif';drivers=ROOT/'build/signoff400/selected_interface_clock_reset_inventory_276.json';inventory=ROOT/'build/signoff400/selected_detector_boundary_inventory_181.json'
    scripts=['capture_selected_full_native_snapshot.py','capture_selected_clock_driver_waveforms.py','measure_selected_full_sender_clock_frame.py']
    helpers=['common_v3.py','resources.py','capture_selected_native_initial_snapshot.py','run_selected_detector_phase_probe.py','selected_spice_device_conditions.py','selected_matching_corner_sender.py','selected_native_clock_shapes.py','assess_selected_detector_phase_probe_v4.py','measure_selected_receiver_clock_frame.py']
    files=[Path(__file__).resolve(),ownerpath,image,drivers,inventory,*[folder/n for n in scripts+helpers],ROOT/'tools/xyce_waveform/extract_boundary_pwl.cpp']
    pins={str(p):sha(p)for p in files};verify(pins)
    save(output/'inputs.json',dict(input_sha256=pins,source_pipeline=str(pipeline),source_owner=owner,expected_corner='tt',normal_full_260ns_completion_required=True,native_simulations_launched=0,automatic_identical_retry=False,observation_cap_s=3*86400,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3*86400
    try:
        while not ready(state(native/'status.json'),state(reference/'status.json'),(reference/'provenance.json').exists()):
            if state(pipeline/'status.json')=='stopped_without_qualification'or state(reference/'status.json')=='stopped_without_qualification':raise RuntimeError('original TT target pipeline stopped')
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('original TT owner exited before normal assessed result')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('TT packet observation deadline; original job unchanged')
            save(output/'status.json',dict(state='waiting_for_original_TT_target_assessment',release_ready=False));time.sleep(10)
        verify(pins)
        prefix=['apptainer','exec','--bind','/home:/home,/tmp:/tmp',str(image),'python3']
        steps=[('snapshot',scripts[0],['--native',native,'--assessment',reference,'--output',output/'snapshot']),('waveforms',scripts[1],['--drivers',drivers,'--inventory',inventory,'--native',native,'--snapshot-receipt',output/'snapshot/assessment.json','--output',output/'waveforms']),('frame',scripts[2],['--native',native,'--snapshot',output/'snapshot','--waveforms',output/'waveforms','--reference',reference,'--corner','tt','--output',output/'frame'])]
        for name,script,args in steps:
            save(output/'status.json',dict(state='capturing_TT_target_sender',stage=name,release_ready=False))
            # Snapshot/export own their leases; avoid reserving a second slot while they wait.
            with (lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+3600)if name=='frame'else nullcontext()),(output/(name+'.log')).open('x')as log:
                subprocess.run(prefix+[str(folder/script)]+list(map(str,args)),check=True,stdout=log,stderr=subprocess.STDOUT,timeout=2400)
            verify(pins)
        from selected_matching_corner_sender import validate
        op,bindings=validate(native,output/'snapshot',output/'waveforms','tt')
        frame=output/'frame/assessment.json';a=json.loads(frame.read_text())
        if a['operating_point']!={'corner':'tt','temperature_c':27,'supply_v':1.8}or not a['same_full_native_root_and_receiver_source']:raise ValueError('actual same-TT clock frame required')
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,source_native=str(native),operating_point=op,sender_bindings=bindings,frame=str(frame),artifacts={str(frame):sha(frame)},native_simulations_launched=0,conditional_detector_qualified=False,complete_controller_timing_qualified=False,native_interface_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='TT_target_sender_packet_and_frame_captured',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),original_native_job_unchanged=True,release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['pipeline','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.pipeline.resolve(),a.output.resolve())
