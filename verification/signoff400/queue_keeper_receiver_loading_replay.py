"""One bounded expanded-receiver loading comparison using a completed full capture."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1')
import argparse
import json
import time
from pathlib import Path
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from plan_keeper_conditional_replay import run as plan
from extract_keeper_replay_waveforms import run as extract
from generate_keeper_aggregate_waveforms import run as aggregate
from stage_keeper_tablefile_sources import run as stage
from benchmark_keeper_aggregated_tablefile_replay_v2 import run as replay


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {29})
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    b = ROOT / 'build/signoff400'
    conditional = b / 'selected_keeper_receiver_native_1419'
    reduction = b / 'selected_keeper_receiver_reduction_1420'
    reference = b / 'selected_keeper_fine149_step50_1278'
    physical = b / 'selected_keeper_step50_physical_1279'
    ports = b / 'selected_keeper_receiver_replay_plan_1422'
    waves = b / 'selected_keeper_receiver_waveforms_1423'
    weighted = b / 'selected_keeper_receiver_aggregate_waveforms_1425'
    staging = b / 'selected_keeper_receiver_sources_1426'
    native = b / 'selected_keeper_receiver_replay_1427'
    names = ['queue_keeper_receiver_loading_replay.py', 'plan_keeper_conditional_replay.py', 'extract_keeper_replay_waveforms.py', 'generate_keeper_aggregate_waveforms.py', 'aggregate_keeper_boundary_waveforms.py', 'stage_keeper_tablefile_sources.py', 'benchmark_keeper_aggregated_tablefile_replay_v2.py']
    pins = {str(Path(__file__).with_name(name)): sha(Path(__file__).with_name(name)) for name in names}
    save(output / 'inputs.json', dict(input_sha256=pins, reference=str(reference), conditional=str(conditional), reduction=str(reduction), maximum_native_PLL_cases=1, native_cap_s=14400, automatic_identical_retry=False, old_backend_loading_comparison_only=True, changed_controller_prediction_qualified=False, release_ready=False))
    try:
        if any(p.exists() for p in [ports, waves, weighted, staging, native]):
            raise ValueError('output already exists; no automatic retry')
        save(output / 'status.json', dict(state='binding_expanded_receiver_to_full_model', release_ready=False))
        with lease(1, 8, time.clock_gettime(time.CLOCK_BOOTTIME) + 7200):
            plan(conditional, b / 'selected_keeper_flat_native_model_1208', ports)
            verify(pins)
            save(output / 'status.json', dict(state='extracting_completed_full_capture_boundaries', release_ready=False))
            extract(reference, ports, waves)
            verify(pins)
        save(output / 'status.json', dict(state='aggregating_expanded_receiver_forcing', release_ready=False))
        aggregate(waves, reduction, b / 'selected_capacitor_boundary_superposition_fine_step_controls_1398', weighted)
        verify(pins)
        save(output / 'status.json', dict(state='staging_expanded_receiver_sources', release_ready=False))
        stage(weighted, staging, shared_knots=True)
        verify(pins)
        save(output / 'status.json', dict(state='running_one_expanded_receiver_replay', release_ready=False))
        replay(reference, conditional, ports, physical, waves, reduction, weighted, staging, native)
        verify(pins)
        receipts = [p / 'assessment.json' for p in [ports, waves, weighted, staging, native]]
        save(output / 'assessment.json', dict(input_sha256=pins, artifacts={str(p): sha(p) for p in receipts}, expanded_receiver_replay_complete=True, downstream_environment_still_prescribed=True, changed_controller_prediction_qualified=False, model_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='expanded_receiver_replay_complete_unqualified', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    run(a.output.resolve())
