#!/usr/bin/env python3
"""Compile retained native extraction using bounded multicore C++ workers."""
import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import json
import multiprocessing
import os
from pathlib import Path
import signal
import sys
import threading
import time

from common import ROOT, save, sha, verify
from compiled_charge_v2 import build, compile_shard, execute, SOURCE
from resources import GIB, available_memory, identity, lease
from parallel_hash import sha_prefetch
from compiled_partition import partition

sys.path.append(str(ROOT / 'verification/prototype400'))
sys.path.append(str(ROOT / 'verification/timing400'))
from compile_capacitance_parallel import merge


def snapshot(paths):
    return {str(p): (p.stat().st_dev,p.stat().st_ino,p.stat().st_size,p.stat().st_mtime_ns,p.stat().st_ctime_ns) for p in paths}


def pins(paths, deadline=None, progress=None):
    cancel=threading.Event()
    def digest(path):
        return sha_prefetch(path,deadline=deadline,cancel=cancel) if path.stat().st_size>=64*1024**2 else sha(path)
    pool=ThreadPoolExecutor(max_workers=min(8,len(paths)));futures={pool.submit(digest,p):p for p in paths};result={}
    pending=set(futures)
    try:
        while pending:
            completed,pending=wait(pending,timeout=2,return_when=FIRST_COMPLETED)
            for future in completed:result[str(futures[future])]=future.result()
            if progress:progress(completed_files=len(result),total_files=len(paths))
        return result
    except BaseException:
        cancel.set()
        raise
    finally:
        pool.shutdown(wait=True,cancel_futures=True)


def terminate_children(out):
    # Workers publish process birth identities; never signal a reused/unrelated PID.
    for record in out.glob('worker_*.process.json'):
        info = json.loads(record.read_text())
        if identity(info['pid']) == info['birth']:
            try:
                os.killpg(info['process_group'], signal.SIGTERM)
            except ProcessLookupError:
                pass



def validate_native_source(source):
    source=Path(source).resolve()
    report=json.loads((source/'assessment.json').read_text())
    state=json.loads((source/'status.json').read_text())['state']
    if state!='native_owned_trace_terminal_pending_compiled_operators':
        raise ValueError('expected completed native owned trace')
    for flag in ('native_C_and_device_cards_unchanged','native_owned_trace_complete','original_floating_nodes_preserved'):
        if report.get(flag) is not True:raise ValueError('native proof missing: '+flag)
    if report.get('synthetic'):raise ValueError('synthetic source is not native evidence')
    runner=ROOT/'verification/prototype400/trace_filled_capacitance_v3.py'
    if report['input_sha256'].get(str(runner))!=sha(runner):
        raise ValueError('native generator source identity mismatch')
    for name in ('node_ids.json','kernels.log','surfaces.log','contributions.log','owners.log','extract.log'):
        if str(source/'trace'/name) not in report['artifacts']:
            raise ValueError('native artifact pin missing: '+name)
    if 'FILLED_OWNER_C_NATIVE_COMPLETE' not in (source/'trace/extract.log').read_text():
        raise ValueError('native owned-C extraction is incomplete')
    return report


