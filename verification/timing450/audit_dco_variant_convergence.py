#!/usr/bin/env python3
"""Compare audited DCO variants; retain missing coverage and failed comparisons."""
import argparse
import json
import math
import statistics
from pathlib import Path
from audit_dco_completed_waveforms import crossings, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'step', 'tolerance', 'settling', 'engineering', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--single-settling', type=Path)
    parser.add_argument('--target-mhz', type=float, required=True)
    args = parser.parse_args()
    assert not args.output.exists() and args.target_mhz > 0
    pins = {}

    def pin(path, expected=None):
        path = str(Path(path).resolve())
        digest = sha(path)
        assert expected is None or digest == expected, path
        assert path not in pins or pins[path] == digest, path
        pins[path] = digest
        return path

    reports = {}
    for label in ('baseline', 'step', 'tolerance', 'settling', 'single_settling'):
        path = getattr(args, label)
        if path is None:
            continue
        report = json.loads(path.read_text())
        assert report['pass'] and report['audited_terminal_points'] == len(report['records'])
        pin(path)
        # Verify every source and completed artifact, merging duplicate pins once.
        for source, digest in report['sha256'].items():
            if source in pins:
                assert pins[source] == digest, source
            else:
                pin(source, digest)
        reports[label] = report
    spec = json.loads(args.engineering.read_text())
    pin(args.engineering)
    pin(Path(__file__))
    pin(Path(__file__).with_name('audit_dco_completed_waveforms.py'))
    expected = set()
    reference_parameters = None
    measured = {}
    window_ns = 50
    invariant_keys = ('coarse_codes', 'corner', 'vdd', 'temperature_c', 'pdk', 'pdk_root', 'subckt_name',
                      'reset_release_ns', 'tran_uic', 'supply_ramp_ns',
                      'supply_ramp_delay_ns', 'therm_invert', 'simulator', 'xyce')
    for label, report in reports.items():
        measured[label] = {}
        for name in report['records']:
            waves = [Path(p) for p in report['sha256'] if Path(p).name == name + '.prn']
            assert len(waves) == 1
            wave = waves[0]
            saved = json.loads(wave.with_name(name + '.provenance.json').read_text())
            parameters = saved['parameters']
            assert saved['completed']
            if reference_parameters is None:
                assert label == 'baseline'
                reference_parameters = parameters
                expected = set(map(int, parameters['codes'].split(',')))
                assert len(expected) == 35
            assert all(parameters[k] == reference_parameters[k] for k in invariant_keys)
            assert sha(parameters['rcx_netlist']) == sha(reference_parameters['rcx_netlist'])
            assert parameters['simulator'] == 'xyce'
            # The isolated probe has one code; full variants must retain the35-code recipe.
            if label != 'single_settling':
                assert set(map(int, parameters['codes'].split(','))) == expected
            baseline = label == 'baseline'
            tight = label in ('tolerance', 'settling', 'single_settling')
            assert math.isclose(parameters['xyce_reltol'], 1e-6 if tight else 1e-5,
                                rel_tol=1e-14, abs_tol=0)
            assert math.isclose(parameters['xyce_abstol'], 1e-10 if tight else 1e-9,
                                rel_tol=1e-14, abs_tol=0)
            assert parameters['step_ps'] == parameters['max_step_ps'] == (10 if baseline or label == 'tolerance' else 5)
            stop = 600 if label in ('settling', 'single_settling') else 300
            assert parameters['sim_time_ns'] == stop
            assert parameters['meas_start_ns'] == (200 if stop == 600 else 100)
            code = int(name.rsplit('_', 1)[1])
            assert code in expected
            rows = [tuple(map(float, fields[1:])) for line in wave.read_text().splitlines()
                    if (fields := line.split()) and fields[0].isdigit()]
            rises = crossings(rows, parameters['vdd'] / 2, True, (stop - 2 * window_ns) * 1e-9)
            windows = []
            for start in (stop - 2 * window_ns, stop - window_ns):
                selected = [t for t in rises if start * 1e-9 <= t < (start + window_ns) * 1e-9]
                assert len(selected) >= 3
                periods = [b - a for a, b in zip(selected, selected[1:])]
                assert all(period > 0 for period in periods)
                windows.append({'start_ns': start, 'end_ns': start + window_ns,
                                'complete_cycles': len(periods),
                                'mean_frequency_hz': 1 / statistics.mean(periods)})
            measured[label][code] = {'windows': windows,
                                    'final_frequency_hz': windows[-1]['mean_frequency_hz'],
                                    'adjacent_window_difference_hz': abs(windows[-1]['mean_frequency_hz'] - windows[0]['mean_frequency_hz'])}
    records = {}
    for code, baseline in measured['baseline'].items():
        neighbors = [abs(baseline['final_frequency_hz'] - measured['baseline'][n]['final_frequency_hz'])
                     for n in (code - 1, code + 1) if n in measured['baseline']]
        assert neighbors and min(neighbors) > 0
        limit = min(args.target_mhz * spec['calibration_error_ppm'],
                    min(neighbors) * spec['calibration_error_local_lsb'])
        variants = {}
        for label in measured:
            if label == 'baseline' or code not in measured[label]:
                continue
            item = measured[label][code]
            delta = abs(item['final_frequency_hz'] - baseline['final_frequency_hz'])
            variants[label] = dict(item, baseline_difference_hz=delta,
                                   baseline_difference_within_limit=delta <= limit,
                                   adjacent_windows_within_limit=item['adjacent_window_difference_hz'] <= limit)
        complete = all(label in variants for label in ('step', 'tolerance', 'settling'))
        baseline_stable = baseline['adjacent_window_difference_hz'] <= limit
        passed = complete and baseline_stable and all(
            variants[label]['baseline_difference_within_limit'] and variants[label]['adjacent_windows_within_limit']
            for label in ('step', 'tolerance', 'settling'))
        records[str(code)] = {'baseline': baseline, 'calibration_limit_hz': limit,
                              'baseline_adjacent_windows_within_limit': baseline_stable,
                              'variants': variants, 'required_variants_complete': complete,
                              'observed_variant_failure': not baseline_stable or any(
                                  not r['baseline_difference_within_limit'] or not r['adjacent_windows_within_limit']
                                  for r in variants.values()),
                              'code_convergence_screen_pass': passed}
    complete_codes = [int(k) for k, r in records.items() if r['required_variants_complete']]
    passed_codes = [int(k) for k, r in records.items() if r['code_convergence_screen_pass']]
    report = {'analysis_complete': True, 'target_mhz': args.target_mhz,
              'window_ns': window_ns, 'expected_codes': sorted(expected),
              'audited_points_by_variant': {k: len(v) for k, v in measured.items()},
              'codes_with_all_required_variants': complete_codes,
              'passing_complete_codes': passed_codes,
              'observed_failing_codes': [int(k) for k, r in records.items() if r['observed_variant_failure']],
              'missing_codes_by_variant': {k: sorted(expected - set(measured[k])) for k in ('baseline', 'step', 'tolerance', 'settling')},
              'all35_codes_convergence_screen_pass': set(passed_codes) == expected,
              'records': records, 'sha256': pins,
              'release_qualified': False, 'selected': False,
              'scope': 'Final50ns mean-frequency and adjacent-window convergence screen for available completed coarse0 SS1.62V/125C canonical extracted-DCO variants. Missing codes and all failures retained. Baseline-derived local spacing; full interpolation, fullPVT, noise/jitter and wholePLL/acquisition qualification remain outstanding.'}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('records', 'sha256')}))


if __name__ == '__main__':
    main()
