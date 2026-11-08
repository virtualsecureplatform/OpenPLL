"""Submit a finite keeper TT tuning family; every native case is independently bounded."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity

CASES=[(8,17,'fit'),(110,18,'fit'),(133,19,'holdout'),(182,22,'fit'),(247,23,'fit')]

def run(output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{31});folder=Path(__file__).resolve().parent;image=ROOT/'build/apptainer/openpll-release-modern.sif';native=folder/'run_keeper_flat_native_independent.py';observer=folder/'assess_keeper_physical_tuning.py';smoke=ROOT/'build/signoff400/selected_keeper_flat_native_smoke_1210';reference=ROOT/'build/signoff400/selected_keeper_fine149_parallel_capture_1266';existing=reference/'inputs.json';base=json.loads(existing.read_text())
    if (base['coarse'],base['fine'],base['corner'],base['temperature_C'],base['supply_V'])!=(20,149,'tt',27,1.8):raise ValueError('same declared TT reference required')
    files=[image,native,observer,smoke/'assessment.json',smoke/'backend_model.spice',existing,Path(__file__).resolve()];pins={str(p):sha(p) for p in files};verify(pins)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));plan=dict(input_sha256=pins,existing_fine149_reference=str(reference),existing_fine149_observer=str(ROOT/'build/signoff400/selected_keeper_parallel_physical_tuning_1268'),coarse=20,corner='tt',temperature_C=27,supply_V=1.8,fit_fine_codes=[8,110,149,182,247],independent_holdout_fine=133,maximum_new_native_cases=5,per_case_CPU=1,per_case_memory_GiB=16,per_case_native_cap_s=86400,maximum_new_native_reservation=dict(CPUs=5,memory_GiB=80),automatic_identical_retry=False,all_node_voltages_requested=True,model_qualified=False,release_ready=False);save(output/'protocol.json',plan);records=[]
    def launch(script,args,log):
        command=['apptainer','exec','--bind','/home:/home,/tmp:/tmp',str(image),'/usr/bin/python3',str(script),*map(str,args)]
        with log.open('x') as stream:child=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        return child,dict(pid=child.pid,birth=identity(child.pid),command=command)
    try:
        for fine,cpu,role in CASES:
            verify(pins);case=output/('fine_'+str(fine).zfill(3));case.mkdir();capture=case/'native';assessment=case/'physical';save(output/'status.json',dict(state='submitting_TT_point',fine=fine,submitted=len(records),release_ready=False))
            child,owner=launch(native,['--smoke',smoke,'--output',capture,'--fine',fine,'--cpu',cpu],case/'native.launch.log');record=dict(fine=fine,CPU=cpu,role=role,native=str(capture),physical=str(assessment),native_controller=owner);records.append(record);save(output/'children.json',dict(records=records,independently_bounded=True,release_ready=False));deadline=time.monotonic()+120
            while not all((capture/name).exists() for name in ['owner.json','inputs.json','status.json']):
                if child.poll() is not None:raise RuntimeError('native controller initialization failed for fine '+str(fine))
                if time.monotonic()>=deadline:raise TimeoutError('native controller initialization observation expired; child unchanged')
                time.sleep(.2)
            ci=json.loads((capture/'inputs.json').read_text())
            if ci['input_sha256'].get(str(smoke/'backend_model.spice'))!=base['input_sha256'].get(str(smoke/'backend_model.spice')):raise ValueError('native model identity changed')
            _,obs=launch(observer,['--reference',capture,'--chains',ROOT/'build/signoff400/selected_keeper_DCO_control_drivers_1233','--full',ROOT/'build/signoff400/selected_keeper_flat_native_model_1208','--route',ROOT/'build/signoff400/selected_keeper_parent_reroute_1136','--output',assessment,'--wait'],case/'physical.launch.log');record['physical_observer']=obs;record['capture_inputs_sha256']=sha(capture/'inputs.json');save(output/'children.json',dict(records=records,independently_bounded=True,release_ready=False))
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,submitted_cases=records,all_five_native_controllers_initialized=True,native_or_physical_results_complete=False,model_qualified=False,release_ready=False));save(output/'status.json',dict(state='TT_characterization_family_submitted',independently_bounded_children=True,release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='submission_stopped_children_unchanged',reason=repr(e),submitted_cases=len(records),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
