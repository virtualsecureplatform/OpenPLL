#!/usr/bin/env python3
"""Audit terminal sequential provenance and freeze the mutable status snapshot.

Preserves the original measurement receipt and all raw files. Only its known
mutable-status artifact is replaced by a separately frozen final snapshot.
This does not independently remeasure events or qualify timing/MTBF models.
"""
import argparse
import json
from pathlib import Path

from check_compact_clock_tree import verify
from run_dco_qualification import sha, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root, out = args.run.resolve(), args.output.resolve()
    source = root/'assessment.json'
    result = json.loads(source.read_text())
    status_path = root/'status.json'
    status_bytes = status_path.read_bytes()
    status = json.loads(status_bytes)
    assert status['state'] == 'terminal_assessment'
    assert result['all_native_waveform_events_terminal']
    assert result['fixtures'] == len(result['records']) == status['fixtures']
    assert result['passing'] == sum(bool(r['passed']) for r in result['records']) == status['passing']
    claim = root.parent/'native_run.json'
    runner = json.loads(claim.read_text())
    launch = json.loads((root/'launch.json').read_text())
    assert Path(runner['output']) == root
    # Do not freeze a snapshot while its original producer can still update it.
    for pid in (runner['runner_pid'], launch['pid']):
        proc = Path('/proc')/str(pid)
        if proc.exists():
            command = (proc/'cmdline').read_bytes().replace(b'\0', b' ')
            assert str(root).encode() not in command and str(root.parent/'batch.cir').encode() not in command, 'producer still live'
    for path, digest in result['input_sha256'].items():
        assert sha(Path(path)) == digest, path
    artifacts = {}
    mismatches = []
    for path, digest in result['artifacts'].items():
        actual = sha(Path(path))
        if Path(path).resolve() == status_path:
            assert actual != digest, 'requires the observed mutable-status mismatch'
            mismatches.append(path)
        else:
            assert actual == digest, path
            artifacts[path] = digest
    assert mismatches == [str(status_path)]
    out.mkdir(parents=True, exist_ok=False)
    snapshot = out/'terminal_status_snapshot.json'
    snapshot.write_bytes(status_bytes)
    artifacts[str(snapshot)] = sha(snapshot)
    pins = dict(result['input_sha256'])
    for path in (source, claim, Path(__file__).resolve(), Path(__file__).with_name('check_compact_clock_tree.py')):
        pins[str(path.resolve())] = sha(path)
    assert status_path.read_bytes() == status_bytes
    updated = dict(result, input_sha256=pins, artifacts=artifacts,
        measurement_scope=result['scope'], scope=__doc__, source_assessment=str(source),
        original_receipt_preserved=True, raw_artifact_hashes_verified=True,
        mutable_status_artifact_replaced_with_frozen_snapshot=True,
        original_mutable_artifact_hash_mismatches=mismatches,
        physical_timing_qualified=False, release_qualified=False)
    save(out/'assessment.json', updated)
    verify(out/'assessment.json')
    print(f'Audited sequential provenance: {result["passing"]}/{result["fixtures"]}; raw data unchanged', flush=True)


if __name__ == '__main__':
    main()
