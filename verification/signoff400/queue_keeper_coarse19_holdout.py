"""Predeclare one independent coarse19 holdout before the diagnostic curve is available."""
import argparse
import json
import os
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from resources import identity
from queue_keeper_coarse19_endpoints import wait_complete, load_point
from run_keeper_native_BSIM_coarse_band import run as capture
from assess_keeper_physical_tuning_v2 import run as physical
from collect_keeper_TT_characterization import characterize


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {22})
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    base = ROOT / 'build/signoff400'
    central = base / 'selected_keeper_corrected_coarse19_fine149_step50_1412'
    central_controls = base / 'selected_keeper_corrected_coarse19_physical_1413'
    endpoints = base / 'selected_keeper_coarse19_parallel_endpoints_1490'
    native = base / 'selected_keeper_coarse19_fine198_step50_1494'
    controls = base / 'selected_keeper_coarse19_fine198_physical_1495'
    try:
        if native.exists() or controls.exists():
            raise FileExistsError('one-shot holdout output exists')
        # This is a prospective holdout, not a relabelled central or endpoint run.
        if ((central / 'assessment.json').exists()
                or (base / 'selected_keeper_coarse19_fine8_step50_1441').exists()
                or (base / 'selected_keeper_coarse19_fine247_step50_1443').exists()):
            raise ValueError('holdout must be declared before central/endpoint results')
        former = base / 'selected_keeper_TT_characterization_1270/fine_182/native'
        former_owner = json.loads((former / 'owner.json').read_text())
        if identity(former_owner['pid']) == former_owner['birth'] or not (former / 'assessment.json').exists():
            raise ValueError('former CPU22 native capture has not completed')
        names = ('queue_keeper_coarse19_holdout.py', 'queue_keeper_coarse19_endpoints.py',
                 'run_keeper_native_BSIM_coarse_band.py', 'assess_keeper_physical_tuning_v2.py',
                 'collect_keeper_TT_characterization.py')
        pins = {str(p): sha(p) for p in [*[Path(__file__).with_name(name) for name in names],
                                       endpoints / 'plan.json', former / 'assessment.json']}
        save(output / 'plan.json', dict(input_sha256=pins, coarse=19, fit_fine_codes=[8, 149, 247],
             independent_holdout_fine=198, primary_interpolation='linear_frequency',
             sensitivity_interpolation='linear_period', target_mhz=400, native_CPU=22,
             native_memory_GiB=16, max_step_ps=50, native_cap_s=86400,
             maximum_additional_native_cases=1, total_band19_campaign_cases_including_central=4,
             central_point_is_not_blind_holdout=True, automatic_identical_retry=False,
             target_extrapolation_forbidden=True, global_interpolation_error_bound_accepted=False,
             other_corners_or_numerical_accuracy_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='waiting_for_completed_central_native_and_physical_point', release_ready=False))
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 86400
        wait_complete(central, deadline)
        wait_complete(central_controls, deadline)
        center = load_point(central, central_controls, 149)
        if center['frequency_mhz'] is None:
            raise ValueError('central point did not establish oscillation')
        verify(pins)
        save(output / 'status.json', dict(state='capturing_predeclared_independent_holdout', release_ready=False))
        capture(base / 'selected_keeper_flat_native_smoke_1210', native, 198, 22, 19, 50)
        physical(native, base / 'selected_keeper_DCO_control_drivers_1233',
                 base / 'selected_keeper_flat_native_model_1208', base / 'selected_keeper_parent_reroute_1136',
                 controls, False, cpu=22)
        held = load_point(native, controls, 198)
        verify(pins)
        save(output / 'status.json', dict(state='waiting_for_completed_fit_endpoints', release_ready=False))
        wait_complete(endpoints, time.clock_gettime(time.CLOCK_BOOTTIME) + 172800)
        e = json.loads((endpoints / 'assessment.json').read_text())
        verify(e['input_sha256'])
        fit = [e['endpoints'][0], e['central'], e['endpoints'][1]]
        if [row['fine'] for row in fit] != [8, 149, 247] or held['fine'] != 198:
            raise ValueError('predeclared fit/holdout roles differ')
        for row in [*fit, held]:
            verify(row['receipt_sha256'])
        def point(row, role):
            if row['frequency_mhz'] is None:
                raise ValueError('all curve points require measured oscillation')
            return dict(fine=row['fine'], frequency_hz=row['frequency_mhz'] * 1e6,
                        role=role, native_assessment=row['native_receipt'], physical_assessment=row['physical_receipt'])
        result = characterize([point(row, 'fit') for row in fit], point(held, 'holdout'))
        verify(pins)
        paths = [endpoints / 'assessment.json', native / 'assessment.json', controls / 'assessment.json']
        save(output / 'assessment.json', dict(input_sha256={**pins, **{str(p): sha(p) for p in paths}},
             **result, coarse=19, corner='tt', temperature_C=27, supply_V=1.8,
             corrected_backend=True, max_step_ps=50, primary_interpolation_predeclared='linear_frequency',
             independent_holdout_roles_preserved=True, target_extrapolation_used=False,
             numerical_accuracy_qualified=False, other_corners_qualified=False,
             changed_controller_prediction_qualified=False, model_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='coarse19_diagnostic_curve_and_holdout_characterized', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
