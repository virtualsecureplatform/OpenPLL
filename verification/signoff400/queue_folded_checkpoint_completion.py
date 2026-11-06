"""Use one certified affine variant only if the original checkpoint hits its cap."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity
from capture_selected_native_runtime import capture
from run_full_corner_calibration import LIB
from queue_selected_target_refinement_v2 import stage_command


def decision(status):
    if status['state']=='saved_state_DCO_diagnostic_complete':return 'skip_original_completed'
    if status['state']=='stopped_without_qualification'and 'TimeoutError'in status.get('reason',''):return 'run_distinct_affine_variant'
    raise ValueError('normal completion or explicit original budget stop required')


def run(original,folded,reference,image,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{30});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    children=[]
    try:
        folder=Path(__file__).resolve().parent;scripts=dict(native=folder/'run_selected_fixed_boundary_fold_control_v2.py',comparison=folder/'compare_selected_saved_state_measured_code.py')
        owner=json.loads((original/'owner.json').read_text());paths=[Path(__file__).resolve(),original/'owner.json',original/'manifest.json',folded/'assessment.json',reference,image,*scripts.values(),*(folder/n for n in('common_v3.py','resources.py','capture_selected_native_runtime.py','run_full_corner_calibration.py','queue_selected_target_refinement_v2.py'))]
        pins={str(p):sha(p)for p in paths};m=json.loads((original/'manifest.json').read_text());verify(m['input_sha256']);f=json.loads((folded/'assessment.json').read_text());verify(f['input_sha256']);verify(f['artifacts'])
        if f['input_sha256'].get(str(original/'manifest.json'))!=sha(original/'manifest.json')or not f['retained_node_equations_exact_before_serialization']or not f['serialized_free_C_passivity_certified']:raise ValueError('same frozen native point and certified affine transform required')
        if m['controls']['coarse']!=20 or m['controls']['fine']!=133 or m['initialized_private_nodes']!=5988:raise ValueError('declared larger fine133 checkpoint required')
        save(output/'inputs.json',dict(input_sha256=pins,original=str(original),folded=str(folded),max_new_native_cases=1,native_cap_s=10800,memory_GiB=8,CPU=22,automatic_identical_retry=False,release_ready=False));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+12600
        while True:
            status=json.loads((original/'status.json').read_text())
            if status['state']not in('preparing_saved_state_DCO_diagnostic','saved_state_DCO_native_running'):break
            if identity(owner['pid'])!=owner['birth']:raise ValueError('original controller disappeared without terminal state')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('original observation deadline; native unchanged')
            save(output/'status.json',dict(state='waiting_for_original_checkpoint_terminal_state',release_ready=False));time.sleep(10)
        worker=json.loads((original/'native.process.json').read_text())
        if identity(worker['pid'])==worker['birth']:raise ValueError('original native remains live')
        action=decision(status);save(output/'decision.json',dict(action=action,original_terminal_status=status,original_worker_confirmed_exited=True,release_ready=False))
        if action=='skip_original_completed':
            verify(pins);save(output/'assessment.json',dict(input_sha256=pins,original_completed_normally=True,new_native_cases=0,folded_variant_executed=False,release_ready=False));save(output/'status.json',dict(state='skipped_original_completed',release_ready=False));return
        def stage(name,args,allow_budget=False):
            command=stage_command(scripts[name],args,image)
            with(output/(name+'.log')).open('x')as log:child=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            children.append(dict(stage=name,pid=child.pid,birth=identity(child.pid),command=command));save(output/'children.json',dict(records=children,release_ready=False));bound=time.clock_gettime(time.CLOCK_BOOTTIME)+(12600 if name=='native'else 1800)
            if name=='native':
                while not(output/'native/owner.json').exists()and child.poll()is None:
                    if time.clock_gettime(time.CLOCK_BOOTTIME)>bound:raise TimeoutError('child observation expired; original child unchanged')
                    time.sleep(1)
                if(output/'native/owner.json').exists():capture(output/'native',LIB,image,output/'runtime_namespace.json')
            while child.poll()is None:
                if time.clock_gettime(time.CLOCK_BOOTTIME)>bound:raise TimeoutError('child observation expired; independently bounded child unchanged')
                save(output/'status.json',dict(state='affine_checkpoint_stage_running',stage=name,release_ready=False));time.sleep(10)
            if child.returncode:
                s=json.loads((output/'native/status.json').read_text())if allow_budget else{}
                if not(allow_budget and s.get('state')=='stopped_without_qualification'and'TimeoutError'in s.get('reason','')):raise RuntimeError('affine stage failed; no identical retry')
        verify(pins);stage('native',['--baseline',original,'--folded',folded,'--output',output/'native','--cpu',22],True)
        stage('comparison',['--native',output/'native','--reference-provenance',reference,'--output',output/'comparison'])
        verify(pins);a=json.loads((output/'comparison/assessment.json').read_text())
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in(output/'decision.json',output/'runtime_namespace.json',output/'comparison/assessment.json')},original_budget_stopped=True,new_distinct_affine_native_cases=1,folded_full_horizon_completed=a['normal_full_window_completed'],uniform_model_uncertainty_qualified=False,release_ready=False));save(output/'status.json',dict(state='conditional_affine_checkpoint_assessed',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),bounded_native_jobs_unchanged=True,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in('original','folded','reference','image','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in('original','folded','reference','image','output')))
