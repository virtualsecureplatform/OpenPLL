#!/usr/bin/env python3
"""Resume the stock build with the required global OpenMP configuration."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prior', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    owner = root / 'build/timing400/release_001/distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    prior = args.prior.resolve(); out = args.output.resolve()
    failed = json.loads((prior / 'status.json').read_text())
    assert failed['state'] == 'build_nonpass' and failed['stage'] == 'configure_trilinos'
    assert not process(failed['runner_pid'])['live']
    old = json.loads((prior / 'input_manifest.json').read_text())
    receipts = json.loads((prior / 'stage_receipts.json').read_text())
    assert len(receipts) >= 6 and all(row['exit_code'] == 0 for row in receipts[:6])
    out.mkdir(exist_ok=False)
    save(out / 'owner.json', dict(original_owner=str(owner), deadline_uptime=deadline,
        runner_pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(), budget_restarted=False))
    def status(state, **extra):
        save(out / 'status.json', dict(state=state, runner_pid=os.getpid(), deadline_uptime=deadline,
            observed_utc=datetime.now(timezone.utc).isoformat(), release_qualified=False, adopted=False, **extra))
    status('preparing_corrected_global_OpenMP_build')
    pins = old['input_sha256'].copy()
    for path in [Path(__file__).resolve(), owner, prior / 'input_manifest.json', prior / 'status.json',
                 prior / 'ordering-install/lib/libmetis.so', prior / 'ordering-install/lib/libGKlib.so',
                 prior / 'ordering-install/include/metis.h']:
        pins[str(path.resolve())] = digest(path)
    assert all(digest(Path(name)) == value for name, value in pins.items())
    stages = old['commands'][6:]
    assert stages[0][0] == 'configure_trilinos'
    stages[0][1].extend(['-DTrilinos_ENABLE_OpenMP=ON', '-DTpetra_INST_SERIAL=ON'])
    # Reuse the failed configure tree and successful dependencies; original
    # receipts remain unchanged. Symlinks expose actual build paths to readers.
    for name in ['xyce-build', 'trilinos-build']:
        (out / name).symlink_to(prior / name, target_is_directory=True)
    save(out / 'input_manifest.json', dict(input_sha256=pins, commands=stages,
        resumed_after_configuration_failure=True, corrected_flags=['Trilinos_ENABLE_OpenMP=ON', 'Tpetra_INST_SERIAL=ON'],
        ordering_source_commits=old['ordering_source_commits'], build_workers=4,
        reused_dependency_prefix=str(prior / 'ordering-install'), source_code_modified=False,
        original_deadline_uptime=deadline, budget_restarted=False, threaded_solver='SHYLU_BASKER'))
    completed = []
    for name, command in stages:
        remaining = deadline - time.clock_gettime(time.CLOCK_BOOTTIME)
        if remaining <= 0: status('timeout_inconclusive', stage=name); return
        start = time.monotonic()
        with (out / (name + '.log')).open('x') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'))
            status('stock_threaded_build_running', stage=name, child_pid=child.pid)
            try: code = child.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGTERM)
                try: child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL); child.wait()
                status('timeout_inconclusive', stage=name); return
        completed.append(dict(stage=name, exit_code=code, elapsed_s=time.monotonic() - start))
        save(out / 'stage_receipts.json', completed)
        if code: status('build_nonpass', stage=name, exit_code=code); return
    cache = (out / 'xyce-build/CMakeCache.txt').read_text()
    assert 'Xyce_PARALLEL_MPI:BOOL=OFF' in cache or 'Xyce_PARALLEL_MPI:BOOL=FALSE' in cache
    assert 'Xyce_AMESOS2_SHYLUBASKER:BOOL=TRUE' in cache or 'Xyce_AMESOS2_SHYLUBASKER:BOOL=ON' in cache
    assert 'Kokkos_ENABLE_OPENMP:BOOL=ON' in (out / 'trilinos-build/CMakeCache.txt').read_text()
    assert 'Xyce Release 7.10' in (out / 'version.log').read_text()
    assert all(digest(Path(name)) == value for name, value in pins.items())
    binary = prior / 'xyce-install/bin/Xyce'
    save(out / 'assessment.json', dict(stock_threaded_build_completed=True, binary=str(binary),
        binary_sha256=digest(binary), source_code_modified=False, installed_golden_binary_modified=False,
        threaded_solver='SHYLU_BASKER', OpenMP_and_METIS_enabled=True,
        ordering_source_commits=old['ordering_source_commits'], independent_threaded_native_controls_passed=False,
        simulator_equivalence_qualified=False, release_qualified=False, adopted=False,
        deadline_uptime=deadline, input_sha256=pins, stages=completed))
    status('stock_threaded_build_completed_controls_pending', binary=str(binary))


if __name__ == '__main__': main()
