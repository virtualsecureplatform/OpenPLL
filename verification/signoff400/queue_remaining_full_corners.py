"""Queue exactly SS/SF/FS full startup holdouts after the FF holdout.

Conditional native points select requests only. All full runs share the existing
single-job lock, pinned CAD image and independently bounded native worker.
"""
import argparse,fcntl,json,math,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from selected_physical_rtl import source_pins
from resources import identity
from selected_spice_device_conditions import read
from audit_selected_dco_history_inputs import sources
from run_selected_corner_initial_states import full_workers
from queue_selected_target_refinement_v2 import stage_command


def request(manifest,assessment,corner):
    expected=dict(corner=corner,temperature_c=27,supply_v=1.8)
    if corner not in('ss','sf','fs')or manifest['operating_point']!=expected or assessment['operating_point']!=expected:raise ValueError('matching declared remaining corner required')
    controls=manifest['controls'];coarse,fine=controls['coarse'],controls['fine']
    if type(coarse)is not int or type(fine)is not int or not 0<=coarse<=47 or not 8<=fine<=247 or(assessment['coarse'],assessment['fine'])!=(coarse,fine):raise ValueError('same supported observed/requested programming codes required')
    if assessment['native_exit_zero']is not True or assessment['all_saved_values_finite']is not True or assessment['waveform']['incomplete_final_sample_discarded']is not False:raise ValueError('normally completed finite conditional native point required')
    value=assessment['frequency']['frequency_mhz']
    if type(value)not in(int,float)or not math.isfinite(value)or not 399.6<=value<=400.4:raise ValueError('conditional target must first measure within 1000 ppm')
    return dict(corner=corner,coarse=coarse,fine=fine,conditional_frequency_mhz=value,conditional_measurement_is_request_guidance_only=True,release_ready=False)


def run(after,requests,image,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{30});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    records=[]
    try:
        config=json.loads(requests.read_text());verify(config['input_sha256'])
        if [r['corner']for r in config['records']]!=['ss','sf','fs']:raise ValueError('exactly the three remaining corners in declared order required')
        folder=Path(__file__).resolve().parent;scripts=dict(native=folder/'run_full_corner_calibration_v2.py',assessment=folder/'follow_full_corner_calibration_v2.py')
        paths=[Path(__file__).resolve(),requests,image,after/'owner.json',Path('/usr/bin/apptainer'),*scripts.values(),*(folder/n for n in('common_v3.py','selected_physical_rtl.py','resources.py','run_selected_corner_initial_states.py','queue_selected_target_refinement_v2.py','follow_full_corner_calibration.py','assess_native_supply_csv.py','selected_spice_device_conditions.py','audit_selected_dco_history_inputs.py'))]
        pins=source_pins();pins.update(config['input_sha256']);pins.update({str(p):sha(p)for p in paths});resolved=[]
        model=ROOT/'build/signoff400/prototype_v3_Xyce_full_C_programming_pilot_030/model.spice'
        for item in config['records']:
            d=Path(item['native']);m=json.loads((d/'manifest.json').read_text());a=json.loads((d/'assessment.json').read_text());verify(m['input_sha256']);verify(a['input_sha256']);verify(a['artifacts'])
            if m['input_sha256'].get(str(model))!=sha(model):raise ValueError('conditional request comes from another physical model')
            if json.loads((d/'status.json').read_text())['state']!='real_driver_DCO_diagnostic_complete':raise ValueError('normally completed conditional worker required')
            deck=d/'control.spice';stimuli=d/'sources.spice'
            if read(deck)!={'corner':item['corner'],'temperature_c':27.}:raise ValueError('actual conditional native PDK corner differs from request')
            voltage=sources(stimuli)
            if any(float(voltage[n][1])!=v for n,v in(('VPWR',1.8),('VPB',1.8),('VGND',0.),('VNB',0.))):raise ValueError('actual nominal guide supply/body rails required')
            pins.update({str(p):sha(p)for p in(deck,stimuli)})
            resolved.append(request(m,a,item['corner']))
        verify(pins);owner=json.loads((after/'owner.json').read_text());save(output/'inputs.json',dict(input_sha256=pins,predecessor=str(after),resolved_requests=resolved,max_additional_full_native_cases=3,full_native_jobs_at_once=1,waiting_cap_s=1036800,native_cap_s_each=172500,automatic_identical_retry=False,release_ready=False))
        wait_deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1036800
        while True:
            state=json.loads((after/'status.json').read_text())['state']
            if state=='full_corner_target_holdout_assessed':break
            if state=='stopped_without_qualification'or identity(owner['pid'])!=owner['birth']:raise RuntimeError('FF predecessor stopped before a completed holdout')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=wait_deadline:raise TimeoutError('predecessor observation deadline; original jobs unchanged')
            save(output/'status.json',dict(state='waiting_for_FF_full_startup_holdout',release_ready=False));time.sleep(10)
        proof=after/'assessment.json';a=json.loads(proof.read_text());verify(a['input_sha256']);verify(a['artifacts']);pins[str(proof)]=sha(proof)
        def stage(name,args,directory):
            verify(pins);command=stage_command(scripts[name],args,image)
            with(directory/(name+'.log')).open('x')as stream:child=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            records.append(dict(corner=directory.name,stage=name,pid=child.pid,birth=identity(child.pid),command=command));save(output/'children.json',dict(records=records,independently_bounded=True,release_ready=False));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+(176400 if name=='native'else 7200)
            while child.poll()is None:
                if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('child observation deadline; independently bounded child unchanged')
                save(output/'status.json',dict(state='remaining_corner_stage_running',corner=directory.name,stage=name,release_ready=False));time.sleep(10)
            if child.returncode:raise RuntimeError('corner stage failed; no identical retry')
        lockpath=ROOT/'build/signoff400/resources/selected_full_native_slot.lock';lockpath.parent.mkdir(parents=True,exist_ok=True);completed=[]
        for item in resolved:
            directory=output/item['corner'];directory.mkdir();save(directory/'request.json',item)
            with lockpath.open('a+')as lock:
                while True:
                    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                    except BlockingIOError:
                        if time.clock_gettime(time.CLOCK_BOOTTIME)>=wait_deadline:raise TimeoutError('shared full slot observation deadline')
                        time.sleep(10)
                while full_workers():
                    if time.clock_gettime(time.CLOCK_BOOTTIME)>=wait_deadline:raise TimeoutError('full native worker observation deadline')
                    time.sleep(10)
                stage('native',['--corner',item['corner'],'--coarse',item['coarse'],'--fine',item['fine'],'--output',directory/'native'],directory)
            stage('assessment',['--native',directory/'native','--output',directory/'waveform_assessment'],directory)
            paths=[directory/'waveform_assessment'/n for n in('assessment.json','operating_point_binding.json','provenance.json','supply_power.json','complete.json')]
            completed.append(dict(request=item,artifacts={str(p):sha(p)for p in paths}));save(output/'completed_corners.json',completed)
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,records=completed,full_native_corners_measured=['ss','sf','fs'],native_points_attached_to_TT_registry=False,corner_model_families_qualified=False,release_ready=False));save(output/'status.json',dict(state='remaining_corner_holdouts_assessed',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),bounded_children_unchanged=True,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in('after','requests','image','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in('after','requests','image','output')))
