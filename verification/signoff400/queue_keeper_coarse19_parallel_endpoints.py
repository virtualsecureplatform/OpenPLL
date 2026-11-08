"""Run the same two predeclared endpoints on separate cores after central checks."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from common_v3 import ROOT, save, sha, verify
from resources import identity
from queue_keeper_coarse19_endpoints import wait_complete, load_point
from run_keeper_native_BSIM_coarse_band import run as capture
from assess_keeper_physical_tuning_v2 import run as physical


def cases():
    b = ROOT / 'build/signoff400'
    return [(8, 20, b / 'selected_keeper_coarse19_fine8_step50_1441', b / 'selected_keeper_coarse19_fine8_physical_1442'),
            (247, 21, b / 'selected_keeper_coarse19_fine247_step50_1443', b / 'selected_keeper_coarse19_fine247_physical_1444')]


def worker(output, fine):
    row = next(row for row in cases() if row[0] == fine)
    _, cpu, native, controls = row
    record = output / f'worker_{fine}.json'
    if record.exists() or native.exists() or controls.exists():
        raise FileExistsError('one-shot endpoint worker refuses existing output')
    save(record, dict(pid=os.getpid(), birth=identity(os.getpid()), fine=fine, CPU=cpu, state='starting'))
    pins = json.loads((output / 'plan.json').read_text())['input_sha256']
    try:
        verify(pins)
        b = ROOT / 'build/signoff400'
        capture(b / 'selected_keeper_flat_native_smoke_1210', native, fine, cpu, 19, 50)
        verify(pins)
        physical(native, b / 'selected_keeper_DCO_control_drivers_1233', b / 'selected_keeper_flat_native_model_1208',
                 b / 'selected_keeper_parent_reroute_1136', controls, False, cpu=cpu)
        result = load_point(native, controls, fine)
        verify(pins)
        save(output / f'result_{fine}.json', result)
        save(record, dict(pid=os.getpid(), birth=identity(os.getpid()), fine=fine, CPU=cpu, state='complete'))
    except BaseException as error:
        save(record, dict(pid=os.getpid(), birth=identity(os.getpid()), fine=fine, CPU=cpu,
                         state='stopped_without_qualification', reason=repr(error)))
        raise


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {21})
    os.environ.update(OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1', OPENBLAS_NUM_THREADS='1')
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    b = ROOT / 'build/signoff400'
    central = b / 'selected_keeper_corrected_coarse19_fine149_step50_1412'
    controls = b / 'selected_keeper_corrected_coarse19_physical_1413'
    handoff = b / 'selected_keeper_endpoint_parallel_handoff_1489.json'
    try:
        h = json.loads(handoff.read_text())
        verify(h['input_sha256'])
        if (h.get('old_coordinator_retired_before_any_endpoint') is not True
                or identity(h['old_owner']['pid']) == h['old_owner']['birth']):
            raise ValueError('exclusive handoff from retired waiting coordinator required')
        if any(path.exists() for _, _, native, physical_dir in cases() for path in (native, physical_dir)):
            raise FileExistsError('endpoint output exists; no duplicate or retry')
        names = ('queue_keeper_coarse19_parallel_endpoints.py', 'queue_keeper_coarse19_endpoints.py',
                 'run_keeper_native_BSIM_coarse_band.py', 'assess_keeper_physical_tuning_v2.py')
        pins = {str(p): sha(p) for p in [handoff, *[Path(__file__).with_name(name) for name in names]]}
        save(output / 'plan.json', dict(input_sha256=pins, coarse=19, endpoint_fine_codes=[8, 247],
             native_CPUs=[20, 21], native_memory_GiB_per_worker=16, max_simultaneous_workers=2,
             maximum_additional_native_cases=2, native_cap_s_per_case=86400, max_step_ps=50,
             same_original_endpoint_output_paths=True, global_CPU_RAM_budget_enforced=True,
             central_point_is_not_blind_holdout=True, automatic_identical_retry=False, release_ready=False))
        save(output / 'status.json', dict(state='waiting_for_completed_central_native_and_physical_point', release_ready=False))
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 86400
        wait_complete(central, deadline)
        wait_complete(controls, deadline)
        center = load_point(central, controls, 149)
        if center['frequency_mhz'] is None:
            raise ValueError('central point did not establish oscillation')
        verify(pins)
        children = []
        for fine, cpu, _, _ in cases():
            log = (output / f'worker_{fine}.log').open('x')
            child = subprocess.Popen([sys.executable, Path(__file__).resolve(), '--output', output, '--worker', str(fine)],
                                     stdout=log, stderr=subprocess.STDOUT)
            log.close()
            children.append((fine, child))
        save(output / 'workers.json', dict(workers=[dict(fine=fine, pid=child.pid, birth=identity(child.pid))
                                                    for fine, child in children]))
        save(output / 'status.json', dict(state='running_two_predeclared_endpoints', release_ready=False))
        # Always observe both workers to termination; an endpoint failure neither
        # retries that case nor leaves the other native worker unobserved.
        codes = {fine: child.wait() for fine, child in children}
        if any(codes.values()):
            raise RuntimeError('endpoint worker failure: ' + repr(codes))
        results = [json.loads((output / f'result_{fine}.json').read_text()) for fine, _, _, _ in cases()]
        for result in results:
            verify(result['receipt_sha256'])
        verify(pins)
        low, high = [r['frequency_mhz'] for r in results]
        bracket = low is not None and high is not None and low < high and low <= 400 <= high
        save(output / 'assessment.json', dict(input_sha256=pins, endpoints=results, central=center,
             measured_50ps_same_band_target_bracket=bracket, parallel_schedule_used=True,
             band_auto_selected=False, central_point_is_not_blind_holdout=True, interpolation_qualified=False,
             numerical_accuracy_qualified=False, changed_controller_prediction_qualified=False,
             model_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='diagnostic_endpoint_captures_complete', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--worker', type=int, choices=[8, 247])
    args = parser.parse_args()
    if args.worker is None:
        run(args.output.resolve())
    else:
        worker(args.output.resolve(), args.worker)
