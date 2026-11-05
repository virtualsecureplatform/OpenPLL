#!/usr/bin/env python3
"""Capture a first native Jacobian/RHS, then stop before awaiting its solve.

This is a bounded matrix-export diagnostic, not a repeated qualification run.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import resource
import signal
import shutil
import subprocess
import time
import numpy as np
from scipy.io import mmread
from scipy.sparse import save_npz
from compile_local_C_operators_v2 import digest, save
from run_DCO_domain_point_v3 import live_engines, model_files


def stop(child):
    if child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        try: child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL); child.wait()


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (48 * 1024**3, 48 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (600, 601))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    args.output = args.output.resolve(); args.output.mkdir(exist_ok=False)
    deadline = time.monotonic() + 600
    prior = base / 'DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_002/point.cir'
    binary = base / 'stock_serial_Xyce_001/xyce-install/bin/Xyce'
    proof = base / 'wire_block_preconditioner_feasibility_001/assessment.json'
    assert json.loads(proof.read_text())['metrics']['converged_at_requested_scaled_tolerance']
    terminal = base / 'campaign_deadline_001/assessment.json'
    assert json.loads(terminal.read_text())['original_runs_stopped']
    deck = args.output / 'point.cir'
    original = prior.read_text()
    option = '.options LINSOL TYPE=KLU TR_PARTITION=0 TR_AMD=0 KLU_REPIVOT=0'
    assert original.count(option) == 1
    deck.write_text(original.replace(option, option + ' OUTPUT_BASE_LS=1'))
    assert deck.read_text().replace(' OUTPUT_BASE_LS=1', '') == original
    cached = base / 'DCO_native_linear_system_capture_001'
    old_assessment = json.loads((cached / 'assessment.json').read_text())
    assert old_assessment['stages'][0]['phase'] == 'names'
    assert old_assessment['stages'][0]['native_exit'] == 0
    assert not old_assessment['first_native_Jacobian_captured']
    assert (cached / 'point.cir').read_text() == deck.read_text()
    inputs = [Path(__file__), prior, binary, proof, terminal,
        cached / 'assessment.json', cached / 'solution.names', cached / 'point.cir',
        root / 'build/apptainer/openpll-release-modern.sif',
        Path('/opt/Xyce/src/LinearAlgebraServicesPKG/N_LAS_AmesosSolver.C'),
        Path('/opt/Xyce/src/LinearAlgebraServicesPKG/N_LAS_EpetraHelpers.C')]
    inputs += model_files(deck, time.clock_gettime(time.CLOCK_BOOTTIME) + 300)
    pins = {str(path.resolve()): digest(path) for path in inputs}
    save(args.output / 'input_manifest.json', dict(input_sha256=pins,
        circuit_identical_except_matrix_export=True, capture_only=True,
        completed_campaign_extended=False, release_qualified=False))
    save(args.output / 'owner.json', dict(runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(), native_stage_wall_limit_s=600,
        per_native_address_space_limit_GiB=48, purpose='first_Jacobian_capture_only',
        original_qualification_campaign_restarted=False))
    def status(state, **extra):
        save(args.output / 'status.json', dict(state=state, runner_pid=os.getpid(),
            release_qualified=False, adopted=False, **extra))
    names = args.output / 'solution.names'
    shutil.copyfile(cached / 'solution.names', names)
    entries = [line.split() for line in names.read_text().splitlines()[1:]]
    assert len(entries) == 174551
    assert sorted(int(entry[0]) for entry in entries) == list(range(174551))
    assert len({entry[1].upper() for entry in entries}) == 174551
    save(args.output / 'names_reuse.json', dict(source=str(cached / 'solution.names'),
        sha256=digest(names), same_native_binary_and_circuit=True,
        independent_completed_names_export_reused=True, native_names_export_repeated=False))
    outcome = 'timeout_inconclusive'; capture = False; stages = []
    with (base.parent / 'guarded_native_admission.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        assert len(live_engines()) == 0, 'Do not overlap this diagnostic with another native engine'
        try:
            for phase in ['matrix']:
                if time.monotonic() >= deadline: break
                command = [str(binary), '-quiet']
                if phase == 'names': command += ['-namesfile', str(names)]
                command += [str(deck)]
                with (args.output / (phase + '.log')).open('x') as log:
                    child = subprocess.Popen(command, cwd=args.output, stdout=log,
                        stderr=subprocess.STDOUT, start_new_session=True,
                        preexec_fn=limits, env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'))
                    status('native_' + phase + '_export_running', native_pid=child.pid)
                    try:
                        while child.poll() is None and time.monotonic() < deadline:
                            rhs = args.output / 'Base_RHS1.mm'
                            if phase == 'matrix' and rhs.exists():
                                # RHS is written only after the matrix closes. Verify the
                                # array's exact row count before stopping the process.
                                lines = rhs.read_text().splitlines()
                                data = [line for line in lines if line and not line.startswith('%')]
                                if data and len(data[0].split()) == 2:
                                    n, k = map(int, data[0].split())
                                    if k == 1 and len(data) == n + 1:
                                        capture = True; break
                            time.sleep(.25)
                    finally: stop(child)
                stages.append(dict(phase=phase, native_exit=child.returncode,
                    stopped_after_complete_matrix_export=phase == 'matrix' and capture))
                save(args.output / 'stages.json', stages)
                if phase == 'names' and (child.returncode != 0 or not names.exists()):
                    outcome = 'names_export_nonpass'; break
        finally:
            if 'child' in locals(): stop(child)
    metrics = None
    if capture:
        A = mmread(args.output / 'Base_Matrix1.mm').tocsr()
        rhs = np.asarray(mmread(args.output / 'Base_RHS1.mm')).reshape(-1)
        mapping = {}
        for line in names.read_text().splitlines()[1:]:
            i, name = line.split(); i = int(i)
            assert i not in mapping
            mapping[i] = name
        assert A.shape == (len(rhs), len(rhs)) and len(mapping) == len(rhs)
        assert set(mapping) == set(range(len(rhs)))
        assert len({name.upper() for name in mapping.values()}) == len(rhs)
        assert np.isfinite(A.data).all() and np.isfinite(rhs).all()
        # The Epetra serial block map must match the names' zero-based GIDs.
        m = [line for line in (args.output / 'Base_BlockMap.mm').read_text().splitlines()
             if line and not line.startswith('%')]
        assert m[0].split() == [str(len(rhs)), '1']
        assert [int(value) for value in m[1:]] == list(range(len(rhs)))
        save_npz(args.output / 'native_Jacobian.npz', A)
        np.save(args.output / 'native_RHS.npy', rhs)
        save(args.output / 'native_variable_names.json', [mapping[i] for i in range(len(rhs))])
        metrics = dict(states=len(rhs), matrix_nnz=int(A.nnz), nonzero_numeric_entries=int(np.count_nonzero(A.data)),
            zero_diagonal_rows=int(np.sum(A.diagonal() == 0)), RHS_inf_norm=float(np.linalg.norm(rhs, np.inf)))
        outcome = 'completed_native_matrix_capture'
    assert all(digest(Path(name)) == value for name, value in pins.items())
    artifacts = {str(path): digest(path) for path in args.output.iterdir()
                 if path.is_file() and path.suffix in ['.mm', '.npz', '.npy', '.names']}
    save(args.output / 'assessment.json', dict(first_native_Jacobian_captured=capture,
        metrics=metrics, stages=stages, input_sha256=pins, artifacts=artifacts,
        full_transient_completion_attempted=False, full_DCO_speedup_demonstrated=False,
        completed_campaign_extended=False, release_qualified=False, adopted=False))
    status(outcome)


if __name__ == '__main__': main()
