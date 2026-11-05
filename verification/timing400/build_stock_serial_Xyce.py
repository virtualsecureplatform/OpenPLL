#!/usr/bin/env python3
"""Build unmodified upstream serial Xyce/Trilinos in an isolated prefix.

Keep the installed golden binary and all live simulations untouched. A built
binary is an unqualified comparison candidate until independent controls pass.
All stages inherit the current campaign's original absolute deadline.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from compile_local_C_operators_v2 import digest, save


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    owner = root / 'build/timing400/release_001/distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    out = args.output.resolve()
    out.mkdir(exist_ok=False)
    sdk = out / 'trilinos-install'
    install = out / 'xyce-install'
    trilinos_build, xyce_build = out / 'trilinos-build', out / 'xyce-build'
    inputs = [Path(__file__).resolve(), owner, root / 'build/apptainer/openpll-release-modern.sif',
        Path('/opt/Xyce/CMakeLists.txt'), Path('/opt/Xyce/cmake/tps.cmake'),
        Path('/opt/Xyce/src/LinearAlgebraServicesPKG/N_LAS_AmesosSolver.C'),
        Path('/opt/Trilinos/CMakeLists.txt'), Path('/opt/trilinos-build/CMakeCache.txt'),
        Path('/opt/xyce/bin/Xyce')]
    pins = {str(p.resolve()): digest(p) for p in inputs}
    cmake = '/usr/bin/cmake'
    configure = [cmake, '-S', '/opt/Trilinos', '-B', str(trilinos_build),
        '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_SHARED_LIBS=OFF',
        '-DCMAKE_C_COMPILER=/usr/bin/gcc', '-DCMAKE_CXX_COMPILER=/usr/bin/g++',
        '-DCMAKE_Fortran_COMPILER=/usr/bin/gfortran',
        '-DCMAKE_INSTALL_PREFIX=' + str(sdk), '-DTPL_ENABLE_MPI=OFF',
        '-DTrilinos_ENABLE_ALL_OPTIONAL_PACKAGES=OFF', '-DTrilinos_ENABLE_TESTS=OFF',
        '-DTrilinos_ENABLE_EXAMPLES=OFF', '-DTrilinos_ENABLE_COMPLEX_DOUBLE=ON',
        '-DTPL_ENABLE_BLAS=ON', '-DTPL_ENABLE_LAPACK=ON', '-DTPL_ENABLE_AMD=ON',
        '-DAMD_INCLUDE_DIRS=/usr/include/suitesparse', '-DAmesos_ENABLE_KLU=ON',
        '-DNOX_ENABLE_LOCA=ON', '-DEpetraExt_BUILD_BTF=ON',
        '-DEpetraExt_BUILD_EXPERIMENTAL=ON', '-DEpetraExt_BUILD_GRAPH_REORDERINGS=ON']
    packages = ['Amesos', 'Epetra', 'EpetraExt', 'Ifpack', 'NOX', 'Teuchos',
                'Sacado', 'Triutils', 'AztecOO', 'Belos', 'TrilinosCouplings']
    configure.extend('-DTrilinos_ENABLE_' + package + '=ON' for package in packages)
    configure_xyce = [cmake, '-S', '/opt/Xyce', '-B', str(xyce_build),
        '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_C_COMPILER=/usr/bin/gcc',
        '-DCMAKE_CXX_COMPILER=/usr/bin/g++', '-DCMAKE_INSTALL_PREFIX=' + str(install),
        '-DTrilinos_ROOT=' + str(sdk), '-DTrilinos_DIR=' + str(sdk / 'lib/cmake/Trilinos'),
        '-DXyce_PARALLEL_MPI=OFF', '-DXyce_STOKHOS_ENABLE=OFF', '-DXyce_ROL=OFF',
        '-DXyce_AMESOS2=OFF', '-DXyce_SHYLU=OFF', '-DXyce_RELEASE=ON']
    stages = [('configure_trilinos', configure),
              ('build_trilinos', [cmake, '--build', str(trilinos_build), '--parallel', '8']),
              ('install_trilinos', [cmake, '--install', str(trilinos_build)]),
              ('configure_xyce', configure_xyce),
              ('build_xyce', [cmake, '--build', str(xyce_build), '--parallel', '8']),
              ('install_xyce', [cmake, '--install', str(xyce_build)]),
              ('version', [str(install / 'bin/Xyce'), '-v'])]
    save(out / 'owner.json', dict(original_owner=str(owner), deadline_uptime=deadline,
        started_utc=datetime.now(timezone.utc).isoformat(), runner_pid=os.getpid(),
        budget_restarted=False))
    save(out / 'input_manifest.json', dict(input_sha256=pins, commands=stages,
        source_code_modified=False, installed_golden_binary_modified=False,
        comparison_only=True, build_workers=8, original_deadline_uptime=deadline))
    def status(state, **extra):
        save(out / 'status.json', dict(state=state, runner_pid=os.getpid(),
            observed_utc=datetime.now(timezone.utc).isoformat(),
            deadline_uptime=deadline, release_qualified=False, adopted=False, **extra))
    receipts = []
    for name, command in stages:
        remaining = deadline - time.clock_gettime(time.CLOCK_BOOTTIME)
        if remaining <= 0:
            status('timeout_inconclusive', stage=name)
            return
        start = time.monotonic()
        with (out / (name + '.log')).open('x') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'),
                start_new_session=True)
            status('stock_serial_build_running', stage=name, child_pid=child.pid)
            try:
                code = child.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
                status('timeout_inconclusive', stage=name)
                return
        receipts.append(dict(stage=name, exit_code=code, elapsed_s=time.monotonic() - start))
        save(out / 'stage_receipts.json', receipts)
        if code:
            status('build_nonpass', stage=name, exit_code=code)
            return
    cache = (xyce_build / 'CMakeCache.txt').read_text()
    assert 'Xyce_PARALLEL_MPI:BOOL=OFF' in cache or 'Xyce_PARALLEL_MPI:BOOL=FALSE' in cache
    assert 'Xyce Release 7.10' in (out / 'version.log').read_text()
    assert all(digest(Path(name)) == value for name, value in pins.items())
    binary = install / 'bin/Xyce'
    save(out / 'assessment.json', dict(stock_serial_build_completed=True,
        binary=str(binary), binary_sha256=digest(binary), source_code_modified=False,
        installed_golden_binary_modified=False, serial_KLU_factor_reuse_controls_passed=False,
        simulator_equivalence_qualified=False, runtime_model_eligible=False,
        release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256=pins, stages=receipts))
    status('stock_serial_build_completed_controls_pending', binary=str(binary))


if __name__ == '__main__':
    main()
