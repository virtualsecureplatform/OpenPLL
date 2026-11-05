#!/usr/bin/env python3
"""Requalify a compiled merge against all retained native inputs and shards.

Inherit the original failed continuation's deadline. Never regenerate shards
or reset the whole-check budget. Electrical-domain qualification stays open.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import sys
import time
from common import ROOT, save, sha
from compile_charge import pins
from resources import identity, lease
from resume_charge import validate_receipt



def require_native_artifacts(receipt):
    roles={Path(p).name for p in receipt['artifacts']}
    if not {'operators.jsonl','fields.json','collapsed_matrix_ledger.json','observed_plane_residues.json'} <= roles:
        raise ValueError('incomplete native shard artifact roles')


def run(prior, merge, output):
    prior, merge, out = (Path(p).resolve() for p in (prior, merge, output))
    out.mkdir(parents=True, exist_ok=False)
    started = time.clock_gettime(time.CLOCK_BOOTTIME)
    owner = json.loads((prior / 'owner.json').read_text())
    deadline = owner['deadline_uptime']
    save(out / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid()),
         started_utc=datetime.now(timezone.utc).isoformat(), budget_started_utc=owner['started_utc'],
         deadline_uptime=deadline, wall_limit_s=owner['wall_limit_s'], original_owner=str(prior / 'owner.json'),
         changed_algorithm='verified_bounded_cpp_merge_without_shard_regeneration', automatic_identical_retry=False))

    def status(state, **kw):
        save(out / 'status.json', dict(state=state, observed_utc=datetime.now(timezone.utc).isoformat(),
             elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started, deadline_uptime=deadline,
             release_qualified=False, **kw))

    def snapshot(paths):
        return {str(p): (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
                for p in paths for s in (p.stat(),)}

    def interrupted(number, frame):
        raise InterruptedError('retained merge validation signal ' + str(number))

    old = {s: signal.signal(s, interrupted) for s in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT)}
    try:
        if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            raise TimeoutError('original whole-check budget exhausted')
        signal.alarm(max(1, int(deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
        state = json.loads((prior / 'status.json').read_text())
        if state['state'] != 'failed' or identity(owner['pid']) == owner['birth']:
            raise ValueError('prior continuation is not terminal')
        if 'MemoryError' not in (prior / 'merge.log').read_text():
            raise ValueError('expected retained bounded Python merge allocation failure')
        proof = json.loads((merge / 'assessment.json').read_text())
        if proof.get('runtime_model_eligible') is not False or proof.get('release_qualified') is not False:
            raise ValueError('merge receipt must retain unqualified scope')
        spans = json.loads((prior / 'ranges.json').read_text())
        if proof['ordered_shards'] != len(spans):
            raise ValueError('merge shard matrix mismatch')
        for i in range(len(spans)):
            receipt = prior / f'worker_{i}/assessment.json'
            if proof['input_sha256'].get(str(receipt)) != sha(receipt):
                raise ValueError('merge does not pin selected shard receipt')
        expected = {}

        def add(table):
            for name, digest in table.items():
                if name in expected and expected[name] != digest:
                    raise ValueError('conflicting retained identity: ' + name)
                expected[name] = digest

        manifest = json.loads((prior / 'input_manifest.json').read_text())
        add(manifest['input_sha256']); add(manifest['retained_input_sha256'])
        add(proof['input_sha256']); add(proof['artifacts'])
        meta_hash = sha(prior / 'trace_metadata.json')
        receipts = []
        for i, span in enumerate(spans):
            receipt_path = prior / f'worker_{i}/assessment.json'
            receipt = json.loads(receipt_path.read_text())
            validate_receipt(receipt, span, meta_hash)
            require_native_artifacts(receipt)
            add({str(receipt_path): sha(receipt_path)})
            add(receipt['input_sha256']); add(receipt['artifacts'])
            receipts.append(receipt)
        paths = [Path(__file__).resolve(), Path(sys.executable).resolve(),
                 prior / 'owner.json', prior / 'status.json', prior / 'input_manifest.json', prior / 'merge.log',
                 prior / 'ranges.json', prior / 'trace_metadata.json', merge / 'assessment.json']
        paths += [Path(__file__).with_name(n) for n in
                  ('common.py', 'compile_charge.py', 'compiled_charge.py', 'parallel_hash.py', 'resources.py', 'resume_charge.py')]
        add({str(p): sha(p) for p in paths})
        # Hash each physical file once; retain alias identities in the manifest.
        canonical = {}
        aliases = {}
        for name, digest in expected.items():
            resolved = str(Path(name).resolve())
            if resolved in canonical and canonical[resolved] != digest:
                raise ValueError('conflicting resolved input identity')
            canonical[resolved] = digest
            aliases[name] = resolved
        all_paths = list(map(Path, expected))
        initial = snapshot(all_paths)
        with lease(8, 8, deadline):
            status('verifying_full_native_inputs_shards_and_merge')
            actual = pins(list(map(Path, canonical)), deadline,
                          lambda **kw: status('verifying_full_native_inputs_shards_and_merge', **kw))
            if actual != canonical:
                raise ValueError('native, shard or compiled-merge artifact identity mismatch')
            if initial != snapshot(all_paths):
                raise ValueError('retained inputs changed during full validation')
            save(out / 'input_manifest.json', dict(input_sha256=actual, retained_aliases=aliases))
            for name in ('ranges.json', 'trace_metadata.json'):
                (out / name).write_bytes((prior / name).read_bytes())
            for name in ('fields.json', 'collapsed_matrix_ledger.json'):
                (out / name).symlink_to((merge / name).resolve())
            artifacts = [out / 'ranges.json', out / 'trace_metadata.json', out / 'fields.json', out / 'collapsed_matrix_ledger.json']
            for i in range(len(spans)):
                (out / f'worker_{i}').symlink_to((prior / f'worker_{i}').resolve(), target_is_directory=True)
                (out / f'worker_{i}_field_map.json').symlink_to((merge / f'worker_{i}_field_map.json').resolve())
                artifacts += [out / f'worker_{i}/assessment.json', out / f'worker_{i}_field_map.json']
            operators = json.loads((merge / 'operators_manifest.json').read_text())
            # Eliminate intermediate directory symlinks from the emitted paths.
            operators['fields'] = str((merge / 'fields.json').resolve())
            for shard in operators['shards']:
                for key in ('operators', 'field_map'):
                    shard[key] = str(Path(shard[key]).resolve())
                    if shard[key] not in actual:
                        raise ValueError('operator manifest references an unverified artifact')
            counts = operators['counts']
            if (counts != proof['counts'] or counts['kernels'] != spans[-1]['kernel_end']-1
                    or counts['events'] != spans[-1]['event_end']
                    or counts['owned_pair_kernels'] != spans[-1]['expected_owner_total']):
                raise ValueError('full merged native coverage mismatch')
            save(out / 'operators_manifest.json', operators)
            artifacts.append(out / 'operators_manifest.json')
            artifact_pins = pins(artifacts, deadline)
            if initial != snapshot(all_paths):
                raise ValueError('retained inputs changed during final assessment')
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('original whole-check budget exhausted during assessment')
            save(out / 'assessment.json', dict(input_sha256=actual, artifacts=artifact_pins,
                 workers=len(spans), reused_completed_shards=len(spans), recompiled_shards=0,
                 all_native_inputs_and_shard_artifacts_rehashed=True,
                 worker_artifacts_pinned_by_shard_assessments=True, all_ranges_compiled=True,
                 local_operator_integrals_match_native_physical_totals=True, counts=counts,
                 compiled_merge_assessment=str(merge / 'assessment.json'),
                 original_whole_check_deadline_preserved=True, physical_domain_complete=False,
                 full_C_energy_matrix_assembled=False, global_passivity_qualified=False,
                 runtime_model_eligible=False, release_qualified=False,
                 elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started))
            status('compiled_pending_R_domain_attachment', counts=counts)
    except BaseException as error:
        status('failed', reason=repr(error)); raise
    finally:
        signal.alarm(0)
        for s, handler in old.items():
            signal.signal(s, handler)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('prior', 'merge', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    run(a.prior, a.merge, a.output)
