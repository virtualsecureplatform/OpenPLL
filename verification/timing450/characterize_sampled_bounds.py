#!/usr/bin/env python3
"""Verify complete sampled-detector PVT receipts and bound both pulse phases."""
import argparse
import itertools
import json
import math
from pathlib import Path
from characterize_bbpd import sha, verify, read_rows, measure

GRID = set(itertools.product(('ss', 'tt', 'ff', 'sf', 'fs'), (1.62, 1.8, 1.95),
                             (-40, 27, 125), (-250, 250), (20, 200)))


def sampled_bounds(points, grid=GRID):
    seen = set()
    samples = {name: [] for name in ('rise', 'fall', 'high', 'low', 'period')}
    for point in points:
        key = tuple(point.get(k) for k in ('corner', 'supply_v', 'temperature_c', 'phase_ps', 'edge_ps'))
        if key not in grid or key in seen or point.get('simulation_completed') is not True or point.get('exit_code') != 0:
            raise RuntimeError('Missing, duplicate, unsupported or incomplete sampled point')
        seen.add(key)
        waves = point['output_waveforms']
        if set(waves) != {'BBPD[0]', 'BBPD[1]'}:
            raise RuntimeError('Missing sampled output interface')
        expected = 'BBPD[0]' if point['phase_ps'] < 0 else 'BBPD[1]'
        active = [name for name, wave in waves.items() if wave['complete_two_pulses']]
        if active != [expected] or any(w['maximum_v'] >= .2 * point['supply_v'] for name, w in waves.items() if name != expected):
            raise RuntimeError('Wrong sign or nonexclusive sampled pulses')
        wave = waves[expected]
        for label, name in (('rise', 'rising_slew_20_80_ns'), ('fall', 'falling_slew_80_20_ns'), ('high', 'high_pulse_widths_ns')):
            values = wave[name]
            if len(values) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in values):
                raise RuntimeError('Invalid sampled waveform measurements')
            samples[label].extend(values)
        edges = wave['rising_half_supply_edges_ns']
        if len(edges) != 2 or not all(type(v) in (int, float) and math.isfinite(v) for v in edges):
            raise RuntimeError('Invalid sampled rising edges')
        period = edges[1] - edges[0]
        low = period - wave['high_pulse_widths_ns'][0]
        if period <= 0 or low <= 0:
            raise RuntimeError('Missing complete low pulse interval')
        samples['period'].append(period)
        samples['low'].append(low)
    if seen != grid:
        raise RuntimeError('Incomplete sampled PVT grid')
    step = .025
    minimum = lambda name: round(math.floor((min(samples[name]) - step) / step) * step, 9)
    maximum = lambda name: round(math.ceil((max(samples[name]) + step) / step) * step, 9)
    result = {'rise_ns': maximum('rise'), 'fall_ns': maximum('fall'),
              'minimum_high_ns': minimum('high'), 'minimum_low_ns': minimum('low'),
              'maximum_high_ns': maximum('high'), 'guard_ns': step,
              'observed_rising_period_range_ns': [min(samples['period']), max(samples['period'])],
              'verified_points': len(seen)}
    if min(result['minimum_high_ns'], result['minimum_low_ns']) <= 0:
        raise RuntimeError('Pulse interval has no positive guarded bound')
    return result


def analyze(directory):
    aggregate = directory / 'assessment.json'
    evidence = json.loads(aggregate.read_text())
    manifest = directory / 'input_manifest.json'
    if sha(manifest) != evidence['input_manifest_sha256']:
        raise RuntimeError('Changed sampled input manifest')
    verify(json.loads(manifest.read_text())['sha256'])
    verify(evidence['receipts'])
    points, pins = [], {str(aggregate): sha(aggregate), str(manifest): sha(manifest),
                       str(Path(__file__).resolve()): sha(Path(__file__).resolve())}
    for receipt, digest in evidence['receipts'].items():
        point = json.loads(Path(receipt).read_text())
        verify(point['sha256'])
        waveform = Path(receipt).parent / 'loaded.prn'
        if point['simulation_completed'] and measure(read_rows(waveform), point['supply_v']) != point['output_waveforms']:
            raise RuntimeError('Sampled measurements disagree with native waveform')
        points.append(point)
        pins[receipt] = digest
        pins.update(point['sha256'])
    result = sampled_bounds(points)
    if evidence['completed_points'] != result['verified_points'] or evidence['requested_points'] != result['verified_points']:
        raise RuntimeError('Aggregate count disagrees with native grid')
    verify(pins)
    return {'bounds': result, 'sha256': pins, 'release_qualified': False, 'selected': False,
            'scope': '45 primitive PVT points, +/-250ps,20/200ps inputs; lumped routed capacitance, two opportunities, fixed ideal rails',
            'limitations': ['Low time measured between the first falling and second rising edge only',
                            'No arbitrary phase/frequency/duty or metastability settling bound',
                            'No nonlinear receiver or whole-PLL qualification']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError('Require a fresh output')
    result = analyze(args.directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['bounds']))


if __name__ == '__main__':
    main()
