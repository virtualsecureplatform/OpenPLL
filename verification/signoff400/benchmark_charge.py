#!/usr/bin/env python3
"""Benchmark real retained prefixes, with independent Python/native comparison."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import math
import multiprocessing
from pathlib import Path
import shutil
import sys
import time

from common import ROOT, save, sha
from compiled_charge import build, compile_shard, execute
from resources import lease

sys.path.append(str(ROOT / 'verification/prototype400'))
sys.path.append(str(ROOT / 'verification/timing400'))
from compile_local_C_operators_v6 import compile_trace
from parallel_C_trace_ranges import partition


def prefix(source, target, limit):
    """Copy a complete aligned prefix, preserving every retained native record."""
    target.mkdir()
    shutil.copyfile(source / 'node_ids.json', target / 'node_ids.json')
    kernels = events = owners = 0
    with (source / 'kernels.log').open('rb') as src, (target / 'kernels.log').open('wb') as dst:
        for line in src:
            if line.startswith(b'END '):
                break
            if line.startswith(b'KERNEL '):
                if kernels == limit:
                    break
                kernels += 1
            if line.startswith(b'EVENT '):
                events += 1
            dst.write(line)
        dst.write(f'END {events} {kernels}\n'.encode())
    for name in ('owners', 'surfaces', 'contributions'):
        with (source / (name+'.log')).open('rb') as src, (target / (name+'.log')).open('wb') as dst:
            captured = 0
            for line in src:
                if name == 'owners':
                    if line.startswith(b'END '): break
                    if line.startswith(b'OWNER '):
                        if int(line.split()[1]) > kernels: break
                        owners += 1
                elif name == 'surfaces':
                    if line.startswith(b'END '): break
                    if line.startswith(b'SURFACE '):
                        if int(line.split()[1]) > events: break
                        captured += 1
                elif line.startswith((b'OPENPLL_G ', b'OPENPLL_P ')):
                    if captured == events: break
                    captured += 1
                dst.write(line)
            if name == 'owners': dst.write(f'END {owners} {kernels}\n'.encode())
            elif name == 'surfaces':
                if captured != events: raise ValueError('incomplete surface prefix')
                dst.write(f'END {events}\n'.encode())
            else:
                if captured != events: raise ValueError('incomplete native prefix')
                dst.write(b'OPENPLL_END\n')
    return dict(kernels=kernels, events=events, owners=owners)


def compare(expected, actual):
    if isinstance(expected, dict):
        if expected.keys() != actual.keys(): raise ValueError('different keys')
        for k in expected: compare(expected[k], actual[k])
    elif isinstance(expected, list):
        if len(expected) != len(actual): raise ValueError('different lengths')
        for a, b in zip(expected, actual): compare(a, b)
    elif isinstance(expected, float):
        if not math.isclose(expected, actual, rel_tol=2e-12, abs_tol=1e-8):
            raise ValueError('numerical reference mismatch')
    elif expected != actual: raise ValueError('identity reference mismatch')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trace', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--kernels', type=int, default=2_000_000)
    p.add_argument('--workers', type=int, nargs='+', default=[1, 8, 16, 32, 64])
    a = p.parse_args()
    if a.kernels < 10000 or any(n not in (1, 8, 16, 32, 64) for n in a.workers):
        p.error('require >=10000 kernels and workers in 1/8/16/32/64')
    out = a.output.resolve();out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 43200
    def status(state, **kw):
        save(out/'status.json', dict(state=state, release_qualified=False, **kw))
    original_hook = sys.excepthook
    def failed(kind, error, traceback):
        status('failed', reason=repr(error))
        original_hook(kind, error, traceback)
    sys.excepthook = failed
    status('copying_retained_native_prefix')
    binary = build(out/'compiler')
    trace = out/'trace'
    with lease(1, 4, deadline):
        sample = prefix(a.trace.resolve(), trace, a.kernels)
        meta = out/'metadata.json'
        execute([binary, 'metadata', trace, meta, deadline], out/'metadata.log', deadline)
        # Compare a smaller actual native prefix without spending the CAD budget in Python.
        control = out/'control_trace'
        prefix(trace, control, min(10000, a.kernels))
        control_meta = out/'control_metadata.json'
        execute([binary, 'metadata', control, control_meta, deadline], out/'control_metadata.log', deadline)
        span = partition(control, 1, deadline)[0]
        started = time.monotonic()
        py = compile_trace(control, out/'python_reference', deadline, None, span, control_meta)
        py_seconds = time.monotonic()-started
        cpp = compile_shard(binary, control, out/'compiled_control', deadline, span, control_meta)
        for key in ('counts', 'components', 'arithmetic_residual_absolute_native_cap_units'):
            compare(py[key], cpp[key])
        for name in ('fields.json', 'collapsed_matrix_ledger.json', 'observed_plane_residues.json'):
            compare(json.loads((out/'python_reference'/name).read_text()),
                    json.loads((out/'compiled_control'/name).read_text()))
        with (out/'python_reference/operators.jsonl').open() as gold, (out/'compiled_control/operators.jsonl').open() as native:
            from itertools import zip_longest
            for x,y in zip_longest(gold,native):
                if x is None or y is None: raise ValueError('operator count mismatch')
                compare(json.loads(x),json.loads(y))
    trials=[]
    for workers in a.workers:
        group=out/f'workers_{workers}';group.mkdir()
        status('benchmarking', workers=workers, trials=trials)
        started=time.monotonic()
        with lease(workers, workers*2, deadline, cpu_limit=64 if workers==64 else 32):
            spans=partition(trace, workers, deadline)
            with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn')) as pool:
                futures=[pool.submit(compile_shard,binary,trace,group/f'worker_{i}',deadline,s,meta,2)
                         for i,s in enumerate(spans)]
                receipts=[f.result() for f in futures]
        elapsed=time.monotonic()-started
        if sum(r['counts']['kernels'] for r in receipts)!=sample['kernels']:
            raise ValueError('benchmark kernel coverage')
        trials.append(dict(workers=workers, elapsed_s=elapsed, kernels_per_second=sample['kernels']/elapsed,
                           maximum_worker_rss_KiB=max(r['child_peak_rss_KiB'] for r in receipts)))
    by_workers={r['workers']:r for r in trials}
    eligible=[r for r in trials if r['workers']<=32]
    selected=max(eligible,key=lambda r:r['kernels_per_second'])['workers']
    if 32 in by_workers and 64 in by_workers and by_workers[64]['kernels_per_second']>=1.1*by_workers[32]['kernels_per_second']:
        if by_workers[64]['kernels_per_second']>=by_workers[selected]['kernels_per_second']:
            selected=64
    save(out/'assessment.json', dict(real_native_prefix=True, sample=sample, trials=trials,
         python_reference_seconds=py_seconds, compiled_control_seconds=cpp['elapsed_s'],
         reference_speedup=py_seconds/cpp['elapsed_s'], python_native_comparison_passed=True,
         recommended_workers=selected, benchmark_scope='retained prefix; full-trace scaling remains measured separately',
         input_sha256={str(p):sha(p) for p in trace.iterdir()},
         compiler_binary_sha256=sha(binary), release_qualified=False))
    status('benchmark_complete', recommended_workers=selected, trials=trials)


if __name__=='__main__':
    main()
