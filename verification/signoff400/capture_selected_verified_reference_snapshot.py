"""Cache a full initial vector from a completed, checksum-bound native reference.

Accept only matching completion provenance, actual native inputs, and complete
260 ns selected-signal assessment. The source RAW is rehashed under a lease;
subsequent waveform captures may then use its exact filesystem fingerprint.
"""
import argparse
import json
import os
from pathlib import Path
import time

from common_v3 import save, sha, verify
from resources import identity, lease
from run_selected_detector_phase_probe import first_sample
from capture_selected_native_initial_snapshot import fingerprint


def run(native, provenance, output):
    os.sched_setaffinity(0, {29})
    output.mkdir(parents=True, exist_ok=False)
    save(output/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    save(output/'status.json', dict(state='verifying_completed_native_reference', release_ready=False))
    try:
        record = json.loads(provenance.read_text())
        verify(record['input_sha256']); verify(record['artifacts'])
        manifest = native/'manifest.json'
        nm = json.loads(manifest.read_text())
        verify(nm['input_sha256'])
        if record['input_sha256'].get(str(manifest)) != sha(manifest):
            raise ValueError('native manifest not bound by reference provenance')
        if record['native_input_sha256'] != nm['input_sha256']:
            raise ValueError('native input provenance differs')
        status = json.loads((native/'status.json').read_text())
        if status['state'] not in ('native_startup_completed_waveform_assessment_pending',
                                   'completed_startup_observed_not_tracking_at_260ns'):
            raise ValueError('normal original native completion required')
        proc = json.loads((native/'native.process.json').read_text())
        if identity(proc['pid']) == proc['birth']:
            raise ValueError('original native worker remains live')
        assessment = provenance.parent/'assessment.json'
        if record['artifacts'].get(str(assessment)) != sha(assessment):
            raise ValueError('assessed waveform not bound by provenance')
        a = json.loads(assessment.read_text())
        if a.get('end_ns') != 260 or a.get('samples', 0) < 3:
            raise ValueError('complete 260 ns assessed waveform required')
        paths = [manifest, provenance, assessment, native/'status.json', native/'native.process.json',
                 Path(__file__).resolve(), Path(__file__).with_name('run_selected_detector_phase_probe.py'),
                 Path(__file__).with_name('capture_selected_native_initial_snapshot.py'),
                 Path(__file__).with_name('common_v3.py'), Path(__file__).with_name('resources.py')]
        pins = {str(p): sha(p) for p in paths}
        raw = native/'profile.raw'
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+1800
        with lease(1, 2, deadline):
            before = fingerprint(raw)
            names, values = first_sample(raw)
            digest = sha(raw)
            if digest != record['raw_sha256'] or fingerprint(raw) != before:
                raise ValueError('source RAW changed or differs from native provenance')
        verify(pins); pins[str(raw)] = digest
        snapshot = output/'initial_voltage_vector.json'
        save(snapshot, dict(variable_names=names, values=values, time_s=0))
        save(output/'assessment.json', dict(input_sha256=pins,
            artifacts={str(snapshot): sha(snapshot)}, vectors=len(names),
            all_initial_values_finite=True, source_file_fingerprint=before,
            raw_rehashed_against_completed_native_provenance=True,
            snapshot_boundary_conditions_qualified=False, physical_models_qualified=False,
            release_ready=False))
        save(output/'status.json', dict(state='full_initial_voltage_snapshot_captured', release_ready=False))
    except BaseException as error:
        save(output/'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('native', 'provenance', 'output'):
        p.add_argument('--'+n, type=Path, required=True)
    a = p.parse_args()
    run(*(getattr(a, n).resolve() for n in ('native', 'provenance', 'output')))
