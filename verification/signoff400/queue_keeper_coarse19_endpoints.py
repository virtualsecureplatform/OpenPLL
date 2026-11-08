"""Predeclare two diagnostic safe-range endpoints after a checked central capture."""
import argparse
import json
import math
import os
import time
from pathlib import Path
from common_v3 import ROOT, save, sha, verify
from resources import identity
from run_keeper_native_BSIM_coarse_band import run as capture
from assess_keeper_physical_tuning_v2 import run as physical

BACKEND = '84ba37cb0e3c405e084b1e210a35f0f492f03b7c94d2c1f9ef284b56121db12a'


def checked_point(native, controls, fine):
    if native.get('normal_native_completion') is not True or native.get('all_saved_native_values_finite') is not True or native.get('stationary_requested_code') is not True:
        raise ValueError('normal finite stationary native point required')
    if native.get('native_executable_sha256') != BACKEND or native.get('BSIM_PBSWGD_default_corrected') is not True:
        raise ValueError('corrected backend required')
    if (native.get('requested_coarse'), native.get('requested_fine'), native.get('max_step_ps')) != (19, fine, 50):
        raise ValueError('declared coarse19/fine/50ps point required')
    if controls.get('all_macro_and_DCO_tuning_bits_match') is not True or controls.get('mismatched_endpoints') != 0 or controls.get('observed_bits') != 302 or controls.get('observed_endpoint_voltages') != 604 or (controls.get('coarse'), controls.get('fine')) != (19, fine):
        raise ValueError('complete matching physical controls required')
    frequency = native.get('frequency_diagnostic')
    if frequency is None:
        return None
    value = frequency['frequency_mhz']
    if not math.isfinite(value) or value <= 0:
        raise ValueError('positive finite completed frequency required')
    return value


def wait_complete(directory, deadline):
    while not (directory / 'assessment.json').exists():
        state = json.loads((directory / 'status.json').read_text())['state']
        if state == 'stopped_without_qualification':
            raise RuntimeError('prerequisite stopped: ' + str(directory))
        owner = json.loads((directory / 'owner.json').read_text())
        if identity(owner['pid']) != owner['birth']:
            raise RuntimeError('prerequisite owner missing: ' + str(directory))
        if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            raise TimeoutError('central-capture observation deadline')
        time.sleep(10)


def load_point(native, controls, fine):
    nr, pr = native / 'assessment.json', controls / 'assessment.json'
    n, p = [json.loads(f.read_text()) for f in [nr, pr]]
    ci = native / 'inputs.json'
    domain = json.loads(ci.read_text())
    if (domain.get('corner'),domain.get('temperature_C'),domain.get('supply_V'),domain.get('coarse'),domain.get('fine'),domain.get('max_step_ps'),domain.get('simulation_ns')) != ('tt',27,1.8,19,fine,50,260):
        raise ValueError('same declared TT operating domain required')
    if p['input_sha256'].get(str(ci)) != sha(ci):
        raise ValueError('physical controls must bind the native operating domain')
    for value in [n, p]:
        verify(value['input_sha256'])
        verify(value['artifacts'])
    if p['input_sha256'].get(str(nr)) != sha(nr):
        raise ValueError('physical receipt belongs to another native result')
    return dict(fine=fine, frequency_mhz=checked_point(n, p, fine), native_receipt=str(nr), physical_receipt=str(pr), receipt_sha256={str(f): sha(f) for f in [nr, pr]})


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {20})
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    b = ROOT / 'build/signoff400'
    central = b / 'selected_keeper_corrected_coarse19_fine149_step50_1412'
    central_physical = b / 'selected_keeper_corrected_coarse19_physical_1413'
    cases = [(8, b / 'selected_keeper_coarse19_fine8_step50_1441', b / 'selected_keeper_coarse19_fine8_physical_1442'), (247, b / 'selected_keeper_coarse19_fine247_step50_1443', b / 'selected_keeper_coarse19_fine247_physical_1444')]
    names = ['queue_keeper_coarse19_endpoints.py', 'run_keeper_native_BSIM_coarse_band.py', 'assess_keeper_physical_tuning_v2.py']
    pins = {str(Path(__file__).with_name(n)): sha(Path(__file__).with_name(n)) for n in names}
    save(output / 'plan.json', dict(input_sha256=pins, coarse=19, endpoint_fine_codes=[8, 247], existing_central_fine=149, central_point_is_not_blind_holdout=True, max_step_ps=50, native_CPU=20, native_memory_GiB=16, maximum_additional_native_cases=2, sequential_cases=True, automatic_identical_retry=False, band_auto_selected=False, timestep_accuracy_qualified=False, release_ready=False))
    try:
        if any(p.exists() for _, native, physical_dir in cases for p in [native, physical_dir]):
            raise ValueError('endpoint output exists; no automatic retry')
        save(output / 'status.json', dict(state='waiting_for_completed_central_native_and_physical_point', release_ready=False))
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 86400
        wait_complete(central, deadline)
        wait_complete(central_physical, deadline)
        center = load_point(central, central_physical, 149)
        if center['frequency_mhz'] is None:
            raise ValueError('central diagnostic did not establish oscillation; endpoint plan stopped')
        verify(pins)
        results = []
        for fine, native, controls in cases:
            save(output / 'status.json', dict(state='running_predeclared_endpoint', fine=fine, release_ready=False))
            capture(b / 'selected_keeper_flat_native_smoke_1210', native, fine, 20, 19, 50)
            verify(pins)
            physical(native, b / 'selected_keeper_DCO_control_drivers_1233', b / 'selected_keeper_flat_native_model_1208', b / 'selected_keeper_parent_reroute_1136', controls, False, cpu=20)
            verify(pins)
            results.append(load_point(native, controls, fine))
        low, high = [r['frequency_mhz'] for r in results]
        bracket = low is not None and high is not None and low < high and low <= 400 <= high
        save(output / 'assessment.json', dict(input_sha256=pins, endpoints=results, central=center, measured_50ps_same_band_target_bracket=bracket, band_auto_selected=False, central_point_is_not_blind_holdout=True, interpolation_qualified=False, numerical_accuracy_qualified=False, changed_controller_prediction_qualified=False, model_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='diagnostic_endpoint_captures_complete', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    run(a.output.resolve())
