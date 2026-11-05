#!/usr/bin/env python3
"""Bounded native-SDK solve with independent residual recomputation."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import shlex
import shutil
import signal
import subprocess
import time
import numpy as np
from scipy.sparse import load_npz
from compile_local_C_operators_v2 import digest, save

root = Path(__file__).resolve().parents[2]
base = root / 'build/timing400/release_001'
folder = base / 'native_adapter_probe_checks_002'; folder.mkdir(exist_ok=False)
inputs = base / 'native_adapter_probe_inputs_001'
manifest = json.loads((inputs / 'assessment.json').read_text())
assert manifest['original_native_equations_exported']
for name, sha in {**manifest['input_sha256'], **manifest['artifacts']}.items():
    assert digest(Path(name)) == sha
build = root / 'build/timing400/native_adapter_probe_002'
source = root / 'verification/timing400/native_adapter_probe_v2'
for stage in ['configure', 'build']:
    shutil.copyfile(Path('/tmp/openpll-native-adapter-v2-' + stage + '.log'), build / (stage + '.log'))
files = [Path(__file__), source / 'main.cpp', source / 'CMakeLists.txt',
    build / 'native_adapter_probe', build / 'CMakeCache.txt', build / 'configure.log', build / 'build.log',
    build / 'CMakeFiles/native_adapter_probe.dir/link.txt', inputs / 'assessment.json',
    root / 'verification/timing400/native_wire_preconditioner/OpenPLL_WirePreconditioner_v2.h',
    base / 'native_wire_preconditioner_metadata_001/assessment.json',
    base / 'native_wire_preconditioner_metadata_001/wire_C.bin',
    root / 'build/apptainer/openpll-release-modern.sif']
for token in shlex.split((build / 'CMakeFiles/native_adapter_probe.dir/link.txt').read_text()):
    path = Path(token)
    if path.is_absolute() and path.is_file(): files.append(path)
pins = {str(path.resolve()): digest(path) for path in files}
save(folder / 'owner.json', dict(runner_pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
    worker_wall_limit_s=180, address_space_limit_GiB=48, offline_captured_matrix_only=True))
save(folder / 'input_manifest.json', dict(input_sha256=pins))
def limits():
    resource.setrlimit(resource.RLIMIT_AS, (48 * 1024**3, 48 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (180, 181))
command = ['apptainer', 'exec', '--bind', '/home:/home',
    str(root / 'build/apptainer/openpll-release-modern.sif'), str(build / 'native_adapter_probe'), str(inputs), str(folder)]
start = time.monotonic(); timed_out = False
with (folder / 'native.log').open('x') as log:
    child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True, preexec_fn=limits,
        env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', OPENPLL_WIRE_PC=str(base / 'native_wire_preconditioner_metadata_001/wire_C.bin')))
    save(folder / 'status.json', dict(state='native_SDK_solver_probe_running',
        runner_pid=os.getpid(), worker_pid=child.pid, release_qualified=False))
    try: code = child.wait(timeout=180)
    except subprocess.TimeoutExpired:
        timed_out = True; os.killpg(child.pid, signal.SIGTERM)
        try: child.wait(timeout=5)
        except subprocess.TimeoutExpired: os.killpg(child.pid, signal.SIGKILL); child.wait()
        code = child.returncode
records = []
if code == 0:
    capture = base / 'DCO_native_linear_system_capture_002'
    A = load_npz(capture / 'native_Jacobian.npz').tocsr()
    rhs_native = np.load(capture / 'native_RHS.npy')
    names = json.loads((capture / 'native_variable_names.json').read_text())
    voltage_rows = np.array([name.lower().endswith('_branch') for name in names])
    rs = 1. / np.asarray(abs(A).max(axis=1).toarray()).reshape(-1)
    known = .1 * (np.sin(np.arange(A.shape[0]) * .013) + np.cos(np.arange(A.shape[0]) * .027))
    reports = [json.loads(line) for line in (folder / 'native.log').read_text().splitlines() if line.startswith('{')]
    assert [item['case'] for item in reports] == ['known_solution', 'native_Newton_RHS']
    assert all(r['original_Jacobian_unchanged'] and r['original_RHS_unchanged'] for r in reports)
    for label, rhs in [('known_solution', A @ known), ('native_Newton_RHS', rhs_native)]:
        z = np.fromfile(folder / (label + '.bin'), dtype='<f8'); assert z.shape == rhs.shape
        x = z; residual = A @ x - rhs
        relative = float(np.linalg.norm(rs * residual) / np.linalg.norm(rs * rhs))
        assert np.isfinite(x).all() and relative < 1e-12
        item = dict(case=label, scaled_true_relative_residual=relative,
            maximum_current_equation_residual_A=float(np.max(abs(residual[~voltage_rows]))),
            maximum_voltage_constraint_residual_V=float(np.max(abs(residual[voltage_rows]))))
        if label == 'known_solution':
            item['known_solution_relative_error'] = float(np.linalg.norm(x - known, np.inf) / np.linalg.norm(known, np.inf))
            assert item['known_solution_relative_error'] < 1e-7
        records.append(item)
assert all(digest(Path(path)) == sha for path, sha in pins.items())
save(folder / 'assessment.json', dict(native_adapter_probe_passed=code == 0 and len(records) == 2,
    worker_exit=code, timed_out=timed_out, elapsed_s=time.monotonic() - start,
    independent_residual_checks=records,
    native_reports=reports if code == 0 else None, input_sha256=pins,
    simulator_source_modified=False, nonlinear_iteration_sequence_tested=False,
    full_transient_tested=False, full_DCO_speedup_demonstrated=False,
    release_qualified=False, adopted=False))
save(folder / 'status.json', dict(state='completed_native_adapter_probe' if code == 0 else
    ('timeout_inconclusive' if timed_out else 'native_adapter_probe_nonpass'), release_qualified=False))
print(json.dumps(dict(native_exit=code, checks=records)))
