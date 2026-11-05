#!/usr/bin/env python3
"""Audit terminal extracted-DCO waveforms; does not qualify calibration or PLL jitter."""
import argparse
import hashlib
import json
import math
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def crossings(rows, threshold, rising, start):
    times = []
    for (ta, va), (tb, vb) in zip(rows, rows[1:]):
        crossed = va < threshold <= vb if rising else va >= threshold > vb
        if crossed:
            t = ta + (threshold - va) * (tb - ta) / (vb - va)
            if t >= start:
                times.append(t)
    return times


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    pins, records, pending = {}, {}, []

    def pin(path, expected=None):
        path = str(path)
        if path not in pins:
            pins[path] = sha(path)
        if expected is not None:
            assert pins[path] == expected, path
        return pins[path]

    for sidecar in sorted(args.directory.resolve().glob('dco_*.provenance.json')):
        saved = json.loads(sidecar.read_text())
        name = sidecar.name.removesuffix('.provenance.json')
        if not saved.get('completed'):
            pending.append(name)
            continue
        fingerprint = {k: saved[k] for k in ('files', 'parameters')}
        assert hashlib.sha256(json.dumps(fingerprint, sort_keys=True, allow_nan=False).encode()).hexdigest() == saved['fingerprint']
        for path, wanted in saved['files'].items():
            pin(path, wanted)
        parameters = saved['parameters']
        assert parameters['simulator'] == 'xyce'
        start = parameters['meas_start_ns'] * 1e-9
        stop = parameters['sim_time_ns'] * 1e-9
        supply = parameters['vdd']
        deck = sidecar.with_name(name + '.spice')
        pin(deck, saved['netlist_sha256'])
        log = sidecar.with_name(name + '.log')
        wave = sidecar.with_name(name + '.prn')
        metrics_path = sidecar.with_name(name + '.mt0')
        for path in (sidecar, log, wave, metrics_path):
            pin(path)
        assert 'End of Xyce(TM) Simulation' in log.read_text()
        text = wave.read_text()
        assert text.splitlines()[0].split() == ['Index', 'TIME', 'V(PLLOUT)']
        assert 'End of Xyce(TM) Simulation' in text
        rows = []
        for line in text.splitlines()[1:]:
            values = line.split()
            if values and values[0].isdigit():
                assert len(values) == 3
                index, t, v = map(float, values)
                assert all(map(math.isfinite, (index, t, v))) and index == len(rows)
                rows.append((t, v))
        assert rows[0][0] == 0 and rows[-1][0] >= stop - 1e-14
        assert all(a[0] < b[0] for a, b in zip(rows, rows[1:]))
        rises = crossings(rows, supply / 2, True, start)
        falls = crossings(rows, supply / 2, False, start)
        assert len(rises) >= 3
        periods, highs, lows = [], [], []
        for a, b in zip(rises, rises[1:]):
            between = [t for t in falls if a < t < b]
            assert len(between) == 1
            periods.append(b - a)
            highs.append(between[0] - a)
            lows.append(b - between[0])
        assert all(p > 0 for p in periods + highs + lows)
        measured = {key: float(value) for key, value in
                    re.findall(r'(?m)^([A-Z_]+) = (\S+)$', metrics_path.read_text())}
        frequency = 2 / (rises[2] - rises[0])
        # Xyce measurements are printed to seven significant decimal digits.
        assert abs(frequency / measured['FREQ_HZ'] - 1) < 2e-6
        mean_period = statistics.mean(periods)
        records[name] = {
            'complete_wave_audit_pass': True,
            'provenance_fingerprint': saved['fingerprint'],
            'measurement_window_ns': [start * 1e9, stop * 1e9],
            'complete_cycles': len(periods),
            'first_two_cycle_frequency_hz': frequency,
            'whole_window_mean_frequency_hz': 1 / mean_period,
            'period_min_max_ns': [min(periods) * 1e9, max(periods) * 1e9],
            'high_width_min_max_ns': [min(highs) * 1e9, max(highs) * 1e9],
            'low_width_min_max_ns': [min(lows) * 1e9, max(lows) * 1e9],
            'duty_ratio_min_max': [min(h/p for h,p in zip(highs,periods)), max(h/p for h,p in zip(highs,periods))],
            'negative_native_measurements_retained': {k:v for k,v in measured.items() if v < 0},
        }
        print(name, 'audited', len(periods), 'cycles', flush=True)
    assert records
    pin(Path(__file__).resolve())
    report = {
        'pass': True,
        'observed_utc': datetime.now(timezone.utc).isoformat(),
        'audited_terminal_points': len(records),
        'nonterminal_sidecars_skipped': pending,
        'records': records,
        'unique_evidence_pins_verified': len(pins),
        'sha256': pins,
        'release_qualified': False,
        'selected': False,
        'limitations': ['Completed points only; missing codes and convergence/interpolation/full-PVT calibration remain unqualified',
                        'Deterministic transient with ideal supply; period variation is not physical jitter/noise qualification',
                        'No whole-PLL acquisition, mode-transition or sustained-window proof'],
    }
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print('Frozen terminal waveform audit:', args.output, flush=True)


if __name__ == '__main__':
    main()
