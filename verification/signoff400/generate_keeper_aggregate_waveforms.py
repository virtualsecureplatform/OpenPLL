"""Generate audited reduced forcing arrays from completed, hash-checked inputs."""
import argparse,json,os,time
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1')
import numpy as np
from common_v3 import save,sha,verify
from resources import identity,lease
from aggregate_keeper_boundary_waveforms import aggregate


def checked(path, required):
    value=json.loads(path.read_text())
    if any(value.get(key) is not True for key in required):
        raise ValueError('required completed evidence missing: '+str(path))
    verify(value['input_sha256']);verify(value['artifacts'])
    return value


def wait_completed(directory,expected,deadline):
    while True:
        state=json.loads((directory/'status.json').read_text())['state']
        if state==expected and (directory/'assessment.json').exists():return
        if state=='stopped_without_qualification':raise RuntimeError('prerequisite stopped: '+str(directory))
        owner=json.loads((directory/'owner.json').read_text())
        if identity(owner['pid'])!=owner['birth']:raise RuntimeError('prerequisite owner missing: '+str(directory))
        if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('completed prerequisite observation deadline')
        time.sleep(10)


def run(waveforms,reduction,controls,output,wait=False):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())) )
    try:
        if wait:
            deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+86400
            save(output/'status.json',dict(state='waiting_for_completed_reduction_and_native_controls',observation_cap_s=86400,release_ready=False))
            wait_completed(reduction,'symbolic_boundary_reduction_complete_native_unqualified',deadline)
            wait_completed(controls,'native_capacitor_superposition_controls_complete',deadline)
        # These operations consume completed arrays only, never live RAW data.
        checked(waveforms/'assessment.json',['completed_boundary_waveforms_available','all_saved_native_values_finite','PLLOUT_is_observation_only'])
        r=checked(reduction/'assessment.json',['symbolic_retained_charge_coefficients_preserved'])
        checked(controls/'assessment.json',['all_twenty_four_native_RC_controls_complete','original_and_aggregated_response_matches_closed_form'])
        if r.get('native_equivalence_verified') is not False or r.get('native_simulation_allowed') is not False:
            raise ValueError('expected explicitly unqualified symbolic reduction')
        paths=[waveforms/'assessment.json',waveforms/'boundary.npy',waveforms/'columns.json',reduction/'assessment.json',reduction/'bindings.json',reduction/'charge_certificate.json',controls/'assessment.json',Path(__file__).resolve(),Path(__file__).with_name('aggregate_keeper_boundary_waveforms.py')]
        pins={str(p):sha(p) for p in paths}
        save(output/'inputs.json',dict(input_sha256=pins,CPU=29,memory_GiB=2,resource_queue_cap_s=7200,native_simulation_requested=False,release_ready=False))
        save(output/'status.json',dict(state='waiting_for_global_CPU_RAM_budget',release_ready=False))
        with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+7200):
            save(output/'status.json',dict(state='generating_exactly_audited_weighted_samples',release_ready=False))
            array=np.load(waveforms/'boundary.npy',mmap_mode='r')
            result,columns,audit=aggregate(array,json.loads((waveforms/'columns.json').read_text()),json.loads((reduction/'bindings.json').read_text()),json.loads((reduction/'charge_certificate.json').read_text()))
            np.save(output/'boundary.npy',result,allow_pickle=False);save(output/'columns.json',columns);save(output/'roundoff_audit.json',audit);verify(pins)
        targets=[output/n for n in ['boundary.npy','columns.json','roundoff_audit.json']]
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in targets},completed_boundary_waveforms_available=True,all_saved_native_values_finite=True,PLLOUT_is_observation_only=True,all_original_time_knots_preserved=True,exact_sample_roundoff_audit_complete=True,source_reduction_receipt=str(reduction/'assessment.json'),native_simulation_allowed=False,native_equivalence_verified=False,dynamic_error_qualified=False,model_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='audited_weighted_samples_complete_native_unqualified',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['waveforms','reduction','controls','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--wait',action='store_true');a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['waveforms','reduction','controls','output']),wait=a.wait)
