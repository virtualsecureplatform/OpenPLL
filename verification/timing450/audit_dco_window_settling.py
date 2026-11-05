#!/usr/bin/env python3
"""Screen completed DCO baseline windows; independent convergence variants remain required."""
import argparse
import hashlib
import json
import re
import statistics
from pathlib import Path
from audit_dco_completed_waveforms import crossings, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wave-audit', type=Path, required=True)
    parser.add_argument('--engineering', type=Path, required=True)
    parser.add_argument('--target-mhz', type=float, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists() and args.target_mhz > 0
    audit = json.loads(args.wave_audit.read_text())
    spec = json.loads(args.engineering.read_text())
    assert audit['pass']
    frequencies = {int(name.rsplit('_', 1)[1]): row['whole_window_mean_frequency_hz']
                   for name, row in audit['records'].items()}
    pins = {str(p.resolve()): sha(p) for p in [args.wave_audit, args.engineering,
            Path(__file__), Path(__file__).with_name('audit_dco_completed_waveforms.py')]}
    results = {}
    for name, previous in audit['records'].items():
        paths = [Path(p) for p in audit['sha256'] if Path(p).name == name + '.prn']
        assert len(paths) == 1
        wave = paths[0]
        pins[str(wave)] = sha(wave)
        assert pins[str(wave)] == audit['sha256'][str(wave)]
        provenance = wave.with_name(name + '.provenance.json')
        pins[str(provenance)] = sha(provenance)
        assert pins[str(provenance)] == audit['sha256'][str(provenance)]
        supply = json.loads(provenance.read_text())['parameters']['vdd']
        rows = [tuple(map(float, fields[1:])) for line in wave.read_text().splitlines()
                if (fields := line.split()) and fields[0].isdigit()]
        code = int(name.rsplit('_', 1)[1])
        neighbors = [abs(frequencies[code] - frequencies[n]) for n in (code-1, code+1)
                     if n in frequencies]
        assert neighbors and min(neighbors) > 0
        limit_hz = min(args.target_mhz * spec['calibration_error_ppm'],
                       min(neighbors) * spec['calibration_error_local_lsb'])
        windows = []
        for start_ns in (100, 150, 200, 250):
            rises = [t for t in crossings(rows, supply/2, True, start_ns*1e-9)
                     if t < (start_ns+50)*1e-9]
            assert len(rises) >= 3
            periods = [b-a for a,b in zip(rises,rises[1:])]
            windows.append({'start_ns':start_ns, 'end_ns':start_ns+50,
                            'complete_cycles':len(periods),
                            'mean_frequency_hz':1/statistics.mean(periods)})
        initial = previous['first_two_cycle_frequency_hz']
        final = windows[-1]['mean_frequency_hz']
        difference = abs(final-initial)
        adjacent_window_difference = abs(final-windows[-2]['mean_frequency_hz'])
        results[name] = {'windows':windows, 'initial_two_cycle_frequency_hz':initial,
                         'initial_to_final_difference_hz':difference,
                         'final_two_window_difference_hz':adjacent_window_difference,
                         'screen_limit_hz':limit_hz,
                         'initial_to_final_within_calibration_limit':difference <= limit_hz,
                         'final_two_windows_within_calibration_limit':adjacent_window_difference <= limit_hz,
                         'independent_convergence_qualified':False}
    report = {'analysis_complete':True, 'audited_terminal_points':len(results),
              'target_mhz':args.target_mhz, 'records':results,
              'initial_to_final_screen_failing_points':sum(not r['initial_to_final_within_calibration_limit'] for r in results.values()),
              'sha256':pins, 'release_qualified':False, 'selected':False,
              'limitations':['Baseline-window diagnostic; not independent tighter-tolerance, half-step or longer-settling convergence qualification',
                             'Local spacing uses available adjacent whole-window baseline means; full interpolation and PVT remain incomplete',
                             'No physical noise/jitter or whole-PLL proof']}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('sha256','records')}))


if __name__ == '__main__':
    main()
