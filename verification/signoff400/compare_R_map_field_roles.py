"""Check field-role stability across R diagnostics without mixing R node data."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
from common import save, sha


def run(old, new, output):
    old, new, out = (p.resolve() for p in (old, new, output))
    out.mkdir(parents=True, exist_ok=False)
    receipts = [p/'assessment.json' for p in (old, new)]
    reports = [json.loads(p.read_text()) for p in receipts]
    sources = [p/'native/field_domains.jsonl' for p in (old, new)]
    pins = {str(p): sha(p) for p in (*receipts, Path(__file__).resolve())}
    hashes = [hashlib.sha256(), hashlib.sha256()]
    counts = Counter()
    deadline = time.monotonic()+43200
    with sources[0].open('rb') as left, sources[1].open('rb') as right:
        for number, raw in enumerate(left):
            if number % 1000 == 0 and time.monotonic() > deadline:
                raise TimeoutError('field-role comparison deadline')
            other = right.readline()
            hashes[0].update(raw)
            hashes[1].update(other)
            a, b = json.loads(raw), json.loads(other)
            for key in ('field_id', 'field_key', 'support_state'):
                if a[key] != b[key]:
                    raise ValueError(f'field {number} changed {key}')
            if a['field_id'] != number:
                raise ValueError('noncontiguous field IDs')
            state = a['support_state']
            counts[state] += 1
            if state != 'exact_native_R_tile_candidates' and a != b:
                raise ValueError('non-R field payload changed')
            if a != b:
                counts['R_candidate_payloads_changed'] += 1
        if right.read(1):
            raise ValueError('extra corrected fields')
    for p, report, digest in zip(sources, reports, hashes):
        h = digest.hexdigest()
        if report['artifacts'][str(p)] != h:
            raise ValueError('map stream differs from producer receipt')
        pins[str(p)] = h
    for p in receipts:
        if sha(p) != pins[str(p)]:
            raise ValueError('map receipt changed')
    save(out/'assessment.json', dict(input_sha256=pins, counts=dict(counts),
        all_field_keys_and_support_roles_identical=True,
        all_non_R_field_payloads_identical=True,
        R_private_nodes_or_bundles_reused=False,
        physical_RC_qualified=False, release_qualified=False))
    print(json.dumps(dict(counts)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('old', 'new', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.old, args.new, args.output)
