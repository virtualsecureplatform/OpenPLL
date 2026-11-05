"""Assess a bounded native transient once its pinned controller completes."""
import argparse
import json
import os
import time
from pathlib import Path
from common_v3 import save, sha, verify
from resources import identity
from compare_selected_transient import compare


def follow(native, reference, output, end_ns):
    if not 0 < end_ns <= 260:
        raise ValueError('unsupported comparison interval')
    output.mkdir(parents=True, exist_ok=False)
    owner = json.loads((native/'owner.json').read_text())
    pins = {str(p): sha(p) for p in (reference, native/'manifest.json',
        Path(__file__).resolve(), Path(__file__).with_name('compare_selected_transient.py'))}
    save(output/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    save(output/'inputs.json', dict(input_sha256=pins, native_owner=owner, end_ns=end_ns))
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 7200
    try:
        while True:
            state = json.loads((native/'status.json').read_text())['state']
            if state == 'conditional_21ns_completed_comparison_pending':
                break
            if state == 'stopped_without_qualification':
                raise RuntimeError('native control stopped without a completed waveform')
            if identity(owner['pid']) != owner['birth']:
                raise RuntimeError('native controller exited without a completion receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('native completion wait exhausted')
            save(output/'status.json', dict(state='waiting_for_native_completion', release_ready=False))
            time.sleep(10)
        verify(pins)
        manifest = json.loads((native/'manifest.json').read_text())
        verify(manifest['input_sha256'])
        waveform = native/'control.raw'
        raw_sha = sha(waveform)
        result = compare(reference, waveform, end_ns*1e-9)
        verify(pins)
        if sha(waveform) != raw_sha:
            raise ValueError('native waveform changed during comparison')
        result['input_sha256'] = dict(pins, **{str(waveform): raw_sha})
        save(output/'assessment.json', result)
        save(output/'status.json', dict(state='conditional_transient_comparison_complete',
             within_diagnostic_voltage_tolerance=result['within_diagnostic_voltage_tolerance'],
             physical_correlation_qualified=False, release_ready=False))
    except BaseException as error:
        save(output/'status.json', dict(state='stopped_without_qualification',
             reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('native', 'reference', 'output'):
        p.add_argument('--'+key, type=Path, required=True)
    p.add_argument('--end-ns', type=float, required=True)
    a = p.parse_args()
    os.sched_setaffinity(0, {24})
    follow(a.native.resolve(), a.reference.resolve(), a.output.resolve(), a.end_ns)
