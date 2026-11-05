#!/usr/bin/env python3
"""Reuse verified completed shards; recompile only unfinished bounded ledgers.

A fresh 12-hour budget includes full input/artifact hashing, compilation, merge
and assessment. No partial worker is accepted as complete. Retained files and
old source are immutable; reused operator directories are referenced by links.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime,timezone
import json
import multiprocessing
import os
from pathlib import Path
import signal
import sys
import time
from common import ROOT,save,sha
from compile_charge import pins,terminate_children
from compiled_charge_v2 import build,compile_shard,execute,SOURCE
from resources import identity,lease,available_memory,GIB


def snapshot(paths):
    return {str(p):(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            for p in paths for s in (p.stat(),)}


def validate_receipt(report,span,metadata_sha256):
    if report.get('synthetic') or report.get('range_spec')!=span:
        raise ValueError('shard range identity mismatch')
    for flag in ('local_operator_integrals_match_native_physical_totals',
                 'finite_R_same_conductor_pair_energy_restored',
                 'aligned_events_have_owned_voltage_fields',
                 'owner_contact_fields_normalized_using_exact_observed_native_plane_residues'):
        if report.get(flag) is not True:raise ValueError('shard lacks native proof: '+flag)
    if report.get('units')!={'length_m':5e-9,'capacitance_F':1e-18}:
        raise ValueError('shard physical units mismatch')
    if not any(Path(p).name=='trace_metadata.json' and v==metadata_sha256
               for p,v in report.get('input_sha256',{}).items()):
        raise ValueError('shard native metadata mismatch')
    counts=report['counts']
    if counts['kernels']!=span['kernel_end']-span['kernel_start'] or counts['events']!=span['event_end']-span['event_start']:
        raise ValueError('shard count/range mismatch')


def run(prior,output,parallelism=16):
    prior,out=(Path(p).resolve() for p in (prior,output));out.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200;pool=None
    def status(state,**kw):
        save(out/'status.json',dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),
             elapsed_s=time.monotonic()-start,deadline_uptime=deadline,release_qualified=False,**kw))
    def interrupted(number,frame):raise InterruptedError('resume controller signal '+str(number))
    old={s:signal.signal(s,interrupted) for s in (signal.SIGALRM,signal.SIGINT,signal.SIGTERM)};signal.alarm(43200)
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),
         started_utc=datetime.now(timezone.utc).isoformat(),wall_limit_s=43200,deadline_uptime=deadline,
         prior_attempt=str(prior),automatic_identical_retry=False,
         changed_algorithm='bounded_streaming_ledger_serialization_with_verified_terminal_shard_reuse'))
    try:
        status('checking_terminal_prior_attempt')
        previous=json.loads((prior/'status.json').read_text());owner=json.loads((prior/'owner.json').read_text())
        if previous['state']!='failed' or identity(owner['pid'])==owner['birth']:
            raise ValueError('prior attempt is not terminal')
        if not any('std::bad_alloc' in p.read_text() for p in prior.glob('worker_*.log')):
            raise ValueError('bounded-ledger continuation requires the retained allocation failure')
        manifest=json.loads((prior/'input_manifest.json').read_text())
        expected=dict(manifest['input_sha256'])
        for path,digest in manifest['retained_input_sha256'].items():
            if path in expected and expected[path]!=digest:raise ValueError('conflicting retained input pins')
            expected[path]=digest
        originals=list(map(Path,expected))
        extras=[Path(__file__).resolve(),Path(__file__).with_name('compiled_charge_v2.py'),
                Path(__file__).with_name('merge_retained_charge.py'),Path(sys.executable).resolve(),SOURCE/'main_stream_ledger.cpp',
                prior/'status.json',prior/'owner.json',prior/'input_manifest.json',prior/'ranges.json',prior/'trace_metadata.json']
        paths=list(dict.fromkeys(originals+extras));initial=snapshot(paths)
        with lease(8,8,deadline):
            status('verifying_full_retained_inputs')
            actual=pins(originals,deadline,lambda **kw:status('verifying_full_retained_inputs',**kw))
            if actual!=expected:raise ValueError('retained native or source identity mismatch')
            input_pins=dict(actual);input_pins.update(pins(extras,deadline))
            save(out/'input_manifest.json',dict(input_sha256=input_pins,retained_input_sha256=manifest['retained_input_sha256']))
            spans=json.loads((prior/'ranges.json').read_text())
            if len(spans)!=owner['workers']:raise ValueError('range/worker matrix mismatch')
            save(out/'ranges.json',spans)
            meta=out/'trace_metadata.json';meta.write_bytes((prior/'trace_metadata.json').read_bytes());meta_sha=sha(meta)
            binary=build(out/'compiler');receipts=[None]*len(spans);pending=[];reused={}
            for i,span in enumerate(spans):
                old_shard=prior/f'worker_{i}';receipt=old_shard/'assessment.json'
                if not receipt.exists():pending.append(i);continue
                report=json.loads(receipt.read_text());validate_receipt(report,span,meta_sha)
                status('verifying_completed_shard',shard=i)
                for name in ('input_sha256','artifacts'):
                    expected_shard=report[name]
                    if pins(list(map(Path,expected_shard)),deadline)!=expected_shard:
                        raise ValueError('retained shard identity mismatch: '+str(i))
                required={str(old_shard/n) for n in ('operators.jsonl','fields.json','collapsed_matrix_ledger.json','observed_plane_residues.json')}
                if not required<=set(report['artifacts']):raise ValueError('shard lacks complete artifact coverage')
                (out/f'worker_{i}').symlink_to(old_shard,target_is_directory=True)
                receipts[i]=report;reused[str(i)]=dict(receipt=str(receipt),sha256=sha(receipt),source=str(old_shard))
            save(out/'reuse_manifest.json',dict(shards=reused,recompile_indices=pending,partial_shards_reused=False))
        if pending:
            workers=min(parallelism,len(pending));trace=Path(owner['source'])/'trace'
            with lease(workers,workers*4,deadline):
                pool=ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn'))
                futures={i:pool.submit(compile_shard,binary,trace,out/f'worker_{i}',deadline,spans[i],meta,4) for i in pending}
                while not all(f.done() for f in futures.values()):
                    for future in futures.values():
                        if future.done():future.result()
                    if available_memory()<32*GIB:raise MemoryError('host memory reserve below 32 GiB')
                    status('compiling_unfinished_shards',reused_shards=len(reused),workers=workers,
                           completed_new_shards=sum(f.done() for f in futures.values()));time.sleep(.5)
                for i,future in futures.items():receipts[i]=future.result();validate_receipt(receipts[i],spans[i],meta_sha)
                pool.shutdown();pool=None
        receipt_path=out/'shard_receipts.json';save(receipt_path,receipts)
        with lease(2,32,deadline):
            status('merging_field_maps_and_ledgers',merge_memory_limit_GiB=32)
            execute([sys.executable,Path(__file__).with_name('merge_retained_charge.py'),'--output',out,
                     '--receipts',receipt_path],out/'merge.log',deadline,32)
            merged=json.loads((out/'operators_manifest.json').read_text());counts=merged['counts']
            if (counts['kernels']!=spans[-1]['kernel_end']-1 or counts['events']!=spans[-1]['event_end'] or
                counts['owned_pair_kernels']!=spans[-1]['expected_owner_total']):
                raise ValueError('merged global native coverage mismatch')
            if initial!=snapshot(paths):raise ValueError('retained inputs changed during continuation')
            artifacts=[out/n for n in ('ranges.json','trace_metadata.json','reuse_manifest.json','shard_receipts.json',
                       'operators_manifest.json','fields.json','collapsed_matrix_ledger.json')]
            artifacts += [out/f'worker_{i}_field_map.json' for i in range(len(spans))]
            artifacts += [out/f'worker_{i}/assessment.json' for i in range(len(spans))]
            save(out/'assessment.json',dict(input_sha256=input_pins,artifacts=pins(artifacts,deadline),
                workers=len(spans),reused_completed_shards=len(reused),recompiled_shards=len(pending),
                worker_artifacts_pinned_by_shard_assessments=True,all_ranges_compiled=True,
                local_operator_integrals_match_native_physical_totals=True,counts=counts,
                physical_domain_complete=False,global_passivity_qualified=False,runtime_model_eligible=False,
                release_qualified=False,elapsed_s=time.monotonic()-start))
        status('compiled_pending_R_domain_attachment',counts=counts)
    except BaseException as error:
        terminate_children(out)
        if pool is not None:pool.shutdown(wait=True,cancel_futures=True)
        status('failed',reason=repr(error));raise
    finally:
        signal.alarm(0)
        for s,handler in old.items():signal.signal(s,handler)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prior',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--parallelism',type=int,default=16,choices=(1,2,4,8,16))
    a=p.parse_args();run(a.prior,a.output,a.parallelism)


if __name__=='__main__':main()
