#!/usr/bin/env python3
"""Reserve the next native slot; keep the container foreground alive for Gear."""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from compile_local_C_operators_v2 import digest, save
from run_DCO_domain_point_v3 import live_engines
from record_qualification_progress_045 import process


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    handoff = base / 'DCO_TRAP_to_GEAR_runtime_handoff_001/handoff.json'
    receipt = json.loads(handoff.read_text())
    deadline = receipt['deadline_uptime']
    assert not process(receipt['source_native_pid'])['live']
    assert not process(receipt['source_runner_pid'])['live']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    failed = base / 'DCO_domain_nom_tt27_c0_f247_80ns_wire_preconditioned_gear_001'
    failure = json.loads((failed / 'runner_failure.json').read_text())
    assert failure['error_type'] == 'OSError' and 'Transport endpoint is not connected' in failure['message']
    assert not (failed / 'launch.json').exists() and not (failed / 'native.log').exists()
    runner = Path(__file__).with_name('run_DCO_gear_fallback_v3.py').resolve()
    out = base / 'DCO_gear_foreground_recovery_001'
    out.mkdir(exist_ok=False)
    save(out / 'owner.json', dict(runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(), deadline_uptime=deadline,
        budget_restarted=False, prior_Gear_native_started=False,
        input_sha256={str(p): digest(p) for p in
            (Path(__file__).resolve(), runner, handoff, failed / 'runner_failure.json')}))
    child = None
    # Reserve only admission. Running engines continue normally; there is no
    # fifth native and no existing case is interrupted to obtain capacity.
    with (base.parent / 'guarded_native_admission.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        while time.clock_gettime(time.CLOCK_BOOTTIME) < deadline:
            active = live_engines()
            save(out / 'status.json', dict(state='reserving_next_native_slot',
                runner_pid=os.getpid(), observed_native_pids=active,
                deadline_uptime=deadline, release_qualified=False))
            if len(active) < 4:
                with (out / 'gear_worker.log').open('x') as log:
                    child = subprocess.Popen([sys.executable, str(runner), '--handoff', str(handoff),
                        '--admission-lock-fd', str(lock.fileno())], cwd=root,
                        stdout=log, stderr=subprocess.STDOUT, pass_fds=(lock.fileno(),),
                        start_new_session=True,
                        env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1'))
                save(out / 'replacement_owner.json', dict(runner_pid=child.pid,
                    deadline_uptime=deadline, inherited_admission_lock=True))
                break
            time.sleep(min(5, max(0, deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    if child is None:
        save(out / 'status.json', dict(state='timeout_inconclusive_before_admission',
            deadline_uptime=deadline, release_qualified=False))
        return
    save(out / 'status.json', dict(state='foreground_wait_for_changed_method_runner',
        replacement_runner_pid=child.pid, deadline_uptime=deadline, release_qualified=False))
    # This wait intentionally preserves the SIF/FUSE mount for all descendants.
    code = child.wait()
    save(out / 'assessment.json', dict(replacement_exit=code, deadline_uptime=deadline,
        container_foreground_lifetime_preserved=True, prior_native_retried=False,
        release_qualified=False, adopted=False))
    save(out / 'status.json', dict(state='replacement_runner_terminal', replacement_exit=code,
        deadline_uptime=deadline, release_qualified=False))


if __name__ == '__main__':
    main()
