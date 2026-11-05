#!/usr/bin/env python3
"""Validate and measure compiled merging of complete native charge shards.

Only consumed fields, ledgers and receipts are rehashed here. This is merge
algorithm evidence, not a replacement for full native-input qualification.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import shutil
import subprocess
import time
from common import ROOT, save, sha, verify
from compile_charge import pins
from compiled_charge_v2 import execute
from resources import lease
from resume_charge import validate_receipt

SOURCE = ROOT / 'tools/charge_compiler/merge_parallel.cpp'
HEADER = ROOT / 'tools/charge_compiler/json.hpp'


def run(source, output, memory_gib=16, reference=None, threads=16):
    source, out = Path(source).resolve(), Path(output).resolve()
    if threads not in (1,2,4,8,16,32):raise ValueError("invalid merge thread count")
    reference=Path(reference).resolve() if reference else None
    out.mkdir(parents=True, exist_ok=False)
    started = time.clock_gettime(time.CLOCK_BOOTTIME)
    deadline = started + 43200
    save(out / 'owner.json', dict(started_utc=datetime.now(timezone.utc).isoformat(),
         wall_limit_s=43200, automatic_identical_retry=False, memory_limit_GiB=memory_gib))

    def status(state, **kw):
        save(out / 'status.json', dict(state=state, elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started,
             release_qualified=False, **kw))

    def snapshot(paths):
        return {str(p): (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
                for p in paths for s in (p.stat(),)}

    try:
        with lease(max(2,threads), memory_gib, deadline):
            status('checking_completed_shard_proofs')
            spans = json.loads((source / 'ranges.json').read_text())
            meta = source / 'trace_metadata.json'
            metadata_hash = sha(meta)
            receipts = []
            compiler = Path(shutil.which('g++')).resolve()
            paths = [SOURCE, HEADER, Path(__file__).resolve(), compiler, meta, source / 'ranges.json']
            paths += [Path(__file__).with_name(n) for n in
                      ('common.py', 'compile_charge.py', 'compiled_charge.py', 'compiled_charge_v2.py',
                       'parallel_hash.py', 'resources.py', 'resume_charge.py')]
            consumed = {}
            for i, span in enumerate(spans):
                shard = source / f'worker_{i}'
                receipt_path = shard / 'assessment.json'
                proof = json.loads(receipt_path.read_text())
                validate_receipt(proof, span, metadata_hash)
                verify(proof['input_sha256'])
                paths.append(receipt_path)
                for name in ('fields.json', 'collapsed_matrix_ledger.json'):
                    path = shard / name
                    # A reused shard receipt can pin its resolved original path.
                    digest = proof['artifacts'].get(str(path)) or proof['artifacts'].get(str(path.resolve()))
                    if not digest:
                        raise ValueError('missing consumed shard artifact pin: ' + str(path))
                    consumed[str(path)] = digest
                    paths.append(path)
                receipts.append(proof)
            reference_proof=None
            if reference:
                reference_proof=json.loads((reference/'assessment.json').read_text())
                verify(reference_proof['input_sha256']);verify(reference_proof['artifacts'])
                reference_inputs={str(Path(p).resolve()):h for p,h in reference_proof['input_sha256'].items()}
                for path,digest in consumed.items():
                    if reference_inputs.get(str(Path(path).resolve()))!=digest:
                        raise ValueError('reference does not consume the same shard artifact: '+path)
                paths += [reference/'assessment.json',reference/'collapsed_matrix_ledger.json',reference/'fields.json',reference/'operators_manifest.json']
                paths += [reference/f'worker_{i}_field_map.json' for i in range(len(spans))]
            initial = snapshot(paths)
            input_pins = pins(paths, deadline, lambda **kw: status('hashing_consumed_shard_artifacts', **kw))
            if any(input_pins[k] != v for k, v in consumed.items()):
                raise ValueError('consumed shard artifact changed')
            save(out / 'input_manifest.json', dict(input_sha256=input_pins))
            for i in range(len(spans)):
                (out / f'worker_{i}').symlink_to(source / f'worker_{i}', target_is_directory=True)
            receipt_path = out / 'shard_receipts.json'
            save(receipt_path, receipts)
            binary = out / 'charge_merge'
            command = [str(compiler), '-std=c++20', '-O3', '-Wall', '-Wextra', '-Wpedantic',
                       '-fno-fast-math', '-ffp-contract=off', '-fopenmp', str(SOURCE), '-o', str(binary)]
            status('building_compiled_merge')
            execute(command, out / 'build.log', deadline, memory_gib)
            config = out / 'merge.config.json'
            settings=dict(output=str(out),receipts=str(receipt_path),deadline_uptime=deadline,threads=threads)
            if reference_proof:settings['reserve_rows']=reference_proof['consumed_local_ledger_rows']
            save(config,settings)
            status('merging_ordered_fields_and_ledgers')
            merge_start = time.clock_gettime(time.CLOCK_BOOTTIME)
            execute([binary, config], out / 'merge.log', deadline, memory_gib)
            merge_seconds = time.clock_gettime(time.CLOCK_BOOTTIME)-merge_start
            compared_rows=None
            if reference:
                status('comparing_every_reference_field_map_and_ledger_value')
                for name in ['fields.json','collapsed_matrix_ledger.json']+[f'worker_{i}_field_map.json' for i in range(len(spans))]:
                    if name.endswith('_field_map.json'):
                        if sha(out/name)!=sha(reference/name):raise ValueError('reference field map differs')
                    else:
                        log=out/(name+'.compare.log')
                        execute([binary,'compare',reference/name,out/name,deadline],log,deadline,memory_gib)
                        if name=='collapsed_matrix_ledger.json':compared_rows=json.loads(log.read_text())['identical_rows']
            merged = json.loads((out / 'operators_manifest.json').read_text())
            counts = merged['counts']
            if reference:
                ref_manifest=json.loads((reference/'operators_manifest.json').read_text())
                for key in ('counts','components','arithmetic_residual_absolute_native_cap_units'):
                    if merged[key]!=ref_manifest[key]:raise ValueError('reference aggregate differs: '+key)
            if (counts['kernels'] != spans[-1]['kernel_end']-1 or counts['events'] != spans[-1]['event_end']
                    or counts['owned_pair_kernels'] != spans[-1]['expected_owner_total']):
                raise ValueError('merged range coverage mismatch')
            if initial != snapshot(paths):
                raise ValueError('consumed merge inputs changed')
            summary = json.loads((out / 'merge_summary.json').read_text())
            artifacts = [binary, config, receipt_path, out / 'fields.json', out / 'collapsed_matrix_ledger.json',
                         out / 'operators_manifest.json', out / 'merge_summary.json']
            artifacts += [out / f'worker_{i}_field_map.json' for i in range(len(spans))]
            if reference:
                artifacts += [out/'fields.json.compare.log',out/'collapsed_matrix_ledger.json.compare.log']
            artifact_pins = pins(artifacts, deadline, lambda **kw: status('hashing_compiled_merge_artifacts', **kw))
            summary.update(input_sha256=input_pins, artifacts=artifact_pins, ordered_shards=len(spans),
                counts=counts, merge_seconds=merge_seconds, elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started,
                child_peak_rss_KiB=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                build_command=command, compiler_version=subprocess.check_output([str(compiler), '--version'], text=True),
                merge_threads=threads,full_reference_numeric_comparison=reference is not None,reference_ledger_rows_compared=compared_rows,
                full_native_inputs_rehashed=False, physical_domain_complete=False,
                global_passivity_qualified=False, runtime_model_eligible=False, release_qualified=False)
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('whole-check deadline exhausted during artifact hashing')
            save(out / 'assessment.json', summary)
            status('compiled_merge_terminal_pending_full_native_requalification',
                   global_fields=summary['global_fields'], global_ledger_rows=summary['global_ledger_rows'])
            return summary
    except BaseException as error:
        status('failed', reason=repr(error)); raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--reference',type=Path);p.add_argument('--threads',type=int,choices=(1,2,4,8,16,32),default=16)
    a = p.parse_args()
    result = run(a.source, a.output,reference=a.reference,threads=a.threads)
    print(json.dumps({k: result[k] for k in ('global_fields', 'global_ledger_rows', 'merge_seconds', 'elapsed_s')}))
