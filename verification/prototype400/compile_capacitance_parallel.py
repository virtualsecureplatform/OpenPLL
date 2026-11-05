#!/usr/bin/env python3
"""Four-process compilation of retained native C traces; no native rerun.

Operator rows retain local field IDs. The manifest supplies an explicit map
to global field IDs for each ordered shard; concatenation without remapping
is invalid. This receipt does not qualify a complete physical model.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
import multiprocessing
import os
from pathlib import Path
import signal
import sys
import time

from common import ROOT, save, sha, verify
from status_store import update_root
sys.path.insert(0, str(ROOT/'verification/timing400'))
from compile_local_C_operators_v6 import compile_trace
from parallel_C_trace_ranges import metadata, partition


def merge(output, receipts):
    """Merge small ledgers and field maps; keep large operator files sharded."""
    fields, field_ids, mappings = [], {}, []
    count, reasons, residuals = Counter(), Counter(), defaultdict(float)
    ledger = defaultdict(lambda: [0., 0., 0.])
    for i, receipt in enumerate(receipts):
        shard = output/f'worker_{i}'
        mapping = []
        for value in json.loads((shard/'fields.json').read_text()):
            key = tuple(value)
            if key not in field_ids:
                field_ids[key] = len(fields)
                fields.append(value)
            mapping.append(field_ids[key])
        assert mapping[0] == 0
        mapping_path = output/f'worker_{i}_field_map.json'
        save(mapping_path, mapping)
        mappings.append(dict(operators=str(shard/'operators.jsonl'),
                             field_map=str(mapping_path), range_spec=receipt['range_spec']))
        count.update(receipt['counts'])
        reasons.update(receipt['components'])
        for k, v in receipt['arithmetic_residual_absolute_native_cap_units'].items():
            residuals[k] += v
        for a, b, *values in json.loads((shard/'collapsed_matrix_ledger.json').read_text()):
            key = tuple(sorted((mapping[a], mapping[b])))
            row = ledger[key]
            for j, value in enumerate(values):
                row[j] += value
    save(output/'fields.json', fields)
    save(output/'collapsed_matrix_ledger.json', [[*k, *v] for k, v in sorted(ledger.items())])
    value = dict(format='ordered_operator_shards_with_local_to_global_field_maps_v1',
                 shards=mappings, fields=str(output/'fields.json'), counts=dict(count),
                 components=dict(reasons), arithmetic_residual_absolute_native_cap_units=dict(residuals))
    save(output/'operators_manifest.json', value)
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--workers', type=int, choices=[4], default=4)
    a = p.parse_args()
    source, out = a.source.resolve(), a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    start = datetime.now(timezone.utc)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(out/'owner.json', dict(pid=os.getpid(), started_utc=start.isoformat(), wall_limit_s=43200,
         deadline_uptime=deadline, workers=a.workers, automatic_identical_retry=False,
         changed_algorithm='four_process_aligned_byte_ranges', previous_attempt=str(source)))
    pool = None
    def status(state, **kw):
        value = dict(state=state, observed_utc=datetime.now(timezone.utc).isoformat(),
                     release_qualified=False, **kw)
        save(out/'status.json', value)
        update_root('owned_capacitance_trace', dict(value, path=str(out/'status.json')))
    def expired(*_):
        raise TimeoutError('parallel compilation 12h whole-check deadline exhausted')
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(43200)
    try:
        # The previous controller reached compilation only after exact C/device
        # comparison. Preserve that evidence and verify its pinned native inputs.
        previous = json.loads((source/'status.json').read_text())
        assert previous['state'] == 'failed' and 'TimeoutError' in previous['reason']
        assert (source/'trace/node_ids.json').exists()
        assert 'FILLED_OWNER_C_NATIVE_COMPLETE' in (source/'trace/extract.log').read_text()
        assert "in compile_trace" in (source.parent/(source.name+'_launch.log')).read_text()
        status('verifying_retained_native_inputs')
        verify(json.loads((source/'input_manifest.json').read_text())['input_sha256'])
        trace = source/'trace'
        inputs = [trace/n for n in ['node_ids.json', 'kernels.log', 'surfaces.log', 'contributions.log', 'owners.log']]
        inputs += [source/'input_manifest.json', source/'status.json', Path(__file__).resolve(),
                   Path(__file__).with_name('common.py'), Path(__file__).with_name('status_store.py'),
                   ROOT/'verification/timing400/compile_local_C_operators_v6.py',
                   ROOT/'verification/timing400/parallel_C_trace_ranges.py',
                   ROOT/'verification/timing400/verify_magic_C_kernel_trace_v2.py',
                   ROOT/'verification/timing400/verify_magic_C_owners.py']
        initial = {str(f): (f.stat().st_size, f.stat().st_mtime_ns) for f in inputs}
        status('indexing_four_aligned_stream_ranges')
        specs = partition(trace, a.workers, deadline)
        save(out/'ranges.json', specs)
        status('reading_shared_surface_metadata')
        meta = out/'trace_metadata.json'
        save(meta, metadata(trace))
        pool = ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context('spawn'))
        futures = [pool.submit(compile_trace, trace, out/f'worker_{i}', deadline, None, spec, meta)
                   for i, spec in enumerate(specs)]
        status('compiling_four_parallel_workers', workers=4)
        while not all(f.done() for f in futures):
            for future in futures:
                if future.done():
                    future.result()  # Fail promptly if any worker fails.
            # Bound total memory instead of risking the shared host's OOM killer.
            rss = 0
            for process in pool._processes.values():
                try:
                    rss += int(Path(f'/proc/{process.pid}/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
                except FileNotFoundError:
                    pass
            available = next(int(row.split()[1])*1024 for row in Path('/proc/meminfo').read_text().splitlines()
                             if row.startswith('MemAvailable:'))
            if rss > 40*1024**3 or available < 4*1024**3:
                raise MemoryError('four-worker memory guard: aggregate RSS >40 GiB or available RAM <4 GiB')
            time.sleep(5)
        receipts = [f.result() for f in futures]
        pool.shutdown(); pool = None
        status('merging_field_maps_and_ledgers')
        merged = merge(out, receipts)
        assert merged['counts']['kernels'] == specs[-1]['kernel_end']-1
        assert merged['counts']['events'] == specs[-1]['event_end']
        assert merged['counts']['owned_pair_kernels'] == specs[-1]['expected_owner_total']
        status('hashing_completed_parallel_evidence')
        pins = {str(f): sha(f) for f in inputs}
        assert initial == {str(f): (f.stat().st_size, f.stat().st_mtime_ns) for f in inputs}
        artifacts = [out/n for n in ['ranges.json', 'trace_metadata.json', 'operators_manifest.json',
                     'fields.json', 'collapsed_matrix_ledger.json']]
        artifacts += [out/f'worker_{i}_field_map.json' for i in range(4)]
        artifacts += [out/f'worker_{i}/assessment.json' for i in range(4)]
        save(out/'assessment.json', dict(input_sha256=pins, artifacts={str(f): sha(f) for f in artifacts},
             worker_artifacts_pinned_by_shard_assessments=True,
             workers=4, native_extraction_reused=True, all_ranges_compiled=True,
             local_operator_integrals_match_native_physical_totals=True,
             counts=merged['counts'], physical_domain_complete=False,
             full_C_energy_matrix_assembled=False, global_passivity_qualified=False,
             runtime_model_eligible=False, release_qualified=False))
        status('owned_capacitance_operators_terminal_pending_R_domain_attachment', counts=merged['counts'])
    except BaseException as e:
        if pool:
            for process in list(pool._processes.values()):
                process.terminate()
            pool.shutdown(wait=True, cancel_futures=True)
        status('failed', reason=repr(e))
        raise
    finally:
        signal.alarm(0)


if __name__ == '__main__':
    main()
