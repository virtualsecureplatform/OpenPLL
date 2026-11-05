#!/usr/bin/env python3
"""Prove native energy operators unchanged and isolate the missing self terms.

Compare every original operator's geometry, coefficient, native event serial
and logical plane/material keys exactly. Only then may a matrix assembly reuse
the original numerical sum and add the missing self-pair energy.
"""
import argparse
import json
from pathlib import Path
import time

from compile_local_C_operators_v2 import digest, save


def separate(old, new, out, deadline):
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    old_proof = json.loads((old/'assessment.json').read_text())
    new_proof = json.loads((new/'assessment.json').read_text())
    assert new_proof['finite_R_same_conductor_pair_energy_restored']
    assert old_proof['counts']['events'] == new_proof['counts']['events']
    old_fields, new_fields = [json.loads((p/'fields.json').read_text()) for p in [old, new]]
    out.mkdir(parents=True, exist_ok=False)
    native = restored = 0
    with (old/'operators.jsonl').open() as before, (new/'operators.jsonl').open() as after, (out/'self_operators.jsonl').open('x') as self_stream:
        for text in after:
            row = json.loads(text)
            if row[3] < 0:
                assert row[1] != 0 and row[2] != 0
                assert new_fields[row[1]][0] == new_fields[row[2]][0]
                self_stream.write(text)
                restored += 1
            else:
                reference = json.loads(next(before))
                assert reference[0] == row[0] and reference[3:] == row[3:], (native, reference, row)
                assert old_fields[reference[1]] == new_fields[row[1]]
                assert old_fields[reference[2]] == new_fields[row[2]]
                native += 1
            if (native+restored) % 100000 == 0:
                assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
                save(out/'status.json', dict(state='checking_native_operator_identity', original_operators=native, self_operators=restored))
        assert next(before, None) is None
    assert native == old_proof['counts']['operators']
    assert restored == new_proof['counts'].get('restored_self_operators', 0)
    assert native+restored == new_proof['counts']['operators']
    inputs = [Path(__file__).resolve(), old/'assessment.json', new/'assessment.json', old/'fields.json', new/'fields.json',
        old/'operators.jsonl', new/'operators.jsonl']
    result = dict(all_original_energy_operators_identical_under_exact_field_key_renaming=True,
        original_operators=native, isolated_missing_self_operators=restored,
        all_increment_endpoints_on_same_original_conductor=True,
        incremental_numerical_matrix_reuse_permitted=True,
        corrected_matrix_passivity_or_runtime_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256={str(p.resolve()): digest(p) for p in inputs},
        artifacts={str((out/'self_operators.jsonl').resolve()): digest(out/'self_operators.jsonl')})
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(out/'assessment.json', result)
    save(out/'status.json', dict(state='completed', original_operators=native, self_operators=restored))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--old', type=Path, required=True)
    parser.add_argument('--new', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--owner', type=Path, required=True)
    args = parser.parse_args()
    deadline = json.loads(args.owner.read_text())['deadline_uptime']
    print(json.dumps(separate(args.old, args.new, args.output, deadline), indent=2))


if __name__ == '__main__':
    main()
