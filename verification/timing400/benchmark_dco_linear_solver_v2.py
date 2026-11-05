#!/usr/bin/env python3
"""Benchmark a direct linear solver and controlled thread policy on a DCO prefix.

Keeps the circuit, initialization, step limit and tolerances. Only solver,
stop time and removal of out-of-window measurement directives change. Reports
raw waveform/edge differences and solver cost; no backend or model adoption.
"""
import argparse
import bisect
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time

from characterize_compact_propagation import XYCE, admit_one, crossings
from run_dco_qualification import sha, save


def waveform(path):
    times, values, terminal = [], [], False
    with path.open() as stream:
        assert stream.readline().split() == ['Index', 'TIME', 'V(PLLOUT)']
        for line in stream:
            if 'End of Xyce(TM) Simulation' in line:
                assert not terminal
                terminal = True
                continue
            row = line.split()
            if not row:
                continue
            assert not terminal and len(row) == 3 and int(row[0]) == len(times)
            t, v = map(float, row[1:])
            assert math.isfinite(t) and math.isfinite(v)
            times.append(t)
            values.append(v)
    assert terminal and times[0] == 0 and all(a < b for a, b in zip(times, times[1:]))
    return times, values


def main():
    deadline = time.monotonic()+43200
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-result', required=True, type=Path)
    parser.add_argument('--solver', required=True, choices=['KLU', 'KLU2', 'BASKER'])
    parser.add_argument('--threads', type=int, default=1)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    assert 1 <= args.threads <= 4
    reference_path, out = args.reference_result.resolve(), args.output.resolve()
    reference = json.loads(reference_path.read_text())
    assert reference['state'] == 'native_pass'
    wave = Path(reference['metric']['waveform'])
    assert sha(wave) == reference['metric']['waveform_sha256']
    original = wave.with_suffix('.spice')
    provenance_path = wave.with_suffix('.provenance.json')
    provenance = json.loads(provenance_path.read_text())
    assert provenance['completed'] and provenance['parameters']['vdd'] == 1.8
    assert sha(original) == provenance['netlist_sha256']
    pins = dict(provenance['files'])
    for path in (reference_path, wave, original, provenance_path, Path(__file__).resolve(),
                 Path(__file__).with_name('characterize_compact_propagation.py'), XYCE):
        pins[str(path.resolve())] = sha(path)
    for path, digest in pins.items():
        assert sha(Path(path)) == digest, path
    reference_times, reference_values = waveform(wave)
    assert reference_times[-1] >= 80e-9-1e-15
    lines = original.read_text().splitlines()
    lines = [line for line in lines if not re.match(r'^\s*\.meas(?:ure)?\b', line, re.I)]
    text = '\n'.join(lines)+'\n'
    text, changes = re.subn(r'(?im)^(\s*\.tran\s+\S+\s+)\S+', r'\g<1>10n', text)
    assert changes == 1 and '.options timeint reltol=1e-05 abstol=1e-09' in text
    out.mkdir(parents=True, exist_ok=False)
    deck = out/'benchmark.spice'
    deck.write_text(text)
    pins[str(deck)] = sha(deck)
    save(out/'plan.json', dict(input_sha256=pins, solver=args.solver,
        omp_num_threads=args.threads, openblas_num_threads=1, mkl_num_threads=1, stop_ns=10, reference_stop_ns=80,
        circuit_and_initialization_preserved=True, tolerances_and_step_limit_preserved=True,
        total_budget_s=43200, automatic_identical_retry=False, scope=__doc__, release_qualified=False))

    def status(state, **fields):
        save(out/'status.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
            state=state, total_budget_s=43200, release_qualified=False, **fields))

    def remaining():
        value = deadline-time.monotonic()
        if value <= 0:
            status('timeout_inconclusive')
            raise TimeoutError('total benchmark budget reached')
        return value

    while True:
        remaining()
        try:
            admit_one(out)
            break
        except AssertionError as error:
            status('waiting_for_native_capacity', reason=str(error))
            time.sleep(min(30, remaining()))
    env = dict(os.environ, OMP_NUM_THREADS=str(args.threads), OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    command = [str(XYCE), '-linsolv', args.solver, '-quiet', '-o', str(out/'benchmark'), str(deck)]
    started = time.monotonic()
    with (out/'run.log').open('x') as stream:
        child = subprocess.Popen(command, env=env, stdout=stream, stderr=subprocess.STDOUT)
        save(out/'launch.json', dict(pid=child.pid, command=command, input_sha256=pins,
            omp_num_threads=args.threads, total_budget_s=43200, release_qualified=False))
        status('native_running', native_pid=child.pid)
        try:
            code = child.wait(timeout=remaining())
        except subprocess.TimeoutExpired:
            child.terminate()
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            status('timeout_inconclusive', native_pid=child.pid)
            return
    elapsed = time.monotonic()-started
    if code != 0:
        status('native_nonpass', exit_code=code)
        return
    times, values = waveform(out/'benchmark.prn')
    assert times[-1] >= 10e-9-1e-15
    records = []
    for rising in (False, True):
        old = [t for t in crossings(reference_times, reference_values, .9, rising) if t <= 10e-9]
        new = crossings(times, values, .9, rising)
        records.append(dict(rising=rising, reference_edges_ns=[t*1e9 for t in old],
            benchmark_edges_ns=[t*1e9 for t in new], same_event_count=len(old)==len(new),
            paired_edge_shift_ps=[(b-a)*1e12 for a, b in zip(old, new)]))
    differences = []
    for t, value in zip(times, values):
        i = bisect.bisect_left(reference_times, t)
        if i == 0:
            estimate = reference_values[0]
        else:
            a, b = reference_times[i-1:i+1]
            estimate = reference_values[i-1]+(reference_values[i]-reference_values[i-1])*(t-a)/(b-a)
        differences.append(abs(value-estimate))
    for path, digest in pins.items():
        assert sha(Path(path)) == digest, path
    remaining()
    log = (out/'run.log').read_text()
    stats = {}
    for label in ('Number Successful Steps Taken', 'Number Linear Solves', 'Total Linear Solution Time'):
        matches = re.findall(re.escape(label)+r':\s*([0-9.eE+-]+)', log)
        if matches:
            stats[label] = float(matches[-1])
    artifacts = {str(p): sha(p) for p in out.iterdir() if p.is_file() and p.name != 'status.json'}
    save(out/'assessment.json', dict(input_sha256=pins, artifacts=artifacts,
        elapsed_s=elapsed, solver=args.solver, omp_num_threads=args.threads,
        raw_edge_comparison=records, maximum_interpolated_waveform_difference_v=max(differences),
        solver_statistics=stats, full_80ns_solver_comparison_complete=False,
        numerical_domain_enclosure_qualified=False, adopted=False, release_qualified=False, scope=__doc__))
    status('terminal_assessment', elapsed_s=elapsed)
    print(f'{args.solver}10ns benchmark complete in {elapsed:.2f}s', flush=True)


if __name__ == '__main__':
    main()
