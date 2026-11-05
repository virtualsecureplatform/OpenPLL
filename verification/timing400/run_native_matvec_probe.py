#!/usr/bin/env python3
"""Measure unchanged captured-matrix products with at most four CPU threads."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import shlex
import signal
import subprocess
import time
import numpy as np
from scipy.sparse import load_npz
from compile_local_C_operators_v2 import digest, save

root = Path(__file__).resolve().parents[2]; base = root/'build/timing400/release_001'
source = root/'verification/timing400/native_matvec_probe'
out = base/'native_matvec_probe_checks_001'; out.mkdir(exist_ok=False)
build = root/'build/timing400/native_matvec_probe_001'
owner = base/'DCO_domain_nom_tt27_c0_f247_80ns_bounded_reuse_gear_001/owner.json'
inherited = json.loads(owner.read_text())['deadline_uptime']
deadline = time.monotonic()+min(180, inherited-time.clock_gettime(time.CLOCK_BOOTTIME))
started = time.monotonic(); assert deadline > started
inputs = base/'native_adapter_probe_inputs_001'
captured = base/'DCO_native_linear_system_capture_002/native_Jacobian.npz'
manifest = inputs/'assessment.json'
pins = {**json.loads(manifest.read_text())['artifacts']}
for p in (Path(__file__).resolve(), owner, source/'main.cpp', source/'CMakeLists.txt', manifest, captured): pins[str(p)] = digest(p)
save(out/'owner.json', dict(runner_pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
     inherited_DCO_deadline_uptime=inherited, total_wall_limit_s=180, maximum_probe_threads=4,
     native_circuit_started=False, live_simulator_changed=False, budget_restarted=False))
child = None
def remaining():
    value = deadline-time.monotonic()
    if value <= 0: raise TimeoutError('offline matrix-product probe deadline')
    return value
def stop():
    if child is not None and child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        try: child.wait(timeout=5)
        except subprocess.TimeoutExpired: os.killpg(child.pid, signal.SIGKILL); child.wait()
def limits():
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (180, 181))
try:
    for path, sha in pins.items(): remaining(); assert digest(Path(path)) == sha, path
    commands = [
        ['cmake', '-S', str(source), '-B', str(build), '-DCMAKE_BUILD_TYPE=Release',
         '-DTrilinos_DIR='+str(base/'stock_serial_Xyce_001/trilinos-install/lib/cmake/Trilinos')],
        ['cmake', '--build', str(build), '-j1'],
        [str(build/'native_matvec_probe'), str(inputs/'original_A.bin'), str(out)]]
    for label, command in zip(('configure', 'build', 'probe'), commands):
        save(out/'status.json', dict(state='offline_'+label, release_qualified=False))
        with (out/(label+'.log')).open('x') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True, preexec_fn=limits, env=dict(os.environ,
                OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', OMP_WAIT_POLICY='PASSIVE'))
            code = child.wait(timeout=remaining())
        assert code == 0, label+' nonpass; see retained log'
    records = [json.loads(s) for s in (out/'probe.log').read_text().splitlines() if s.startswith('{')]
    assert [r['threads'] for r in records] == [0, 1, 2, 4]
    a = load_npz(captured).tocsr(); n = a.shape[0]
    x = np.sin(.013*np.arange(n))+np.cos(.027*np.arange(n))
    expected = a@x; absolute = abs(a)@abs(x)
    eps = np.finfo(float).eps; terms = np.diff(a.indptr)
    bound = 16*(terms+1)*eps/(1-(terms+1)*eps)*absolute
    checks = []
    for record in records:
        assert record['original_matrix_unchanged'] and record['all_three_fixture_checks_passed']
        p = out/('threads'+str(record['threads'])+'.bin'); values = np.fromfile(p, dtype='<f8')
        assert values.shape == (n,) and np.isfinite(values).all()
        assert np.all(abs(values-expected) <= bound), record
        checks.append(dict(threads=record['threads'], maximum_SciPy_difference=float(max(abs(values-expected))),
                           independent_forward_error_check_passed=True))
        pins[str(p)] = digest(p)
    for p in (build/'native_matvec_probe', build/'CMakeCache.txt', build/'CMakeFiles/native_matvec_probe.dir/link.txt', out/'probe.log'):
        pins[str(p)] = digest(p)
    for token in shlex.split((build/'CMakeFiles/native_matvec_probe.dir/link.txt').read_text()):
        p = Path(token)
        if p.is_absolute() and p.is_file(): pins[str(p)] = digest(p)
    for p, sha in pins.items(): remaining(); assert digest(Path(p)) == sha, p
    reference = records[0]['total_multiply_s']
    save(out/'assessment.json', dict(input_sha256=pins, records=records, independent_checks=checks,
         Epetra_over_candidate_time_ratios={str(r['threads']):reference/r['total_multiply_s'] for r in records[1:]},
         captured_matrix_unchanged=True, maximum_probe_threads=4, three_input_fixture_checks_per_variant=True,
         solver_integrated=False, actual_Newton_sequence_tested=False, statistical_speedup_repeatability_qualified=False,
         full_DCO_speedup_demonstrated=False, live_simulator_changed=False, release_qualified=False, adopted=False))
    save(out/'status.json', dict(state='completed_offline_matrix_product_probe', release_qualified=False))
    print(json.dumps(records))
except Exception as error:
    stop()
    save(out/'failure_receipt.json', dict(error_type=type(error).__name__, message=str(error),
         elapsed_s=time.monotonic()-started, native_circuit_changed=False, release_qualified=False))
    save(out/'status.json', dict(state='offline_probe_nonpass', release_qualified=False))
    raise
finally:
    stop()