def run(source, output, workers=32, memory_gib=4, wall_limit_s=43200, binary=None):
    source, out = Path(source).resolve(), Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + wall_limit_s
    pool = None
    def status(state, **kw):
        save(out / 'status.json', dict(state=state, observed_utc=datetime.now(timezone.utc).isoformat(),
                                      elapsed_s=time.monotonic()-start, deadline_uptime=deadline,
                                      release_qualified=False, **kw))
    def interrupted(number, frame):
        raise InterruptedError('controller interrupted by signal ' + str(number))
    old = {s: signal.signal(s, interrupted) for s in (signal.SIGTERM, signal.SIGINT, signal.SIGALRM)}
    signal.alarm(max(1, int(wall_limit_s)))
    save(out / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid()),
         started_utc=datetime.now(timezone.utc).isoformat(), workers=workers,
         worker_memory_limit_GiB=memory_gib, wall_limit_s=wall_limit_s,
         deadline_uptime=deadline, automatic_identical_retry=False,
         changed_algorithm='direct_native_receipt_bounded_ledger_cpp_v3', source=str(source)))
    try:
        status('checking_retained_extraction')
        native = validate_native_source(source)
        original = native['input_sha256']
        trace = source / 'trace'
        inputs = [trace / name for name in ('node_ids.json', 'kernels.log', 'surfaces.log', 'contributions.log', 'owners.log')]
        inputs += [source / 'input_manifest.json', source / 'assessment.json', source / 'status.json', source / 'trace/extract.log',
                   Path(__file__).resolve(), SOURCE / 'main_stream_ledger.cpp', SOURCE / 'json.hpp',
                   Path(__file__).with_name('compiled_charge_v2.py'), Path(__file__).with_name('compiled_charge.py'), Path(__file__).with_name('resources.py'),
                   Path(__file__).with_name('common.py'),
                   Path(__file__).with_name('compiled_partition.py'),Path(__file__).with_name('parallel_hash.py'),
                   ROOT / 'verification/timing400/parallel_C_trace_ranges.py',
                   ROOT / 'verification/prototype400/compile_capacitance_parallel.py',
                   Path(__file__).with_name('merge_retained_charge.py'),Path(sys.executable).resolve()]
        initial = snapshot(inputs)
        with lease(8, 8, deadline):
            original_paths = list(map(Path, original))
            if pins(original_paths,deadline,lambda **kw:status('verifying_retained_dependencies',**kw)) != original:
                raise ValueError('retained extraction dependency identity mismatch')
            input_pins = pins(inputs,deadline,lambda **kw:status('hashing_trace_inputs',**kw))
            for path in [trace / name for name in ('node_ids.json','kernels.log','surfaces.log','contributions.log','owners.log','extract.log')]:
                if native['artifacts'].get(str(path)) != input_pins[str(path)]:
                    raise ValueError('native artifact identity mismatch: '+str(path))
            save(out / 'input_manifest.json', dict(input_sha256=input_pins, retained_input_sha256=original))
            binary = Path(binary).resolve() if binary else build(out / 'compiler')
            status('indexing_aligned_streams')
            spans = partition(trace, workers, deadline, binary, out)
            save(out / 'ranges.json', spans)
            meta = out / 'trace_metadata.json'
            execute([binary, 'metadata', trace, meta, deadline], out / 'metadata.log', deadline, memory_gib)
        status('waiting_for_parallel_resources', workers=workers)
        with lease(workers, workers * memory_gib, deadline, cpu_limit=64 if workers == 64 else 32):
            pool = ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'))
            futures = [pool.submit(compile_shard, binary, trace, out / f'worker_{i}', deadline, span, meta, memory_gib)
                       for i, span in enumerate(spans)]
            while not all(f.done() for f in futures):
                for future in futures:
                    if future.done():
                        future.result()
                if available_memory() < 32 * GIB:
                    raise MemoryError('host memory reserve below 32 GiB')
                status('compiling_native_workers', workers=workers,
                       completed_shards=sum(f.done() for f in futures))
                time.sleep(.5)
            receipts = [f.result() for f in futures]
            pool.shutdown()
            pool = None
        with lease(2, 32, deadline):
            status('merging_field_maps_and_ledgers')
            receipt_path=out/'shard_receipts.json';save(receipt_path,receipts)
            execute([sys.executable,Path(__file__).with_name('merge_retained_charge.py'),'--output',out,
                     '--receipts',receipt_path],out/'merge.log',deadline,32)
            merged=json.loads((out/'operators_manifest.json').read_text())
            counts = merged['counts']
            if (counts['kernels'] != spans[-1]['kernel_end']-1 or counts['events'] != spans[-1]['event_end']
                    or counts['owned_pair_kernels'] != spans[-1]['expected_owner_total']):
                raise ValueError('compiled range coverage mismatch')
            if initial != snapshot(inputs):
                raise ValueError('retained extraction changed during compilation')
            artifacts = [out / n for n in ('ranges.json', 'trace_metadata.json', 'operators_manifest.json',
                                          'fields.json', 'collapsed_matrix_ledger.json',
                                          'native_index.config.json','native_index.json')]
            artifacts += [out / f'worker_{i}_field_map.json' for i in range(workers)]
            artifacts += [out / f'worker_{i}/assessment.json' for i in range(workers)]
            save(out / 'assessment.json', dict(input_sha256=input_pins,
                 retained_input_sha256=original, artifacts=pins(artifacts,deadline), workers=workers,
                 compiler_binary_sha256=sha(binary), native_extraction_reused=True,
                 worker_artifacts_pinned_by_shard_assessments=True, all_ranges_compiled=True,
                 local_operator_integrals_match_native_physical_totals=True,
                 elapsed_s=time.monotonic()-start, kernels_per_second=counts['kernels']/(time.monotonic()-start),
                 counts=counts, physical_domain_complete=False, full_C_energy_matrix_assembled=False,
                 global_passivity_qualified=False, runtime_model_eligible=False, release_qualified=False))
        status('compiled_pending_R_domain_attachment', counts=counts)
    except BaseException as error:
        terminate_children(out)
        if pool is not None:
            pool.shutdown(wait=True, cancel_futures=True)
        status('stopped_by_user' if isinstance(error, (KeyboardInterrupt, InterruptedError)) else 'failed', reason=repr(error))
        raise
    finally:
        signal.alarm(0)
        for s, handler in old.items():
            signal.signal(s, handler)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--workers', type=int, choices=(1, 8, 16, 32, 64), default=16)
    p.add_argument('--worker-memory-gib', type=float, default=4)
    a = p.parse_args()
    if not 0 < a.worker_memory_gib <= 200 / a.workers:
        p.error('worker memory exceeds the aggregate 200 GiB budget')
    run(a.source, a.output, a.workers, a.worker_memory_gib)


if __name__ == '__main__':
    main()
