"""Compare completed reduced/unreduced replays without assigning a release tolerance."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1')
import argparse,json,time,math
from pathlib import Path
import numpy as np
from common_v3 import save,sha,verify
from resources import lease
from compare_keeper_native_timestep import compare_waveforms
from assess_selected_detector_phase_probe_v2 import read_selected


def compatible(original,reduced):
    for a in [original,reduced]:
        if not a.get('normal_native_replay_complete') or not a.get('all_saved_replay_values_finite') or a.get('PLLOUT_forced') is not False or not a.get('sampled_boundary_replay_only'):
            raise ValueError('normally completed finite unforced replays required')
    if original.get('symbolic_boundary_reduction_used') or reduced.get('symbolic_boundary_reduction_used') is not True:
        raise ValueError('one original and one reduced replay required')
    for field in ['native_executable_sha256','max_step_ps','shared_knot_carrier_used','source_representation']:
        if field not in original or original[field]!=reduced.get(field):raise ValueError('replay conditions differ: '+field)
    if not original.get('literal_samples_preserved') or not reduced.get('literal_aggregated_samples_preserved') or not reduced.get('roundoff_audited_at_source_samples'):
        raise ValueError('original and audited aggregate source representations required')
    return True


def native_wall_seconds(path):
    rows=[line.rsplit(': ',1)[-1].strip() for line in path.read_text().splitlines() if 'Elapsed (wall clock) time' in line]
    if len(rows)!=1:raise ValueError('one native GNU time elapsed measurement required')
    parts=rows[0].split(':')
    if len(parts) not in [2,3]:raise ValueError('GNU time duration format')
    seconds=0.
    for part in parts:seconds=seconds*60+float(part)
    if not math.isfinite(seconds) or seconds<=0:raise ValueError('positive finite native elapsed time required')
    return seconds


def run(original,reduced,conditional,reduction,reference,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29})
    try:
        receipts=[p/'assessment.json' for p in [original,reduced,conditional,reduction,reference]]
        a,b,c,d,r=[json.loads(p.read_text()) for p in receipts];compatible(a,b)
        for receipt in [receipts[2],receipts[4]]:
            if a['input_sha256'].get(str(receipt))!=sha(receipt) or b['input_sha256'].get(str(receipt))!=sha(receipt):raise ValueError('replays use different original model or full reference')
        if b['input_sha256'].get(str(receipts[3]))!=sha(receipts[3]) or d['input_sha256'].get(str(receipts[2]))!=sha(receipts[2]):raise ValueError('reduced replay or reduction source differs')
        pins={str(p):sha(p) for p in [*receipts,conditional/'bindings.json',reduction/'bindings.json',original/'replay.raw',reduced/'replay.raw',original/'memory.log',reduced/'memory.log',Path(__file__).resolve(),Path(__file__).with_name('compare_keeper_native_timestep.py'),Path(__file__).with_name('assess_selected_detector_phase_probe_v2.py')]}
        with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+7200):
            for value in [a,b,c,d,r]:verify(value['input_sha256']);verify(value['artifacts'])
            bindings=[json.loads((p/'bindings.json').read_text()) for p in [conditional,reduction]]
            rows=[np.asarray(read_selected(p/'replay.raw',{'PLLOUT':binding['observation_only_ports']['PLLOUT']},260e-9)) for p,binding in zip([original,reduced],bindings)]
            metrics=compare_waveforms(*rows);metrics.pop('finer_step_convergence_available',None);metrics.pop('release_ready',None)
            elapsed=[native_wall_seconds(p/'memory.log') for p in [original,reduced]]
            if any(t<=0 for t in elapsed):raise ValueError('positive completed elapsed times required')
            verify(pins)
            save(output/'assessment.json',dict(input_sha256=pins,artifacts={},metrics=metrics,completed_reduced_and_original_replays_compared=True,original_native_elapsed_s=elapsed[0],reduced_native_elapsed_s=elapsed[1],observed_runtime_ratio_original_over_reduced=elapsed[0]/elapsed[1],original_peak_RSS_KiB=a['native_peak_RSS_KiB'],reduced_peak_RSS_KiB=b['native_peak_RSS_KiB'],native_elapsed_excludes_resource_queue_wait=True,timing_samples_are_single_runs=True,aggregation_dynamic_error_tolerance_defined=False,aggregation_dynamic_error_qualified=False,changed_controller_prediction_qualified=False,model_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='completed_reduced_replay_comparison',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['original','reduced','conditional','reduction','reference','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['original','reduced','conditional','reduction','reference','output']))
