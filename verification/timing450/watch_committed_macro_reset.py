#!/usr/bin/env python3
"""Audit the existing committed-bundle pilot when terminal; never launch or restart analog."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from characterize_bbpd import sha, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    directory = args.directory.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    here = Path(__file__).resolve().parent
    helpers = [here / name for name in ('audit_committed_macro_reset_native.py',
               'replay_committed_macro_reset.py', 'audit_committed_macro_reset_replay.py', 'audit_receiver_reset_replay.py',
               'characterize_bbpd.py', Path(__file__).name)]
    manifest = directory / 'input_manifest.json'
    pins = {str(p): sha(p) for p in [manifest, *helpers]}
    receipt = directory / 'assessment.json'
    while not receipt.exists():
        verify(pins)
        time.sleep(10)
    native = json.loads(receipt.read_text())
    verify(pins)
    pins[str(receipt)] = sha(receipt)
    report = {'native_completed': native['simulation_completed'], 'commands': [],
              'source_pins': pins, 'release_qualified': False, 'selected': False}
    if native['simulation_completed'] and native['exit_code'] == 0:
        commands = [
            [sys.executable, str(helpers[0]), '--directory', str(directory),
             '--output', str(output / 'native_audit.json')],
            [sys.executable, str(helpers[1]), '--directory', str(directory),
             '--output', str(output / 'rtl_replay')],
            [sys.executable, str(helpers[2]), '--native-directory', str(directory),
             '--replay-directory', str(output / 'rtl_replay'),
             '--output', str(output / 'consumption_audit.json')],
            [sys.executable, str(helpers[1]), '--directory', str(directory),
             '--output', str(output / 'direction_control'), '--swap-direction-control']]
        for index, command in enumerate(commands):
            verify(pins)
            log = output / f'command_{index}.log'
            with log.open('w') as stream:
                result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
            report['commands'].append({'argv': command, 'exit_code': result.returncode,
                                       'log': str(log), 'log_sha256': sha(log)})
            if result.returncode != 0:
                break
    verify(pins)
    report['terminal_checks_pass'] = (len(report['commands']) == 4 and
                                     all(c['exit_code'] == 0 for c in report['commands']))
    report['independent_consumption_audit_pass'] = False
    report['direction_control_rejected'] = False
    audit = output / 'consumption_audit.json'
    control = output / 'direction_control' / 'assessment.json'
    if audit.exists():
        assessed = json.loads(audit.read_text()); verify(assessed['sha256'])
        report['independent_consumption_audit_pass'] = assessed['pass']
        report['consumption_audit_sha256'] = sha(audit)
    if control.exists():
        assessed = json.loads(control.read_text()); verify(assessed['sha256']); verify(assessed['artifacts'])
        report['direction_control_rejected'] = (assessed['negative_control'] and
                                               assessed['negative_control_rejected'] and not assessed['pass'])
        report['direction_control_sha256'] = sha(control)
    report['terminal_checks_pass'] = (report['terminal_checks_pass'] and
                                      report['independent_consumption_audit_pass'] and
                                      report['direction_control_rejected'])
    # These checks still do not supply full PVT, mode, acquisition or PLL signoff.
    (output / 'assessment.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
