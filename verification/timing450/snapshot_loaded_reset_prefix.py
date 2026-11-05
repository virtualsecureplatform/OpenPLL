#!/usr/bin/env python3
"""Freeze a bounded native trace prefix for diagnosis, never qualification."""
import argparse
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stop-ns', type=float, required=True)
    args = parser.parse_args()
    assert math.isfinite(args.stop_ns) and args.stop_ns > 0
    directory = args.directory.resolve()
    output = args.output.resolve()
    assert not output.exists()
    deck, manifest = directory/'loaded.cir', directory/'input_manifest.json'
    pins = {str(p): sha(p) for p in (deck, manifest, Path(__file__).resolve())}
    supply = float(re.search(r'^\.param VDD=([0-9.]+)$', deck.read_text(), re.M)[1])
    assert supply in (1.62, 1.8, 1.95)
    source = directory/'loaded.prn'
    names = ('READY2', 'EVENT_RESET', 'BBPD_RESET_PHY', 'UP2', 'DN2')
    rises = {name: [] for name in names}
    falls = {name: [] for name in names}
    previous = None
    count = 0
    passed_boundary = False
    output.mkdir()
    prefix = output/'wave.prefix.txt'
    with source.open() as stream, prefix.open('w') as frozen:
        header = stream.readline()
        columns = header.split()
        assert len(columns) == 23 and columns[:2] == ['Index', 'TIME']
        indices = {name: columns.index('V('+name+')') for name in names}
        frozen.write(header)
        for line in stream:
            fields = line.split()
            assert fields and fields[0].isdigit(), 'Missing numeric boundary in native prefix'
            row = list(map(float, fields))
            assert len(row) == 23 and all(map(math.isfinite, row))
            assert row[0] == count
            if row[1] * 1e9 > args.stop_ns:
                passed_boundary = True
                break
            if previous is None:
                assert row[1] == 0
            else:
                assert row[1] > previous[1]
                for name, index in indices.items():
                    a, b = previous[index], row[index]
                    if a < supply/2 <= b or a >= supply/2 > b:
                        time = previous[1] + (supply/2-a)*(row[1]-previous[1])/(b-a)
                        (rises if b > a else falls)[name].append(time*1e9)
            frozen.write(line)
            previous = row
            count += 1
    assert passed_boundary and previous is not None
    for path, digest in pins.items():
        assert sha(Path(path)) == digest, path
    pins[str(prefix)] = sha(prefix)
    record = {'observed_utc': datetime.now(timezone.utc).isoformat(),
              'native_directory': str(directory), 'source_waveform': str(source),
              'requested_prefix_stop_ns': args.stop_ns, 'last_snapshot_time_ns': previous[1]*1e9,
              'numeric_rows': count, 'prefix_integrity_checked': True,
              'source_prefix_byte_identity': True, 'supply_v': supply,
              'rising_crossings_ns': rises, 'falling_crossings_ns': falls,
              'last_values_v': {name: previous[index] for name, index in indices.items()},
              'sha256': pins, 'simulation_completed': False,
              'release_qualified': False, 'selected': False,
              'scope': 'Bounded recorded prefix only; growing source waveform is not pinned. '
                       'No native completion, loaded-withdrawal, consumption, MTBF or wholePLL qualification.'}
    (output/'assessment.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({k: v for k, v in record.items() if k != 'sha256'}))


if __name__ == '__main__':
    main()
