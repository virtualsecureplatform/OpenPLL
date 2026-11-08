"""Audit only a normally completed PLLOUT coupling-export experiment."""
import argparse
import json
import os
import resource
import time
from pathlib import Path
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compare_keeper_coupling_export import metrics


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {29})
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    b = ROOT / 'build/signoff400'
    candidate = b / 'selected_keeper_PLLOUT_explicit_coupling_1433'
    pipeline = b / 'selected_keeper_PLLOUT_coupling_pipeline_1434'
    previous = b / 'selected_keeper_PLLOUT_R_corrected_geometry_1339'
    flat = b / 'selected_keeper_flat_geometry_C_1202'
    try:
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 86400
        save(output / 'status.json', dict(state='waiting_for_completed_PLLOUT_export', release_ready=False))
        while not (candidate / 'assessment.json').exists():
            state = json.loads((pipeline / 'status.json').read_text())['state']
            if state == 'stopped_without_qualification':
                raise RuntimeError('PLLOUT producer pipeline stopped')
            owner = json.loads((pipeline / 'owner.json').read_text())
            if identity(owner['pid']) != owner['birth']:
                raise RuntimeError('producer owner missing without completed export')
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('completed-export observation deadline')
            time.sleep(10)
        receipts = [p / 'assessment.json' for p in [flat, previous, candidate]]
        values = [json.loads(p.read_text()) for p in receipts]
        for value in values:
            verify(value['input_sha256'])
            verify(value['artifacts'])
        for value in values[1:]:
            if value.get('native_process_completed') is not True or value['input_sha256'].get(str(receipts[0])) != sha(receipts[0]):
                raise ValueError('normally completed exports of same flat source required')
        if values[2].get('explicit_coupling_not_grounded') is not True:
            raise ValueError('explicit coupling control required')
        paths = [*receipts, flat / 'capacitance.spice', previous / 'pilot.spice', candidate / 'pilot.spice', Path(__file__).resolve(), Path(__file__).with_name('compare_keeper_coupling_export.py'), Path(__file__).with_name('audit_keeper_native_R_contraction.py')]
        pins = {str(p): sha(p) for p in paths}
        save(output / 'inputs.json', dict(input_sha256=pins, CPU=29, memory_GiB=16, release_ready=False))
        save(output / 'status.json', dict(state='waiting_for_static_audit_resource_budget', release_ready=False))
        with lease(1, 16, time.clock_gettime(time.CLOCK_BOOTTIME) + 7200):
            resource.setrlimit(resource.RLIMIT_AS, (16 * 1024**3, 16 * 1024**3))
            save(output / 'status.json', dict(state='comparing_completed_C_and_R_exports', release_ready=False))
            result = metrics((flat / 'capacitance.spice').read_text(), (previous / 'pilot.spice').read_text(), (candidate / 'pilot.spice').read_text())
            verify(pins)
        save(output / 'assessment.json', dict(input_sha256=pins, **result))
        save(output / 'status.json', dict(state='completed_static_coupling_export_audit', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    run(a.output.resolve())
