#!/usr/bin/env python3
"""Wait for one identified capture, then run one bounded offline solve."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process

parser = argparse.ArgumentParser()
parser.add_argument('--capture-pid', type=int, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
base = root / 'build/timing400/release_001'
capture = base / 'DCO_native_linear_system_capture_002'
owner = capture / 'owner.json'
assert json.loads(owner.read_text())['runner_pid'] == args.capture_pid
identity = process(args.capture_pid)
assert identity['live'] and Path(identity['argv'][1]).name == 'capture_DCO_native_linear_system_v2.py'
benchmark = root / 'verification/timing400/benchmark_native_capacitance_preconditioner.py'
pins = {str(path.resolve()): digest(path) for path in [Path(__file__), owner, benchmark]}
args.output = args.output.resolve(); args.output.mkdir(exist_ok=False)
save(args.output / 'owner.json', dict(runner_pid=os.getpid(), capture_identity=identity,
    started_utc=datetime.now(timezone.utc).isoformat(), maximum_wait_s=660,
    subsequent_worker_limit_s=180, native_DCO_restarted=False))
def status(state, **extra):
    save(args.output / 'status.json', dict(state=state, runner_pid=os.getpid(),
        release_qualified=False, adopted=False, **extra))
status('waiting_for_identified_capture')
deadline = time.monotonic() + 660
proof = capture / 'assessment.json'
while not proof.exists() and time.monotonic() < deadline:
    observed = process(args.capture_pid)
    if not observed['live'] or observed['argv'] != identity['argv']: break
    time.sleep(1)
if not proof.exists():
    status('capture_unavailable_no_solver_started')
    sys.exit(0)
data = json.loads(proof.read_text())
assert all(digest(Path(path)) == sha for path, sha in pins.items())
if not data['first_native_Jacobian_captured']:
    status('capture_inconclusive_no_solver_started')
    sys.exit(0)
status('offline_solver_started')
case = base / 'native_capacitance_preconditioner_feasibility_001'
with (args.output / 'solver_runner.log').open('x') as log:
    result = subprocess.run([sys.executable, str(benchmark), '--output', str(case)],
        cwd=root, stdout=log, stderr=subprocess.STDOUT,
        env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'), timeout=240)
assessment = case / 'assessment.json'
metrics = json.loads(assessment.read_text()) if result.returncode == 0 and assessment.exists() else None
save(args.output / 'assessment.json', dict(runner_exit=result.returncode,
    capture_assessment_sha256=digest(proof), solver_assessment=metrics,
    input_sha256=pins, native_DCO_restarted=False, release_qualified=False, adopted=False))
status('completed_offline_solver_handoff' if metrics is not None else 'offline_solver_runner_nonpass')
