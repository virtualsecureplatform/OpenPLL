"""Capture initial state directly from an assessed, normally completed full run.

This removes the conditional-probe prerequisite without upgrading conditional
boundary conditions or detector models to qualified evidence.
"""
import argparse
import json
import os
import time
from pathlib import Path
from common_v3 import save, sha, verify
from resources import identity, lease
from capture_selected_native_initial_snapshot import fingerprint
from run_selected_detector_phase_probe import first_sample
from selected_spice_device_conditions import read


def validate(native, assessment):
    status = json.loads((native / 'status.json').read_text())
    if status.get('state') != 'native_startup_completed_waveform_assessment_pending':
        raise ValueError('normally completed full native run required')
    provenance = json.loads((assessment / 'provenance.json').read_text())
    result = json.loads((assessment / 'assessment.json').read_text())
    manifest = native / 'manifest.json'
    deck = native / 'profile.spice'
    inputs = json.loads(manifest.read_text())['input_sha256']
    if provenance['input_sha256'].get(str(manifest)) != sha(manifest):
        raise ValueError('assessment belongs to a different native manifest')
    if provenance['native_input_sha256'] != inputs:
        raise ValueError('assessment native input lineage mismatch')
    if inputs.get(str(deck)) != sha(deck):
        raise ValueError('native deck identity mismatch')
    if provenance['artifacts'].get(str(assessment / 'assessment.json')) != sha(assessment / 'assessment.json'):
        raise ValueError('assessment artifact identity mismatch')
    if result.get('end_ns') != 260 or result.get('samples', 0) < 2:
        raise ValueError('complete 260 ns assessment required')
    verify(provenance['input_sha256'])
    verify(inputs)
    return provenance['raw_sha256'], read(deck)


def run(native, assessment, output):
    output.mkdir(parents=True, exist_ok=False)
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    try:
        expected, conditions = validate(native, assessment)
        raw = native / 'profile.raw'
        sources = [native / 'manifest.json', native / 'status.json',
                   assessment / 'provenance.json', assessment / 'assessment.json',
                   Path(__file__).resolve(), Path(__file__).with_name('run_selected_detector_phase_probe.py'),
                   Path(__file__).with_name('selected_spice_device_conditions.py')]
        pins = {str(p): sha(p) for p in sources}
        with lease(1, 2, time.clock_gettime(time.CLOCK_BOOTTIME) + 1800):
            before = fingerprint(raw)
            names, values = first_sample(raw)
            digest = sha(raw)
            if digest != expected or fingerprint(raw) != before:
                raise ValueError('full native RAW identity mismatch or changed during capture')
        verify(pins)
        pins[str(raw)] = digest
        vector = output / 'initial_voltage_vector.json'
        save(vector, dict(variable_names=names, values=values, time_s=0))
        save(output / 'assessment.json', dict(input_sha256=pins,
            artifacts={str(vector): sha(vector)}, vectors=len(names),
            all_initial_values_finite=True, source_file_fingerprint=before,
            source_device_conditions=conditions, source_time_coverage_s=[0, 260e-9],
            snapshot_boundary_conditions_qualified=False, physical_models_qualified=False,
            release_ready=False))
        save(output / 'status.json', dict(state='full_initial_voltage_snapshot_captured', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['native', 'assessment', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    os.sched_setaffinity(0, {30})
    run(args.native.resolve(), args.assessment.resolve(), args.output.resolve())
