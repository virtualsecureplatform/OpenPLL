#!/usr/bin/env python3
"""Compare complete field identities/maps with the retained independent merge.

The failed Python merge completed all maps before final-ledger serialization.
This comparison covers field mapping only, not the global numerical ledger.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from common import ROOT, save, sha
from compile_charge import pins
from compiled_charge_v2 import execute
from resources import identity, lease


def compare_map(reference, compiled, global_fields):
    if not isinstance(reference, list) or not isinstance(compiled, list) or reference != compiled:
        raise ValueError('local-to-global field map differs')
    if not reference or reference[0] != 0:
        raise ValueError('reference field zero is missing')
    if any(type(v) is not int or v < 0 or v >= global_fields for v in reference + compiled):
        raise ValueError('invalid global field ID')
    return len(reference)


def run(reference, compiled, output):
    reference, compiled, out = (Path(p).resolve() for p in (reference, compiled, output))
    out.mkdir(parents=True, exist_ok=False)
    start = time.clock_gettime(time.CLOCK_BOOTTIME); deadline = start + 43200
    save(out / 'owner.json', dict(started_utc=datetime.now(timezone.utc).isoformat(),
         wall_limit_s=43200, automatic_identical_retry=False))

    def status(state, **kw):
        save(out / 'status.json', dict(state=state, elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start,
             release_qualified=False, **kw))

    def snapshot(paths):
        return {str(p): (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
                for p in paths for s in (p.stat(),)}

    try:
        with lease(4, 4, deadline):
            owner = json.loads((reference / 'owner.json').read_text())
            if identity(owner['pid']) == owner['birth'] or json.loads((reference / 'status.json').read_text())['state'] != 'failed':
                raise ValueError('reference merge is not terminal')
            if 'MemoryError' not in (reference / 'merge.log').read_text():
                raise ValueError('reference did not stop at final ledger serialization')
            proof = json.loads((compiled / 'assessment.json').read_text())
            producer = ROOT / 'verification/prototype400/compile_capacitance_parallel.py'
            producer_pins = json.loads((reference / 'input_manifest.json').read_text())['input_sha256']
            if producer_pins.get(str(producer)) != sha(producer):
                raise ValueError('reference producer identity mismatch')
            binary = compiled / 'charge_merge'
            paths = [reference / 'owner.json', reference / 'status.json', reference / 'merge.log',
                     reference / 'input_manifest.json', compiled / 'assessment.json', producer,
                     reference / 'fields.json', compiled / 'fields.json', binary, Path(__file__).resolve()]
            paths += [Path(__file__).with_name(n) for n in
                      ('common.py', 'compile_charge.py', 'compiled_charge.py', 'compiled_charge_v2.py', 'parallel_hash.py', 'resources.py')]
            for i in range(proof['ordered_shards']):
                paths += [folder / f'worker_{i}_field_map.json' for folder in (reference, compiled)]
            initial = snapshot(paths)
            input_pins = pins(paths, deadline, lambda **kw: status('hashing_reference_and_compiled_maps', **kw))
            for path in paths:
                if path.parent == compiled and path.name not in ('assessment.json',):
                    if proof['artifacts'].get(str(path)) != input_pins[str(path)]:
                        raise ValueError('compiled map artifact identity mismatch')
            save(out / 'input_manifest.json', dict(input_sha256=input_pins))
            status('comparing_all_global_field_identities')
            execute([binary, 'compare', reference / 'fields.json', compiled / 'fields.json', deadline],
                    out / 'fields_compare.log', deadline, 4)
            field_result = json.loads((out / 'fields_compare.log').read_text())
            if field_result['identical_rows'] != proof['global_fields']:
                raise ValueError('global field count mismatch')
            local_fields = 0
            for i in range(proof['ordered_shards']):
                status('comparing_all_local_to_global_maps', shard=i)
                name = f'worker_{i}_field_map.json'
                local_fields += compare_map(json.loads((reference / name).read_text()),
                                            json.loads((compiled / name).read_text()), proof['global_fields'])
                if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                    raise TimeoutError('whole-check deadline exhausted')
            if initial != snapshot(paths):
                raise ValueError('field-map input changed during comparison')
            save(out / 'assessment.json', dict(input_sha256=input_pins,
                 artifacts={str(out / 'fields_compare.log'): sha(out / 'fields_compare.log')},
                 global_fields=proof['global_fields'], local_fields=local_fields,
                 ordered_shards=proof['ordered_shards'], all_global_field_identities_match_reference=True,
                 all_local_to_global_maps_match_reference=True, global_numerical_ledger_compared=False,
                 physical_domain_complete=False, runtime_model_eligible=False, release_qualified=False,
                 elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start))
            status('all_field_identities_and_maps_match_independent_reference', local_fields=local_fields)
    except BaseException as error:
        status('failed', reason=repr(error)); raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'compiled', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args(); run(a.reference, a.compiled, a.output)
