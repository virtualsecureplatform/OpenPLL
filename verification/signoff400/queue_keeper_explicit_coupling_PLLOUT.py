"""Wait for combined-engine controls before one bounded PLLOUT native extraction."""
import argparse
import json
import os
import time
from pathlib import Path
from common_v3 import ROOT, save, sha, verify
from resources import identity
from probe_magic_explicit_coupling_control import run as control
from run_keeper_PLLOUT_R_explicit_coupling import run as pilot


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {28})
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    names = ['queue_keeper_explicit_coupling_PLLOUT.py', 'probe_magic_explicit_coupling_control.py', 'run_keeper_PLLOUT_R_explicit_coupling.py']
    pins = {str(Path(__file__).with_name(n)): sha(Path(__file__).with_name(n)) for n in names}
    b = ROOT / 'build/signoff400'
    engine = ROOT / 'build/tools/magic_geometry_explicit_coupling_1431'
    controls = b / 'selected_magic_geometry_explicit_coupling_controls_1432'
    target = b / 'selected_keeper_PLLOUT_explicit_coupling_1433'
    save(output / 'inputs.json', dict(input_sha256=pins, maximum_full_layout_native_cases=1, automatic_identical_retry=False, release_ready=False))
    try:
        if controls.exists() or target.exists():
            raise ValueError('output already exists; no automatic retry')
        save(output / 'status.json', dict(state='waiting_for_combined_engine_and_native_controls', release_ready=False))
        control(engine, controls)
        verify(pins)
        save(output / 'status.json', dict(state='running_one_PLLOUT_coupling_export_control', release_ready=False))
        pilot(b / 'selected_keeper_flat_geometry_C_1202', b / 'selected_keeper_EXT_driver_anchors_1250', engine, controls, target)
        verify(pins)
        save(output / 'assessment.json', dict(input_sha256=pins, artifacts={str(p): sha(p) for p in [controls / 'assessment.json', target / 'assessment.json']}, native_pipeline_complete=True, model_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='native_pipeline_complete_audit_pending', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    run(a.output.resolve())
