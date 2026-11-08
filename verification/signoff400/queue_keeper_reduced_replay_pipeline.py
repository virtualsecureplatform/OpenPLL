"""One-shot completed-input staging, reduced replay and comparison follow-up."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1')
import argparse,json,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity
from stage_keeper_tablefile_sources import run as stage
from benchmark_keeper_aggregated_tablefile_replay import run as replay
from compare_keeper_reduced_replay import run as compare


def completed(directory,expected,deadline):
    while True:
        state=json.loads((directory/'status.json').read_text())['state']
        if state==expected and (directory/'assessment.json').exists():return
        if state=='stopped_without_qualification':raise RuntimeError('prerequisite stopped: '+str(directory))
        owner=json.loads((directory/'owner.json').read_text())
        if identity(owner['pid'])!=owner['birth']:raise RuntimeError('prerequisite owner missing: '+str(directory))
        if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('pipeline observation deadline')
        time.sleep(10)


def run(output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));b=ROOT/'build/signoff400'
    waveform=b/'selected_keeper_aggregate_waveforms_1385';staging=b/'selected_keeper_aggregate_sources_1389';target=b/'selected_keeper_aggregate_replay_1390';comparison=b/'selected_keeper_aggregate_comparison_1391';original=b/'selected_keeper_shared_TABLEFILE_replay_1380'
    names=['queue_keeper_reduced_replay_pipeline.py','stage_keeper_tablefile_sources.py','write_keeper_shared_tablefile_sources.py','write_keeper_tablefile_sources.py','benchmark_keeper_aggregated_tablefile_replay.py','compare_keeper_reduced_replay.py']
    pins={str(Path(__file__).with_name(n)):sha(Path(__file__).with_name(n)) for n in names}
    save(output/'inputs.json',dict(input_sha256=pins,maximum_native_PLL_cases=1,automatic_identical_retry=False,observation_cap_s=86400,staging=str(staging),replay=str(target),comparison=str(comparison),release_ready=False))
    try:
        if any(p.exists() for p in [staging,target,comparison]):raise ValueError('pipeline output already exists; no automatic retry')
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+86400
        save(output/'status.json',dict(state='waiting_for_completed_audited_aggregate_waveforms',release_ready=False));completed(waveform,'audited_weighted_samples_complete_native_unqualified',deadline);verify(pins)
        save(output/'status.json',dict(state='staging_verified_aggregate_sources',release_ready=False));stage(waveform,staging,shared_knots=True);verify(pins)
        save(output/'status.json',dict(state='running_one_bounded_aggregate_replay',release_ready=False))
        replay(b/'selected_keeper_fine149_step50_1278',b/'selected_keeper_conditional_native_1242',b/'selected_keeper_conditional_replay_plan_1243',b/'selected_keeper_step50_physical_1279',b/'selected_keeper_replay_memory_benchmark_1365/waveforms',b/'selected_keeper_capacitor_boundary_reduction_1383',waveform,staging,target);verify(pins)
        save(output/'status.json',dict(state='waiting_for_completed_original_replay_comparison',release_ready=False));completed(original,'conditional_native_replay_complete',deadline)
        compare(original,target,b/'selected_keeper_conditional_native_1242',b/'selected_keeper_capacitor_boundary_reduction_1383',b/'selected_keeper_fine149_step50_1278',comparison);verify(pins)
        receipts=[p/'assessment.json' for p in [staging,target,comparison]]
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in receipts},completed_reduced_replay_pipeline=True,model_qualified=False,release_ready=False));save(output/'status.json',dict(state='reduced_replay_pipeline_complete_unqualified',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),existing_native_jobs_unchanged=True,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
