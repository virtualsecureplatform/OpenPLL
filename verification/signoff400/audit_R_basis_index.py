"""Independently verify every field slot and R-bundle offset/key in an index."""
import argparse
import hashlib
import json
import mmap
from pathlib import Path
import struct
import time
from common import save, sha


def run(index, output):
    index, out = index.resolve(), output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    receipt = index/'assessment.json'
    report = json.loads(receipt.read_text())
    root = Path(report['source_mapping'])
    bundles, fields = (root/'native'/name for name in ('R_tile_bundles.jsonl', 'field_domains.jsonl'))
    hashes = [hashlib.sha256(), hashlib.sha256()]
    offsets, offset = [], 0
    deadline = time.monotonic()+43200
    with bundles.open('rb') as stream:
        for raw in stream:
            if time.monotonic() > deadline:
                raise TimeoutError('R index audit deadline')
            row = json.loads(raw)
            if row['bundle_id'] != len(offsets):
                raise ValueError('noncontiguous R bundle IDs')
            offsets.append((offset, len(raw)-1, row['field_key']))
            hashes[0].update(raw)
            offset += len(raw)
    path = index/'fields.idx'
    if sha(path) != report['artifacts'][str(path)]:
        raise ValueError('R field index changed')
    selected, count = 0, 0
    used = set()
    with path.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as table, fields.open('rb') as source:
        total = struct.unpack_from('<Q', table, 8)[0]
        if table[:8] != b'RBSIDX01' or len(table) != 16+16*total:
            raise ValueError('R index header/size')
        for count, raw in enumerate(source, 1):
            if count % 1000 == 0 and time.monotonic() > deadline:
                raise TimeoutError('R index audit deadline')
            row = json.loads(raw)
            if row['field_id'] != count-1 or count > total:
                raise ValueError('contiguous field index IDs')
            entry = struct.unpack_from('<QII', table, 16+16*(count-1))
            if row['support_state'] == 'exact_native_R_tile_candidates':
                bundle = row['R_tile_bundle_id']
                if bundle in used or not 0 <= bundle < len(offsets):
                    raise ValueError('R bundle reuse/range')
                offset, length, key = offsets[bundle]
                if entry != (offset, length, bundle) or key != row['field_key']:
                    raise ValueError('field/R bundle index identity or offset mismatch')
                used.add(bundle)
                selected += 1
            elif entry != (2**64-1, 0, 0):
                raise ValueError('non-R field has indexed R geometry')
            hashes[1].update(raw)
    if count != total or selected != len(offsets) or selected != report['R_fields']:
        raise ValueError('R index coverage count')
    for p, digest in zip((bundles, fields), hashes):
        if digest.hexdigest() != report['input_sha256'][str(p)]:
            raise ValueError('R index source changed')
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in
         (receipt, path, bundles, fields, Path(__file__).resolve())},
         global_fields=count, R_fields=selected, all_field_slots_independently_checked=True,
         all_bundle_offsets_lengths_and_keys_match=True, physical_RC_qualified=False, release_qualified=False))
    print(json.dumps(dict(global_fields=count, R_fields=selected)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('index', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    run(args.index, args.output)
