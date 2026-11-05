#!/usr/bin/env python3
"""Measure the full independent Python baseline on an already retained sample."""
import argparse
import json
from itertools import zip_longest
from pathlib import Path
import sys
import time

from common import ROOT, save, sha
from resources import lease
from benchmark_charge import compare
sys.path.append(str(ROOT/'verification/timing400'))
from compile_local_C_operators_v6 import compile_trace
from parallel_C_trace_ranges import partition


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--benchmark',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    benchmark=a.benchmark.resolve();summary=json.loads((benchmark/'assessment.json').read_text())
    trace=benchmark/'trace';native=benchmark/'workers_1/worker_0'
    if not summary['python_native_comparison_passed'] or not native.exists():
        raise ValueError('completed retained native prefix benchmark with serial C++ output required')
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(out/'status.json',dict(state='running_python_reference',release_qualified=False))
    started=time.monotonic()
    with lease(1,4,deadline):
        span=partition(trace,1,deadline)[0]
        expected=compile_trace(trace,out/'python',deadline,None,span,benchmark/'metadata.json')
        elapsed=time.monotonic()-started
        actual=json.loads((native/'assessment.json').read_text())
        for key in ('counts','components','arithmetic_residual_absolute_native_cap_units'):
            compare(expected[key],actual[key])
        for name in ('fields.json','collapsed_matrix_ledger.json','observed_plane_residues.json'):
            compare(json.loads((out/'python'/name).read_text()),json.loads((native/name).read_text()))
        with (out/'python/operators.jsonl').open() as py,(native/'operators.jsonl').open() as cpp:
            for x,y in zip_longest(py,cpp):
                if x is None or y is None:raise ValueError('operator count mismatch')
                compare(json.loads(x),json.loads(y))
    trials=summary['trials'];best=min(trials,key=lambda r:r['elapsed_s'])
    save(out/'assessment.json',dict(input_sha256={str(benchmark/'assessment.json'):sha(benchmark/'assessment.json'),
         str(native/'assessment.json'):sha(native/'assessment.json')},
         artifacts={str(out/'python/assessment.json'):sha(out/'python/assessment.json')},
         kernels=expected['counts']['kernels'],python_elapsed_s=elapsed,
         serial_compiled_elapsed_s=next(r['elapsed_s'] for r in trials if r['workers']==1),
         parallel_compiled_elapsed_s=best['elapsed_s'],parallel_workers=best['workers'],
         end_to_end_speedup=elapsed/best['elapsed_s'],all_native_operators_match_python=True,
         release_qualified=False))
    save(out/'status.json',dict(state='python_reference_complete',release_qualified=False))


if __name__=='__main__':main()
