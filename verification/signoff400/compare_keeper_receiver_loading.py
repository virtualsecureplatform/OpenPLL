"""Compare completed first-clamped and expanded-receiver conditional replays."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1')
import argparse
import json
import time
from pathlib import Path
import numpy as np
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compare_keeper_native_timestep import compare_waveforms
from compare_keeper_reduced_replay import native_wall_seconds
from assess_selected_detector_phase_probe_v2 import read_selected


def compatible(a, b):
    for value in [a, b]:
        for field in ['normal_native_replay_complete', 'all_saved_replay_values_finite', 'all_completed_native_outputs_copy_verified', 'all_physical_tuning_controls_correct', 'symbolic_boundary_reduction_used', 'literal_aggregated_samples_preserved', 'roundoff_audited_at_source_samples']:
            if value.get(field) is not True:
                raise ValueError('completed checked reduced replays required: ' + field)
        if value.get('PLLOUT_forced') is not False:
            raise ValueError('PLLOUT must remain unforced')
    for field in ['native_executable_sha256', 'max_step_ps', 'shared_knot_carrier_used', 'source_representation']:
        if field not in a or a[field] != b.get(field):
            raise ValueError('replay conditions differ: ' + field)


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {29})
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    b = ROOT / 'build/signoff400'
    original = b / 'selected_keeper_aggregate_replay_1403'
    candidate = b / 'selected_keeper_receiver_replay_1427'
    pipeline = b / 'selected_keeper_receiver_replay_pipeline_1424'
    reductions = [b / 'selected_keeper_capacitor_boundary_reduction_1383', b / 'selected_keeper_receiver_reduction_1420']
    reference = b / 'selected_keeper_fine149_step50_1278/assessment.json'
    physical = b / 'selected_keeper_step50_physical_1279/assessment.json'
    expansion = b / 'selected_keeper_receiver_expansion_1416/assessment.json'
    try:
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 86400
        save(output / 'status.json', dict(state='waiting_for_completed_receiver_loading_replay', release_ready=False))
        while not (candidate / 'assessment.json').exists():
            state = json.loads((pipeline / 'status.json').read_text())['state']
            if state == 'stopped_without_qualification':
                raise RuntimeError('receiver producer stopped')
            owner = json.loads((pipeline / 'owner.json').read_text())
            if identity(owner['pid']) != owner['birth']:
                raise RuntimeError('receiver producer missing without completed replay')
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('completed receiver observation deadline')
            time.sleep(10)
        receipts = [p / 'assessment.json' for p in [original, candidate]]
        values = [json.loads(p.read_text()) for p in receipts]
        compatible(*values)
        for value, reduction in zip(values, reductions):
            for path in [reference, physical, reduction / 'assessment.json']:
                if value['input_sha256'].get(str(path)) != sha(path):
                    raise ValueError('same full reference, physical code and declared reduction required')
        ex = json.loads(expansion.read_text())
        if ex.get('receiver_no_longer_prescribed') is not True or ex.get('previous_internal_unknowns_preserved') is not True:
            raise ValueError('checked receiver expansion required')
        files = [*receipts, reference, physical, expansion, Path(__file__).resolve(), Path(__file__).with_name('compare_keeper_native_timestep.py'), Path(__file__).with_name('compare_keeper_reduced_replay.py')]
        files += [p / name for p in [original, candidate] for name in ['replay.raw', 'memory.log']]
        files += [p / name for p in reductions for name in ['assessment.json', 'bindings.json']]
        pins = {str(p): sha(p) for p in files}
        with lease(1, 2, time.clock_gettime(time.CLOCK_BOOTTIME) + 7200):
            for value in [*values, ex]:
                verify(value['input_sha256'])
                verify(value['artifacts'])
            rows = []
            for replay, reduction in zip([original, candidate], reductions):
                binding = json.loads((reduction / 'bindings.json').read_text())
                rows.append(np.asarray(read_selected(replay / 'replay.raw', {'PLLOUT': binding['observation_only_ports']['PLLOUT']}, 260e-9)))
            result = compare_waveforms(*rows)
            result.pop('finer_step_convergence_available', None)
            result.pop('release_ready', None)
            verify(pins)
            save(output / 'assessment.json', dict(input_sha256=pins, metrics=result, native_elapsed_s=[native_wall_seconds(p / 'memory.log') for p in [original, candidate]], peak_RSS_KiB=[v['native_peak_RSS_KiB'] for v in values], same_completed_reference_and_physical_code=True, receiver_boundary_moved_downstream=True, downstream_environment_still_prescribed=True, receiver_loading_error_tolerance_defined=False, numerical_accuracy_qualified=False, changed_controller_prediction_qualified=False, model_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='completed_receiver_loading_comparison', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    run(a.output.resolve())
