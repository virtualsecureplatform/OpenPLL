"""Measure early frequency/control stability only in a completed native capture."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1')
import argparse,json,time
from pathlib import Path
import numpy as np
from common_v3 import save,sha,verify
from resources import lease,identity
from assess_selected_detector_phase_probe_v2 import read_selected
from assess_selected_isolated_control import frequency
from assess_keeper_physical_tuning import expected
from extract_keeper_replay_waveforms import completed_reference


def measure(rows,array,records,coarse,fine):
    waveform=np.asarray(rows)
    if waveform.ndim!=2 or waveform.shape[1]!=2 or len(waveform)<3 or not np.isfinite(waveform).all() or waveform[0,0]!=0 or abs(waveform[-1,0]-260e-9)>1e-18 or not np.all(np.diff(waveform[:,0])>0):raise ValueError('complete finite increasing oscillator capture required')
    if array.ndim!=2 or array.shape!=(len(waveform),len(records)+1) or not np.isfinite(array).all() or not np.array_equal(array[:,0],waveform[:,0]):raise ValueError('complete same-grid physical controls required')
    bad=np.zeros(len(array),dtype=bool)
    for i,record in enumerate(records.values(),1):
        high=expected(record['bus'],record['bit'],coarse,fine)
        bad|=~(array[:,i]>=1.44 if high else array[:,i]<=.36)
    invalid=np.flatnonzero(bad);last=int(invalid[-1]) if len(invalid) else None
    first_good=0 if last is None else last+1
    stable_after=float(array[first_good,0]*1e9) if first_good<len(array) else None
    baseline=frequency(rows,200,260);windows=[]
    for start,stop in [(20,60),(40,80),(60,100),(80,120),(100,160),(140,200),(200,260)]:
        try:metrics=dict(frequency_available=True,**frequency(rows,start,stop))
        except ValueError as error:metrics=dict(frequency_available=False,frequency_unavailable_reason=str(error))
        selected=waveform[(waveform[:,0]>=start*1e-9)&(waveform[:,0]<=stop*1e-9),1]
        windows.append(dict(window_ns=[start,stop],**metrics,frequency_difference_from_final_ppm=1e6*(metrics['frequency_mhz']/baseline['frequency_mhz']-1) if metrics['frequency_available'] else None,sampled_minimum_V=float(selected.min()) if len(selected) else None,sampled_maximum_V=float(selected.max()) if len(selected) else None,all_physical_controls_match_at_all_saved_samples=bool(np.all(~bad[(array[:,0]>=start*1e-9)&(array[:,0]<=stop*1e-9)]))))
    return dict(final_window_frequency=baseline,windows=windows,last_mismatching_control_sample_ns=None if last is None else float(array[last,0]*1e9),all_controls_match_from_saved_sample_ns=stable_after,samplewise_control_check_only=True,between_sample_control_behavior_qualified=False,shorter_native_capture_qualified=False,timestep_convergence_qualified=False,other_codes_or_corners_qualified=False,model_qualified=False,release_ready=False)


def run(reference,physical,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{25});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())) )
    try:
        receipts=[p/'assessment.json' for p in [reference,physical]];a,p=[json.loads(q.read_text()) for q in receipts];completed_reference(a)
        if not p['all_macro_and_DCO_tuning_bits_match'] or p['observed_bits']!=302 or p['observed_endpoint_voltages']!=604 or p['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]):raise ValueError('matching completed all-bit physical checks required')
        files=[*receipts,reference/'transient.raw',physical/'controls.npy',physical/'plan.json',Path(__file__).resolve(),*[Path(__file__).with_name(n) for n in ['assess_selected_detector_phase_probe_v2.py','assess_selected_isolated_control.py','assess_keeper_physical_tuning.py','extract_keeper_replay_waveforms.py']]];pins={str(q):sha(q) for q in files}
        save(output/'inputs.json',dict(input_sha256=pins,CPU=25,memory_GiB=2,resource_queue_cap_s=7200,native_simulation_requested=False,release_ready=False));save(output/'status.json',dict(state='waiting_for_global_CPU_RAM_budget',release_ready=False))
        with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+7200):
            for record in [a,p]:verify(record['input_sha256']);verify(record['artifacts'])
            rows=read_selected(reference/'transient.raw',{'PLLOUT':'PLLOUT'},260e-9);controls=np.load(physical/'controls.npy',mmap_mode='r');records=json.loads((physical/'plan.json').read_text())['observations'];result=measure(rows,controls,records,p['coarse'],p['fine']);verify(pins)
            save(output/'assessment.json',dict(input_sha256=pins,artifacts={},**result))
        save(output/'status.json',dict(state='completed_native_early_settling_measured',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','physical','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','physical','output']))
