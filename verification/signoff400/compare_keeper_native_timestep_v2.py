"""Compare completed full native 10 ps and finer/coarser controls; never promote numerical accuracy."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1')
import argparse,json,time
from pathlib import Path
import numpy as np
from common_v3 import save,sha,verify
from resources import lease,identity
from extract_keeper_replay_waveforms import extract,completed_reference
from assess_selected_detector_phase_probe_v2 import transitions

from compare_keeper_native_timestep import compare_waveforms

def run(reference,candidate,reference_physical,candidate_physical,output,wait,candidate_step_ps):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{30})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    paths=[reference,candidate,reference_physical,candidate_physical]
    helpers=['common_v3.py','resources.py','extract_keeper_replay_waveforms.py','plan_keeper_conditional_replay.py','assess_selected_detector_phase_probe_v2.py','compare_keeper_native_timestep.py']
    pins={str(p):sha(p)for p in [Path(__file__).resolve(),*[Path(__file__).with_name(n)for n in helpers]]}
    save(output/'inputs.json',dict(input_sha256=pins,reference=str(reference),candidate=str(candidate),reference_physical=str(reference_physical),candidate_physical=str(candidate_physical),candidate_step_ps=candidate_step_ps,observation_cap_s=172800,automatic_identical_retry=False,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+172800
    try:
        while True:
            pending=[]
            for i,folder in enumerate(paths):
                state=json.loads((folder/'status.json').read_text())['state']
                terminal='flat_native_programming_transient_complete' if i<2 else 'physical_tuning_voltage_assessment_complete'
                if state==terminal and (folder/'assessment.json').exists():continue
                if state=='stopped_without_qualification':raise RuntimeError('a comparison input stopped without qualification')
                owner=json.loads((folder/'owner.json').read_text())
                if identity(owner['pid'])!=owner['birth']:raise RuntimeError('input owner gone without completed receipt')
                pending.append(dict(path=str(folder),state=state))
            if not pending:break
            if not wait:raise RuntimeError('comparison inputs still running')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observation deadline; native children unchanged')
            save(output/'status.json',dict(state='waiting_for_completed_timestep_controls',pending=pending,release_ready=False));time.sleep(10)
        assessments=[p/'assessment.json' for p in paths];records=[json.loads(p.read_text())for p in assessments]
        for a in records:verify(a['input_sha256']);verify(a['artifacts'])
        for a in records[:2]:completed_reference(a)
        for i in range(2):
            p=records[i+2]
            if p['input_sha256'].get(str(assessments[i]))!=sha(assessments[i]) or not p['all_macro_and_DCO_tuning_bits_match'] or p['observed_bits']!=302 or p['observed_endpoint_voltages']!=604 or (p['coarse'],p['fine'])!=(20,149):raise ValueError('matching physical tuning validation required')
        ri,ci=[json.loads((p/'inputs.json').read_text())for p in paths[:2]]
        for a,step in [(ri,10),(ci,candidate_step_ps)]:
            if (a['coarse'],a['fine'],a['corner'],a['temperature_C'],a['supply_V'],a['max_step_ps'])!=(20,149,'tt',27,1.8,step):raise ValueError('one declared timestep fine149 TT pair required')
        rd,cd=[p/'transient.spice'for p in paths[:2]]
        expected=rd.read_text().replace(str(reference/'transient.raw'),str(candidate/'transient.raw'))
        if expected.splitlines().count('.tran 10p 260n 0 10p')!=1 or expected.replace('.tran 10p 260n 0 10p',f'.tran 10p 260n 0 {candidate_step_ps}p')!=cd.read_text():raise ValueError('decks differ beyond output path and maximum timestep')
        pins.update({str(p):sha(p)for p in [*assessments,rd,cd,*[d/'inputs.json'for d in paths[:2]]]})
        artifacts={};arrays=[];capture=[]
        save(output/'status.json',dict(state='comparing_completed_timestep_controls',release_ready=False))
        with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+7200):
            for name,folder,record in zip(['reference','candidate'],paths[:2],records[:2]):
                raw=folder/'transient.raw'
                if str(raw)not in record['artifacts']:raise ValueError('completed RAW hash required')
                pins[str(raw)]=record['artifacts'][str(raw)];target=output/(name+'.npy')
                capture.append(extract(raw,{'PLLOUT':dict(role='observation_only',expected_RAW_variable='V(PLLOUT)')},target,260e-9))
                arrays.append(np.load(target,mmap_mode='r'));artifacts[str(target)]=sha(target)
            metrics=compare_waveforms(*arrays);metrics.pop('finer_step_convergence_available');metrics.update(finer_step_control_compared=candidate_step_ps<10,numerical_convergence_qualified=False,candidate_max_step_ps=candidate_step_ps,reference_max_step_ps=10)
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,**metrics,
            captures=capture,electrical_deck_only_max_step_changed=True,all_physical_tuning_controls_correct=True,
            reference_capture_elapsed_s=records[0]['elapsed_s'],candidate_capture_elapsed_s=records[1]['elapsed_s'],
            capture_elapsed_ratio=records[0]['elapsed_s']/records[1]['elapsed_s'],
            runtime_scope='controller elapsed through capture validation; includes output and postprocessing, not isolated solver time',
            model_qualified=False));save(output/'status.json',dict(state='native_timestep_diagnostics_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),native_children_unchanged=True,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','candidate','reference-physical','candidate-physical','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--candidate-step-ps',type=int,choices=[5,50],required=True);p.add_argument('--wait',action='store_true');a=p.parse_args();run(a.reference.resolve(),a.candidate.resolve(),a.reference_physical.resolve(),a.candidate_physical.resolve(),a.output.resolve(),a.wait,a.candidate_step_ps)
