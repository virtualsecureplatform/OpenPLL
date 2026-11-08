"""One corrected-BSIM reduced replay, after completed native and physical evidence."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1')
import argparse
import json
from pathlib import Path
import time

from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from extract_keeper_replay_waveforms import run as extract, completed_reference
from generate_keeper_aggregate_waveforms import run as aggregate
from stage_keeper_tablefile_sources import run as stage
from benchmark_keeper_corrected_reduced_replay_v2 import run as replay, checked_backend


def wait_completed(directory, state, deadline):
    while True:
        status = json.loads((directory / 'status.json').read_text())
        if status['state'] == state and (directory / 'assessment.json').exists():
            return
        if status['state'] == 'stopped_without_qualification':
            raise RuntimeError('prerequisite stopped: ' + str(directory))
        owner = json.loads((directory / 'owner.json').read_text())
        if identity(owner['pid']) != owner['birth']:
            raise RuntimeError('prerequisite owner missing without completion: ' + str(directory))
        if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            raise TimeoutError('completed-reference observation deadline')
        time.sleep(10)


def checked(path):
    value = json.loads(path.read_text())
    verify(value['input_sha256'])
    verify(value['artifacts'])
    return value


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {25})
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())) )
    base = ROOT / 'build/signoff400'
    reference = base / 'selected_keeper_corrected_BSIM_fine149_1295'
    physical = base / 'selected_keeper_corrected_BSIM_physical_1296'
    conditional = base / 'selected_keeper_receiver_native_1419'
    reduction = base / 'selected_keeper_receiver_reduction_1420'
    plan = base / 'selected_keeper_receiver_replay_plan_1422'
    waves = base / 'selected_keeper_corrected_receiver_waveforms_1467'
    weighted = base / 'selected_keeper_corrected_receiver_aggregate_1468'
    staging = base / 'selected_keeper_corrected_receiver_sources_1469'
    native = base / 'selected_keeper_corrected_receiver_replay_1470'
    controls = base / 'selected_capacitor_boundary_superposition_fine_step_controls_1398'
    names = ('queue_keeper_corrected_reduced_pipeline_v2.py', 'benchmark_keeper_corrected_reduced_replay_v2.py',
             'extract_keeper_replay_waveforms.py', 'generate_keeper_aggregate_waveforms.py',
             'aggregate_keeper_boundary_waveforms.py', 'stage_keeper_tablefile_sources.py',
             'write_keeper_shared_tablefile_sources.py', 'write_keeper_tablefile_sources.py')
    try:
        if any(p.exists() for p in (waves, weighted, staging, native)):
            raise FileExistsError('one-shot pipeline output exists; no retry or overwrite')
        for directory in (conditional, reduction, plan, controls):
            checked(directory / 'assessment.json')
        ri = json.loads((reference / 'inputs.json').read_text())
        binary = ROOT / 'build/tools/xyce_umfpack_BSIM_junction_1292/Xyce'
        checked_backend(ri, sha(binary))
        if ((ri['corner'], ri['temperature_C'], ri['supply_V'], ri['coarse'], ri['fine'],
             ri['max_step_ps'], ri['simulation_ns']) != ('tt', 27, 1.8, 20, 149, 10, 260)
                or ri['all_node_voltages_requested'] is not True):
            raise ValueError('predeclared corrected TT 10 ps reference required')
        paths = [Path(__file__).with_name(n) for n in names]
        paths += [reference / 'inputs.json', physical / 'plan.json', binary]
        paths += [p / 'assessment.json' for p in (conditional, reduction, plan, controls)]
        pins = {str(p): sha(p) for p in paths}
        save(output / 'inputs.json', dict(input_sha256=pins, reference=str(reference),
             physical=str(physical), native_output=str(native), max_step_ps=10,
             maximum_additional_native_cases=1, native_memory_GiB=8, native_CPU=25,
             preparation_CPU=29, observation_cap_s=172800, native_cap_s=86400,
             automatic_identical_retry=False, original_jobs_modified=False,
             full_reference_waveform_read_before_completion=False, release_ready=False))
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 172800
        save(output / 'status.json', dict(state='waiting_for_completed_corrected_reference', release_ready=False))
        wait_completed(reference, 'flat_native_programming_transient_complete', deadline)
        a = checked(reference / 'assessment.json')
        completed_reference(a)
        checked_backend(a, sha(binary))
        verify(pins)
        save(output / 'status.json', dict(state='waiting_for_all_604_physical_controls', release_ready=False))
        wait_completed(physical, 'physical_tuning_voltage_assessment_complete', deadline)
        p = checked(physical / 'assessment.json')
        if (p['input_sha256'].get(str(reference / 'assessment.json')) != sha(reference / 'assessment.json')
                or p.get('all_macro_and_DCO_tuning_bits_match') is not True
                or p['observed_bits'] != 302 or p['observed_endpoint_voltages'] != 604
                or (p['coarse'], p['fine']) != (20, 149)):
            raise ValueError('same completed native capture and all physical controls required')
        save(output / 'status.json', dict(state='extracting_completed_reference_boundaries', release_ready=False))
        with lease(1, 8, time.clock_gettime(time.CLOCK_BOOTTIME) + 86400):
            extract(reference, plan, waves)
        verify(pins)
        save(output / 'status.json', dict(state='aggregating_exact_boundary_samples', release_ready=False))
        aggregate(waves, reduction, controls, weighted)
        verify(pins)
        save(output / 'status.json', dict(state='staging_verified_shared_knot_sources', release_ready=False))
        stage(weighted, staging, shared_knots=True)
        verify(pins)
        save(output / 'status.json', dict(state='running_one_corrected_10ps_replay', release_ready=False))
        replay(reference, conditional, plan, physical, waves, reduction, weighted, staging, native)
        verify(pins)
        receipts = [p / 'assessment.json' for p in (reference, physical, waves, weighted, staging, native)]
        save(output / 'assessment.json', dict(input_sha256=pins,
             artifacts={str(p): sha(p) for p in receipts}, corrected_10ps_reduced_replay_complete=True,
             original_jobs_modified=False, downstream_environment_still_prescribed=True,
             changed_controller_prediction_qualified=False, model_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='corrected_reduced_replay_complete_unqualified', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
