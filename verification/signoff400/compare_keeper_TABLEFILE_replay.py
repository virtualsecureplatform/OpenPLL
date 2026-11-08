"""Compare only completed sampled-boundary replay with its identical captured reference."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1')
import argparse,json,time
from pathlib import Path
import numpy as np
from common_v3 import save,sha,verify
from resources import identity,lease
from compare_keeper_native_timestep import compare_waveforms
from assess_selected_detector_phase_probe_v2 import read_selected


def run(replay,waveforms,conditional,output,wait):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+172800
    try:
        while True:
            state=json.loads((replay/'status.json').read_text())['state']
            if state=='conditional_native_replay_complete' and (replay/'assessment.json').exists():break
            if state=='stopped_without_qualification':raise RuntimeError('replay stopped without completed comparison input')
            owner=json.loads((replay/'owner.json').read_text())
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('replay owner gone without completed receipt')
            if not wait:raise RuntimeError('replay still running')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('replay observation deadline')
            save(output/'status.json',dict(state='waiting_for_completed_TABLEFILE_replay',release_ready=False));time.sleep(10)
        receipts=[replay/'assessment.json',waveforms/'assessment.json',conditional/'assessment.json'];r,w,c=[json.loads(p.read_text()) for p in receipts]
        if not r['normal_native_replay_complete'] or not r['all_saved_replay_values_finite'] or r['PLLOUT_forced'] or not r['sampled_boundary_replay_only'] or not r['literal_samples_preserved'] or r['downsampling_requested']:raise ValueError('completed literal unforced sampled replay required')
        for receipt in receipts[1:]:
            if r['input_sha256'].get(str(receipt))!=sha(receipt):raise ValueError('replay uses different waveform or conditional model')
        if not w['completed_boundary_waveforms_available'] or not w['all_saved_native_values_finite'] or not w['PLLOUT_is_observation_only']:raise ValueError('completed finite reference boundary capture required')
        with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+7200):
            for a in [r,w,c]:verify(a['input_sha256']);verify(a['artifacts'])
            columns_file=waveforms/'columns.json';array_file=waveforms/'boundary.npy';bindings_file=conditional/'bindings.json'
            columns=json.loads(columns_file.read_text());bindings=json.loads(bindings_file.read_text())
            index=columns['ordered_physical_ports'].index('PLLOUT')+1
            reference=np.asarray(np.load(array_file,mmap_mode='r')[:,[0,index]])
            rows=np.asarray(read_selected(replay/'replay.raw',{'PLLOUT':bindings['observation_only_ports']['PLLOUT']},260e-9))
            metrics=compare_waveforms(reference,rows);metrics.pop('finer_step_convergence_available',None);metrics.pop('release_ready',None)
            helpers=['common_v3.py','resources.py','compare_keeper_native_timestep.py','assess_selected_detector_phase_probe_v2.py','check_selected_boundary_waveforms.py']
            files=[*receipts,columns_file,array_file,bindings_file,replay/'replay.raw',Path(__file__).resolve(),*[Path(__file__).with_name(n) for n in helpers]];pins={str(p):sha(p) for p in files};verify(pins)
            save(output/'assessment.json',dict(input_sha256=pins,artifacts={},**metrics,completed_replay_and_reference_compared=True,reference_boundary_samples=len(reference),replay_samples=len(rows),sampled_boundary_replay_only=True,independently_predictive_DCO_model=False,conditional_replay_correlation_qualified=False,numerical_timestep_convergence_qualified=False,model_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='completed_TABLEFILE_replay_waveforms_compared',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),native_children_unchanged=True,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['replay','waveforms','conditional','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--wait',action='store_true');a=p.parse_args();run(a.replay.resolve(),a.waveforms.resolve(),a.conditional.resolve(),a.output.resolve(),a.wait)
