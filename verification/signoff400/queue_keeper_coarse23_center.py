"""Measure one new coarse-band center; local trend selects an experiment, not a model."""
import argparse
import json
import math
import os
from pathlib import Path
import re
from common_v3 import ROOT, save, sha, verify
from resources import identity
from run_keeper_native_BSIM_coarse_band import run as capture
from assess_keeper_physical_tuning_v2 import run as physical

BACKEND = '84ba37cb0e3c405e084b1e210a35f0f492f03b7c94d2c1f9ef284b56121db12a'


def normalized_deck(text):
    count = 0
    rows = []
    for line in text.splitlines():
        if re.fullmatch(r'Vbias\d+ STARTUP_COARSE\[[0-5]\] 0 (0|1\.8)', line):
            count += 1
            line = line.rsplit(' ',1)[0] + ' COARSE_BIT'
        line = re.sub(r'file=\S+/transient\.raw', 'file=TRANSIENT_RAW', line)
        rows.append(line)
    if count != 6:
        raise ValueError('six coarse startup sources required')
    return '\n'.join(rows)


def checked_frequency(native, controls, coarse):
    if (native.get('normal_native_completion') is not True
            or native.get('all_saved_native_values_finite') is not True
            or native.get('stationary_requested_code') is not True
            or native.get('native_executable_sha256') != BACKEND
            or native.get('BSIM_PBSWGD_default_corrected') is not True
            or native.get('max_step_ps') != 50
            or native.get('codes') != {'COARSE_CODE':[coarse],'DCO_CODE':[149]}):
        raise ValueError('completed corrected stationary 50 ps center required')
    if (controls.get('all_macro_and_DCO_tuning_bits_match') is not True
            or controls.get('mismatched_endpoints') != 0
            or controls.get('observed_bits') != 302
            or controls.get('observed_endpoint_voltages') != 604
            or (controls.get('coarse'),controls.get('fine')) != (coarse,149)):
        raise ValueError('all matching physical tuning endpoints required')
    f = native.get('frequency_diagnostic', {}).get('frequency_mhz')
    if type(f) not in (int,float) or not math.isfinite(f) or f <= 0:
        raise ValueError('positive finite measured frequency required')
    return f


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{18})
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    save(output / 'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    base = ROOT / 'build/signoff400'
    native = base / 'selected_keeper_corrected_coarse23_fine149_step50_1513'
    controls = base / 'selected_keeper_corrected_coarse23_physical_1514'
    try:
        if native.exists() or controls.exists():
            raise FileExistsError('one-shot center refuses existing output')
        priors = [(19,'selected_keeper_corrected_coarse19_fine149_step50_1412','selected_keeper_corrected_coarse19_physical_1413'),
                  (20,'selected_keeper_corrected_BSIM_step50_1341','selected_keeper_corrected_BSIM_step50_physical_1342')]
        pins, measured, decks = {}, {}, []
        for coarse,n,c in priors:
            paths = [base / n / 'assessment.json',base / c / 'assessment.json']
            nr,cr = [json.loads(p.read_text()) for p in paths]
            for record in (nr,cr):
                verify(record['input_sha256'])
                verify(record['artifacts'])
            measured[str(coarse)] = checked_frequency(nr,cr,coarse)
            deck = base / n / 'transient.spice'
            decks.append(normalized_deck(deck.read_text()))
            pins.update({str(p):sha(p) for p in [*paths,deck]})
        if decks[0] != decks[1] or not measured['19'] < measured['20'] < 400:
            raise ValueError('same-deck measured positive coarse direction below target required')
        helpers = ['run_keeper_native_BSIM_coarse_band.py','assess_keeper_physical_tuning_v2.py']
        pins.update({str(p):sha(p) for p in [Path(__file__).resolve(),*[Path(__file__).with_name(n) for n in helpers]]})
        save(output / 'plan.json',dict(input_sha256=pins,measured_centers_MHz=measured,
             next_coarse=23,fine=149,max_step_ps=50,CPU=18,memory_GiB=16,
             maximum_additional_native_cases=1,native_cap_s=86400,automatic_identical_retry=False,
             choice_is_experiment_location_only=True,unmeasured_frequency_inferred=False,
             calibration_extrapolation_allowed=False,band_auto_selected=False,release_ready=False))
        save(output / 'status.json',dict(state='capturing_predeclared_coarse23_center_subject_to_resource_admission',release_ready=False))
        capture(base / 'selected_keeper_flat_native_smoke_1210',native,149,18,23,50)
        physical(native,base / 'selected_keeper_DCO_control_drivers_1233',base / 'selected_keeper_flat_native_model_1208',
                 base / 'selected_keeper_parent_reroute_1136',controls,False,cpu=18)
        nr,cr = [json.loads((p/'assessment.json').read_text()) for p in (native,controls)]
        f = checked_frequency(nr,cr,23)
        pins.update({str(p/'assessment.json'):sha(p/'assessment.json') for p in (native,controls)})
        verify(pins)
        save(output / 'assessment.json',dict(input_sha256=pins,frequency_mhz=f,coarse=23,fine=149,
             measured_prior_centers_MHz=measured,band_auto_selected=False,
             target_bracket_established=False,numerical_accuracy_qualified=False,
             model_qualified=False,release_ready=False))
        save(output / 'status.json',dict(state='coarse23_central_capture_and_physical_checks_complete',release_ready=False))
    except BaseException as error:
        save(output / 'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False))
        raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    run(parser.parse_args().output.resolve())
