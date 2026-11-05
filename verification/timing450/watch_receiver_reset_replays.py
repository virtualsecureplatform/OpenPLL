#!/usr/bin/env python3
"""Replay terminal native reset-PVT waveforms without restarting analog jobs."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from characterize_bbpd import sha, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    campaign = args.campaign.resolve()
    manifest = campaign / 'input_manifest.json'
    inputs = json.loads(manifest.read_text())
    helper = Path(__file__).with_name('replay_receiver_reset_pvt.py').resolve()
    pins = {str(p.resolve()): sha(p) for p in (manifest, helper, Path(__file__),
            Path(__file__).with_name('characterize_bbpd.py'))}
    requested = inputs['requested_points']
    folders = sorted(p.parent for p in campaign.glob('*/loaded.cir'))
    assert len(folders) == requested == 180
    args.output.mkdir(parents=True, exist_ok=False)
    records = {}
    while len(records) < requested:
        verify(pins)
        for folder in folders:
            receipt = folder / 'assessment.json'
            if folder.name in records or not receipt.exists():
                continue
            try:
                native = json.loads(receipt.read_text())
            except json.JSONDecodeError:
                continue  # Native runner may still be writing its terminal receipt.
            verify(native['sha256'])
            record = {'native_assessment': str(receipt), 'native_assessment_sha256': sha(receipt),
                      'native_completed': native['simulation_completed'], 'replay_pass': False}
            if native['simulation_completed'] and native['exit_code'] == 0:
                out = args.output / folder.name
                with (args.output / (folder.name + '.log')).open('w') as log:
                    result = subprocess.run([sys.executable, str(helper), '--directory', str(folder),
                                             '--output', str(out)], stdout=log, stderr=subprocess.STDOUT)
                record['exit_code'] = result.returncode
                if (out / 'assessment.json').exists():
                    report = json.loads((out / 'assessment.json').read_text())
                    record.update(replay_pass=report['pass'], replay_assessment=str(out / 'assessment.json'),
                                  replay_assessment_sha256=sha(out / 'assessment.json'))
            records[folder.name] = record
            verify(pins)
            report = {'requested_points': requested, 'terminal_points': len(records),
                      'replay_passed_points': sum(r['replay_pass'] for r in records.values()),
                      'all_terminal_replays_pass': all(r['replay_pass'] for r in records.values()),
                      'complete': len(records) == requested, 'input_pins': pins, 'records': records,
                      'release_qualified': False, 'selected': False,
                      'limitations': ['Functional measured-storage replay at half-supply threshold, no SDF/MTBF/fullPLL proof',
                                      'Only450MHz and one reset alignment, nominal cellRC and fixed routeRC',
                                      'Post-window signed event consumption; no comprehensive stale same-direction qualification']}
            temporary = args.output / 'assessment.tmp'
            temporary.write_text(json.dumps(report, indent=2) + '\n')
            temporary.replace(args.output / 'assessment.json')
            print(json.dumps({'terminal_points': len(records), 'last_point': folder.name,
                              'replay_pass': record['replay_pass']}), flush=True)
        if len(records) < requested:
            final = campaign / 'assessment.json'
            if final.exists() and json.loads(final.read_text())['completed_points'] != requested:
                raise RuntimeError('Analog campaign terminated incomplete; keep failed evidence')
            time.sleep(10)
    verify(pins)


if __name__ == '__main__':
    main()
