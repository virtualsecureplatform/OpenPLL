#!/usr/bin/env python3
"""Exercise native-identity and group-termination safeguards on dummy processes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from guard_DCO_assessment_deadline import terminate_identified
from record_qualification_progress_045 import process
from compile_local_C_operators_v2 import digest,save

root=Path(__file__).resolve().parents[2]
out=root/'build/timing400/release_001/DCO_deadline_guard_signal_checks_001';out.mkdir(exist_ok=False)
command=[sys.executable,'-c','import time; time.sleep(20)']
child=subprocess.Popen(command,start_new_session=True)
try:
    expected=process(child.pid);assert expected['live']
    wrong=dict(expected,argv=['wrong command'])
    try:terminate_identified(child.pid,wrong,.1)
    except AssertionError:pass
    else:raise AssertionError('mismatched identity was accepted')
    assert child.poll() is None
    assert terminate_identified(child.pid,expected,1)
    assert child.wait(timeout=3)==-15
    assert not terminate_identified(child.pid,expected,.1)
finally:
    if child.poll() is None:child.kill();child.wait()
# A non-leader process must not permit signaling the parent's process group.
other=subprocess.Popen(command)
try:
    assert os.getpgid(other.pid)!=other.pid
    try:terminate_identified(other.pid,process(other.pid),.1)
    except AssertionError:pass
    else:raise AssertionError('non-leader group termination was accepted')
    assert other.poll() is None
finally:other.terminate();other.wait(timeout=3)
save(out/'assessment.json',dict(wrong_identity_rejected_without_signal=True,matching_dummy_group_terminated=True,
    terminal_process_not_signaled=True,nonleader_rejected_without_signal=True,native_circuit_started=False,
    input_sha256={str(p):digest(p) for p in (Path(__file__).resolve(),Path(__file__).with_name('guard_DCO_assessment_deadline.py'))},release_qualified=False))
print('Four deadline-guard signal checks passed; no native circuit started')
