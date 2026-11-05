#!/usr/bin/env python3
"""Bound an offline initial-guess trial; never modify the live simulator."""
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


def main():
    started = time.monotonic()
    deadline = started+180
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    out = base / 'native_warm_start_probe_checks_001'
    out.mkdir(exist_ok=False)
    build = root / 'build/timing400/native_warm_start_probe_001'
    source = Path(__file__).with_name('native_warm_start_probe')
    inputs = base / 'native_adapter_probe_inputs_001'
    metadata = base / 'native_wire_preconditioner_metadata_001/wire_C.bin'
    capture = base / 'DCO_native_linear_system_capture_002'
    save(out / 'owner.json', dict(runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(), total_wall_limit_s=180,
        native_circuit_started=False, address_space_limit_GiB=8))
    child = None

    def remaining():
        value = deadline-time.monotonic()
        if value <= 0:
            raise TimeoutError('180-second offline trial deadline')
        return value

    def limits():
        resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
        seconds = max(1, int(remaining()))
        resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds+1))

    def stop():
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()

    try:
        manifest = json.loads((inputs / 'assessment.json').read_text())
        assert manifest['original_native_equations_exported']
        pins = {**manifest['input_sha256'], **manifest['artifacts']}
        for path in (Path(__file__).resolve(), source / 'main.cpp', source / 'CMakeLists.txt',
                     Path(__file__).with_name('native_wire_preconditioner') / 'OpenPLL_WirePreconditioner_v2.h',
                     Path(__file__).with_name('native_wire_preconditioner') / 'OpenPLL_WirePreconditioner_warm_start.h',
                     inputs / 'assessment.json', metadata, capture / 'native_Jacobian.npz'):
            pins[str(path)] = digest(path)
        for path, sha in pins.items():
            remaining()
            assert digest(Path(path)) == sha, path
        save(out / 'input_manifest.json', dict(input_sha256=pins))
        commands = [
            ['cmake', '-S', str(source), '-B', str(build), '-DCMAKE_BUILD_TYPE=Release',
             '-DTrilinos_DIR='+str(base / 'stock_serial_Xyce_001/trilinos-install/lib/cmake/Trilinos')],
            ['cmake', '--build', str(build), '-j1'],
            [str(build / 'native_warm_start_probe'), str(inputs), str(out)]]
        for label, command in zip(('configure', 'build', 'probe'), commands):
            save(out / 'status.json', dict(state='offline_'+label, release_qualified=False))
            with (out / (label+'.log')).open('x') as log:
                child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=True, preexec_fn=limits,
                    env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
                             OPENPLL_WIRE_PC=str(metadata)))
                try:
                    code = child.wait(timeout=remaining())
                except subprocess.TimeoutExpired:
                    raise TimeoutError('offline '+label+' deadline')
            assert code == 0, label+' failed; retained stage log'
        A = load_npz(capture / 'native_Jacobian.npz').tocsr()
        scale = 1/np.asarray(abs(A).max(axis=1).toarray()).reshape(-1)
        reports = [json.loads(line) for line in (out / 'probe.log').read_text().splitlines() if line.startswith('{')]
        assert len(reports) == 10
        checks = []
        for report in reports:
            remaining()
            assert report['original_Jacobian_unchanged'] and report['original_RHS_unchanged']
            label = report['case']
            solution = np.fromfile(out / (label+'.bin'), dtype='<f8')
            rhs = np.fromfile(out / (label+'.rhs.bin'), dtype='<f8')
            assert solution.shape == rhs.shape == (A.shape[0],) and np.isfinite(solution).all()
            residual = A@solution-rhs
            relative = float(np.linalg.norm(scale*residual)/np.linalg.norm(scale*rhs))
            assert relative <= 1e-12
            checks.append(dict(case=label, scaled_true_relative_residual=relative,
                               measured_adapter_wall_s=report['solve_wall_s']))
        for path in (build / 'native_warm_start_probe', build / 'CMakeCache.txt',
                     build / 'CMakeFiles/native_warm_start_probe.dir/link.txt'):
            pins[str(path)] = digest(path)
        for token in shlex.split((build / 'CMakeFiles/native_warm_start_probe.dir/link.txt').read_text()):
            path = Path(token)
            if path.is_absolute() and path.is_file():
                pins[str(path)] = digest(path)
        for path, sha in pins.items():
            remaining()
            assert digest(Path(path)) == sha, path
        save(out / 'assessment.json', dict(input_sha256=pins, checks=checks,
            all_original_equation_residual_checks_passed=True, elapsed_s=time.monotonic()-started,
            same_native_matrix_retained=True, synthetic_RHS_perturbation_included=True,
            actual_nonlinear_RHS_sequence_tested=False, live_adapter_changed=False,
            full_DCO_speedup_demonstrated=False, release_qualified=False, adopted=False))
        save(out / 'status.json', dict(state='completed_offline_probe', release_qualified=False))
        print(json.dumps(checks))
    except Exception as error:
        stop()
        save(out / 'failure_receipt.json', dict(error_type=type(error).__name__, message=str(error),
            elapsed_s=time.monotonic()-started, native_circuit_changed=False, release_qualified=False))
        save(out / 'status.json', dict(state='timeout_inconclusive' if isinstance(error, TimeoutError) else 'offline_probe_nonpass', release_qualified=False))
        raise
    finally:
        stop()


if __name__ == '__main__':
    main()
