#!/usr/bin/env python3
"""Capture missing finite-R self-coupling ownership on the actual nominal DCO.

Require unchanged native C, device cards and feedback. This is a changed
diagnostic extraction, not a retry or an adopted capacitor model.
"""
from datetime import datetime, timezone
import argparse
import fcntl
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import time

from check_isolated_magic_stock_v3 import matrix, devices
from check_magic_C_owner_controls import live_engines
from compile_local_C_operators_v2 import digest, save


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--corner', choices=['min', 'nom', 'max'], required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    control_path = base/'magic_C_owner_controls_001/assessment.json'
    assert json.loads(control_path.read_text())['all12_owner_trace_native_equivalence_and_accounting_controls_passed']
    build_path = base/'magic_C_owner_trace_build_001/assessment.json'
    binary = root/'build/timing400/magic_C_owner_trace_623_001/bin/magic'
    private = root/'build/timing450/pdk/sky130A'
    rc = private/'libs.tech/magic/sky130A.magicrc'
    old = base/'DCO_C_kernel_trace_controls_001'/(args.corner+'_trace')
    out = base/('DCO_C_owner_trace_'+args.corner+'_001')
    out.mkdir(exist_ok=False)
    target = out/(args.corner+'_trace')
    target.mkdir()
    task = target/'extract.tcl'
    task.write_text((old/'extract.tcl').read_text().replace(str(old), str(target)))
    inputs = [Path(__file__).resolve(), owner, control_path, build_path, binary, rc,
        old/'extract.tcl', old/'control.spice', old/'feedback.txt', task,
        base/'DCO_C_kernel_trace_controls_001/assessment.json']
    pins = {str(p): digest(p) for p in inputs}
    env = {k: v for k, v in os.environ.items() if not k.startswith('OPENPLL_')}
    env.update(PDK_ROOT=str(private.parent), OPENPLL_CAP_RC_SUBSTRATE='1', OPENPLL_CAP_TRACE_SUPPORT='1',
        OPENPLL_CAP_TRACE_FILE=str(target/'contributions.log'), OPENPLL_CAP_SURFACE_FILE=str(target/'surfaces.log'),
        OPENPLL_CAP_KERNEL_FILE=str(target/'kernels.log'), OPENPLL_CAP_OWNER_FILE=str(target/'owners.log'))
    with (base.parent/'guarded_native_admission.lock').open('a+') as admission:
        fcntl.flock(admission, fcntl.LOCK_EX)
        before = live_engines()
        assert len(before) < 4
        with (target/'extract.log').open('x') as log, (target/'trace.log').open('x') as errors:
            child = subprocess.Popen([str(binary), '-dnull', '-noconsole', '-rcfile', str(rc), str(task)],
                cwd=target, env=env, stdout=log, stderr=errors, start_new_session=True)
        save(out/'owner.json', dict(runner_pid=os.getpid(), native_pid=child.pid,
            started_utc=datetime.now(timezone.utc).isoformat(), deadline_uptime=deadline,
            original_owner=str(owner), budget_restarted=False, automatic_identical_retry=False, previous_engines=before))
        save(out/'status.json', dict(state='native_DCO_owner_extraction_running', runner_pid=os.getpid(),
            native_pid=child.pid, deadline_uptime=deadline))
    try:
        code = child.wait(timeout=min(900., deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGTERM)
        child.wait(timeout=10)
        save(out/'status.json', dict(state='timeout_inconclusive'))
        return
    assert code == 0 and 'DCO_FULL_C_TRACE_COMPLETE' in (target/'extract.log').read_text()
    assert not list(target.glob('*.res.ext'))
    save(out/'status.json', dict(state='checking_native_output_equivalence', runner_pid=os.getpid(), deadline_uptime=deadline))
    ext_paths = list(target.glob('*.ext'))
    assert len(ext_paths) == 1
    ext = ext_paths[0]
    assert matrix(old/'control.spice') == matrix(target/'control.spice')
    assert devices(old/ext.name) == devices(ext)
    assert (old/'feedback.txt').read_text() == (target/'feedback.txt').read_text()
    mapping = {}
    with (target/'contributions.log').open() as stream:
        for line in stream:
            if line.startswith('OPENPLL_ID '):
                f = shlex.split(line)
                assert len(f) == 4 and f[1] not in mapping and f[3] in ['0', '1']
                mapping[f[1]] = '@SUBSTRATE' if f[3] == '1' else f[2]
    assert list(mapping.values()).count('@SUBSTRATE') == 1
    save(target/'node_ids.json', mapping)
    assert all(digest(Path(p)) == value for p, value in pins.items())
    artifacts = [p for p in target.iterdir() if p.is_file()]
    result = dict(native_C_devices_and_feedback_unchanged=True, RC_corner=args.corner,
        nominal_native_C_devices_and_feedback_unchanged=args.corner == 'nom',
        changed_diagnostic_native_extractions_added=1, full_wire_R_extraction_performed=False,
        full_kernel_ownership_and_restored_self_coupling_qualification_complete=False,
        installed_extractor_replaced=False, runtime_model_eligible=False,
        release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256=pins, artifacts={str(p): digest(p) for p in artifacts})
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(out/'assessment.json', result)
    save(out/'status.json', dict(state='native_equivalence_passed_owner_model_compilation_required'))
    print('Actual DCO owner diagnostics preserve the native C matrix, all devices and feedback.')


if __name__ == '__main__':
    main()
