#!/usr/bin/env python3
"""Replay pinned STA recipes at both measured sampled-detector pulse extremes."""
import argparse
import concurrent.futures
import json
import math
from pathlib import Path
import re
import subprocess
from characterize_bbpd import sha, verify
from verify_extended_models import summarize, verify_bbpd_slews

OPENROAD = '/nix/store/qqz49dx8dpx4q9i5wriif091n7iaa0ld-openroad-2026-02-17/bin/openroad'


def pulse_constraints(text, width):
    text, count = re.subn(r'(create_clock -name EVENT_\$name -period 40 -waveform )\{0 [\d.]+\}( \$port)',
                         lambda m: m[1] + '{0 ' + str(width) + '}' + m[2], text)
    if count != 1 or not 0 < width < 40:
        raise RuntimeError('Unexpected event-clock recipe or invalid pulse width')
    return text


def verify_event_clocks(log, width):
    rows = {}
    for line in log.splitlines():
        fields = line.split()
        if fields and fields[0].startswith('EVENT_BBPD['):
            if len(fields) != 4:
                raise RuntimeError('Malformed source event clock report')
            rows[fields[0]] = list(map(float, fields[1:]))
    if set(rows) != {'EVENT_BBPD[0]', 'EVENT_BBPD[1]'}:
        raise RuntimeError('Incomplete source event clock properties')
    for values in rows.values():
        if not all(math.isfinite(v) for v in values) or abs(values[0] - 40) > 1e-6 or abs(values[1]) > 1e-6 or abs(values[2] - width) > .0051:
            raise RuntimeError('Measured event pulse bound was not applied')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prior-directory', type=Path, required=True)
    parser.add_argument('--bounds', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    if args.output.exists() or args.jobs < 1:
        raise RuntimeError('Require fresh output and positive worker count')
    source = json.loads(args.bounds.read_text())
    verify(source['sha256'])
    bounds = source['bounds']
    # Two 40 ns waveforms cover independent minimum high and low times.
    profiles = {'minimum_high': bounds['minimum_high_ns'],
                'minimum_low': 40 - bounds['minimum_low_ns']}
    pins = {str(args.bounds): sha(args.bounds), str(Path(__file__).resolve()): sha(Path(__file__).resolve()),
            OPENROAD: sha(Path(OPENROAD)), **source['sha256']}
    for name in ('verify_extended_models.py', 'closure_audit.py', 'run.py', 'characterize_bbpd.py'):
        path = Path(__file__).with_name(name).resolve()
        pins[str(path)] = sha(path)
    jobs = []
    output = args.output.resolve()
    output.mkdir(parents=True)
    for suite in ('original', 'hot'):
        for mode in (100, 250, 300, 400, 450):
            prior = args.prior_directory.resolve() / f'verified_{suite}_{mode}'
            assessment = prior / 'assessment.json'
            evidence = json.loads(assessment.read_text())
            verify(evidence['sha256'])
            if not evidence['diagnostic_timing_pass']:
                raise RuntimeError('Prior timing assessment did not pass')
            pins.update(evidence['sha256'])
            pins[str(assessment)] = sha(assessment)
            original = prior / 'bbpd_constraints.tcl'
            for profile, width in profiles.items():
                directory = output / f'{suite}_{mode}_{profile}'
                directory.mkdir()
                constraints = directory / 'constraints.tcl'
                constraints.write_text(pulse_constraints(original.read_text(), width))
                pins[str(constraints)] = sha(constraints)
                for model in ('ss', 'tt', 'ff'):
                    for rc in ('min', 'nom', 'max'):
                        original_recipe = prior / f'{model}_{rc}_timing.tcl'
                        text = original_recipe.read_text()
                        expected = 'source ' + str(original) + '\n'
                        if text.count(expected) != 1 or text.count('puts "SETUP_AND_RECOVERY_SCREEN"') != 1:
                            raise RuntimeError('Unexpected pinned timing recipe structure')
                        text = text.replace(expected, 'source ' + str(constraints) + '\n')
                        text = text.replace('puts "SETUP_AND_RECOVERY_SCREEN"',
                                            'puts "SAMPLED_EVENT_CLOCK_PROPERTIES"\nreport_clock_properties [get_clocks EVENT_*]\nputs "SETUP_AND_RECOVERY_SCREEN"')
                        recipe = directory / f'{model}_{rc}_timing.tcl'
                        recipe.write_text(text)
                        pins[str(recipe)] = sha(recipe)
                        jobs.append((recipe, width, suite, mode, profile, model, rc))
    verify(pins)
    manifest = output / 'input_manifest.json'
    manifest.write_text(json.dumps({'sha256': pins, 'requested_screens': len(jobs), 'profiles_ns': profiles}, indent=2) + '\n')

    def run(job):
        recipe, width, suite, mode, profile, model, rc = job
        log = recipe.with_suffix('.log')
        with log.open('w') as stream:
            native = subprocess.run([OPENROAD, '-exit', '-threads', '2', str(recipe)], stdout=stream, stderr=subprocess.STDOUT)
        result = {'suite': suite, 'mode_mhz': mode, 'profile': profile, 'model': model, 'rc': rc,
                  'high_ns': width, 'low_ns': 40 - width, 'exit_code': native.returncode,
                  'diagnostic_timing_pass': False, 'release_qualified': False, 'selected': False}
        if native.returncode == 0:
            try:
                text = log.read_text()
                rows, passed = summarize(text)
                verify_bbpd_slews(text, bounds)
                verify_event_clocks(text, width)
                result.update(timing_ns=rows, diagnostic_timing_pass=passed,
                              electrical_violated_rows=text.count('(VIOLATED)'), source_clock_properties_verified=True)
            except (RuntimeError, ValueError) as error:
                result['error'] = str(error)
        result['sha256'] = {str(p): sha(p) for p in (recipe, log)}
        receipt = recipe.with_suffix('.assessment.json')
        receipt.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({k: v for k, v in result.items() if k not in ('sha256', 'timing_ns')}), flush=True)
        return receipt, result

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(run, jobs))
    verify(pins)
    result = {'requested_screens': len(jobs), 'terminal_screens': len(results),
              'all_native_exit_zero': all(r['exit_code'] == 0 for _, r in results),
              'diagnostic_timing_pass': all(r['diagnostic_timing_pass'] for _, r in results),
              'input_manifest_sha256': sha(manifest), 'receipts': {str(p): sha(p) for p, _ in results},
              'bounds': bounds, 'profiles_ns': profiles, 'release_qualified': False, 'selected': False,
              'limitations': ['Supplied cell models only; 44 exact required cell PVT points still missing',
                              'Two-opportunity +/-250ps/20-200ps source screen; arbitrary phase/duty and metastability remain open',
                              'Full nonlinear receiver and whole-PLL qualification remain separate']}
    (output / 'assessment.json').write_text(json.dumps(result, indent=2) + '\n')
    if not result['diagnostic_timing_pass']:
        raise RuntimeError('Sampled pulse timing campaign contains failed screens')


if __name__ == '__main__':
    main()
