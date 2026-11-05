#!/usr/bin/env python3
"""Require all twelve saved-case comparisons before using the new owner tracer."""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from check_magic_C_kernel_trace import reconstruct
from check_isolated_magic_stock_v3 import matrix, devices
from compile_local_C_operators_v2 import digest, save
from verify_magic_C_kernel_trace_v2 import verify_kernels
from verify_magic_C_surface_alignment_v2 import verify_alignment
from verify_magic_C_owners import verify_owners


def live_engines():
    active = []
    for p in Path('/proc').glob('[0-9]*'):
        try:
            name = (p/'comm').read_text().strip()
            state = (p/'stat').read_text().rsplit(')', 1)[1].split()[0]
            if name in ['Xyce', 'ngspice', 'magicdnull'] and state != 'Z':
                active.append(int(p.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
    return active


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    build_path = base/'magic_C_owner_trace_build_001/assessment.json'
    build = json.loads(build_path.read_text())
    assert build['full_geometry_owner_trace_build_completed']
    for name, value in build['input_sha256'].items():
        assert digest(Path(name)) == value
    binary = root/'build/timing400/magic_C_owner_trace_623_001/bin/magic'
    private = root/'build/timing450/pdk/sky130A'
    rc = private/'libs.tech/magic/sky130A.magicrc'
    out = base/'magic_C_owner_controls_001'
    out.mkdir(exist_ok=False)
    save(out/'owner.json', dict(runner_pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
        deadline_uptime=deadline, original_owner=str(owner), budget_restarted=False))
    original = base/'magic_C_kernel_trace_controls_001'
    inputs = [Path(__file__).resolve(), owner, build_path, binary, rc,
        Path(__file__).with_name('verify_magic_C_owners.py'), original/'assessment.json']
    results = []
    env = {k: v for k, v in os.environ.items() if not k.startswith('OPENPLL_')}
    env.update(PDK_ROOT=str(private.parent), OPENPLL_CAP_TRACE_SUPPORT='1')
    for old in sorted(p for p in original.iterdir() if p.is_dir()):
        assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
        target = out/old.name
        target.mkdir()
        task = target/'extract.tcl'
        task.write_text((old/'extract.tcl').read_text().replace(str(old), str(target)))
        inputs.extend([old/'extract.tcl', task, old/'control.spice', old/'feedback.txt'])
        env.update(OPENPLL_CAP_TRACE_FILE=str(target/'contributions.log'),
            OPENPLL_CAP_SURFACE_FILE=str(target/'surfaces.log'), OPENPLL_CAP_KERNEL_FILE=str(target/'kernels.log'),
            OPENPLL_CAP_OWNER_FILE=str(target/'owners.log'))
        with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            active = live_engines()
            assert len(active) < 4, active
            with (target/'extract.log').open('x') as log, (target/'trace.log').open('x') as errors:
                child = subprocess.Popen([str(binary), '-dnull', '-noconsole', '-rcfile', str(rc), str(task)],
                    cwd=target, env=env, stdout=log, stderr=errors, start_new_session=True)
            save(out/'status.json', dict(state='checking_owner_native_equivalence', case=old.name,
                native_pid=child.pid, runner_pid=os.getpid(), deadline_uptime=deadline))
        try:
            code = child.wait(timeout=min(60., deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGTERM)
            child.wait(timeout=10)
            save(out/'status.json', dict(state='timeout_inconclusive', case=old.name))
            return
        assert code == 0 and 'FULL_C_TRACE_CONTROL_COMPLETE' in (target/'extract.log').read_text()
        ext_paths = list(target.glob('*.ext'))
        assert len(ext_paths) == 1
        ext = ext_paths[0]
        assert matrix(old/'control.spice') == matrix(target/'control.spice')
        assert devices(old/ext.name) == devices(ext)
        assert (old/'feedback.txt').read_text() == (target/'feedback.txt').read_text()
        _, _, events, _, mapping = reconstruct((target/'contributions.log').read_text())
        save(target/'node_ids.json', mapping)
        kernels = verify_kernels(target/'contributions.log', target/'kernels.log', deadline=deadline)
        surfaces = verify_alignment(target/'contributions.log', target/'surfaces.log')
        owners = verify_owners(target, deadline)
        assert kernels['counts']['events'] == surfaces['events'] == len(events)
        result = dict(case=old.name, native_C_devices_and_feedback_unchanged=True,
            kernel_integral_and_surface_accounting_passed=True, owners=owners)
        save(target/'assessment.json', result)
        results.append(result)
    assert len(results) == 12
    assert sum(r['owners']['same_ideal_conductor_kernel_counts'].get('SIDEWALL', 0) for r in results) > 0
    artifacts = [p for p in out.rglob('*') if p.is_file() and p.name not in ['assessment.json', 'status.json', 'owner.json']]
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(out/'assessment.json', dict(all12_owner_trace_native_equivalence_and_accounting_controls_passed=True,
        self_sidewall_diagnostics_exercised=True, native_CAD_runs_added=12, results=results,
        runtime_model_eligible=False, release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256={str(p): digest(p) for p in inputs}, artifacts={str(p): digest(p) for p in artifacts}))
    save(out/'status.json', dict(state='completed', cases=12))
    print('All twelve owner-trace controls preserve native C/devices/feedback and validate ownership.')


if __name__ == '__main__':
    main()
