#!/usr/bin/env python3
"""Read-only terminal watcher; run an audit, never launch a native circuit."""
import json
import os
from pathlib import Path
import subprocess
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
source=base/'bounded_reuse_native_controls_001'
owner=json.loads((source/'owner.json').read_text());pid=owner['runner_pid']
identity=process(pid);assert identity['live'] and any(x.endswith('check_bounded_reuse_native_controls.py') for x in identity['argv'])
deadline=json.loads((base/'DCO_domain_nom_tt27_c0_f247_80ns_wire_preconditioned_gear_002/owner.json').read_text())['deadline_uptime']
out=base/'bounded_reuse_native_controls_audit_watcher_001';out.mkdir(exist_ok=False)
save(out/'owner.json',dict(runner_pid=os.getpid(),source_runner_pid=pid,deadline_uptime=deadline,
    native_circuit_started=False,auditor_sha256=digest(Path(__file__).with_name('audit_bounded_reuse_native_controls.py'))))
while not (source/'assessment.json').exists():
    state=process(pid)
    if not state['live'] or time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
        save(out/'status.json',dict(state='source_terminal_without_pass_or_deadline',source_runner=state,release_qualified=False));raise SystemExit(0)
    assert state['argv']==identity['argv']
    save(out/'status.json',dict(state='waiting_for_native_control_receipt',source_runner_live=True,release_qualified=False))
    time.sleep(min(5,max(.01,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
command=['apptainer','exec','--bind','/home:/home',str(root/'build/apptainer/openpll-release-modern.sif'),
    str(root/'build/timing400/numeric_tools_002/bin/python'),str(Path(__file__).with_name('audit_bounded_reuse_native_controls.py'))]
with (out/'audit.log').open('x') as log:
    child=subprocess.Popen(command,cwd=root,stdout=log,stderr=subprocess.STDOUT)
    save(out/'status.json',dict(state='auditing_terminal_controls',child_pid=child.pid,release_qualified=False))
    try:code=child.wait(timeout=max(.001,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
    except subprocess.TimeoutExpired:child.terminate();child.wait(timeout=5);code=child.returncode
save(out/'status.json',dict(state='audit_completed' if code==0 else 'audit_nonpass',audit_exit=code,release_qualified=False))
