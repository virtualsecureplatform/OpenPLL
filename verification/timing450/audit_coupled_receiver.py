#!/usr/bin/env python3
"""Independently audit native coupled BBPD/event-receiver grid and full waveforms."""
import argparse
import hashlib
import itertools
import json
import math
import re
from collections import Counter
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(pins):
    for name, wanted in pins.items():
        if digest(name) != wanted:
            raise RuntimeError(f'Changed pinned input: {name}')


def edges(rows, column, threshold):
    rising, falling = [], []
    for a, b in zip(rows, rows[1:]):
        if a[column] < threshold <= b[column] or a[column] >= threshold > b[column]:
            t = a[1] + (threshold - a[column]) * (b[1] - a[1]) / (b[column] - a[column])
            if 5e-9 <= t <= 85e-9:
                (rising if b[column] > a[column] else falling).append(t)
    return rising, falling


def score(rows, supply, direction):
    details = {}
    for name, column in [('UP', 6), ('DN', 7)]:
        rise, fall = edges(rows, column, supply / 2)
        initial = [r[column] for r in rows if 5e-9 <= r[1] <= 8e-9]
        first = [r[column] for r in rows if 25e-9 <= r[1] <= 29e-9]
        second = [r[column] for r in rows if 65e-9 <= r[1] <= 69e-9]
        assert initial and first and second
        passed = all(v < .1 * supply for v in initial)
        if name == direction:
            passed &= (len(rise) == len(fall) == 1 and 10e-9 <= rise[0] <= 25e-9
                       and 50e-9 <= fall[0] <= 65e-9 and min(first) > .8 * supply
                       and max(second) < .2 * supply)
        else:
            passed &= (not rise and not fall and all(r[column] < .2 * supply
                                                   for r in rows if 5e-9 <= r[1] <= 85e-9))
        details[name] = {'pass': bool(passed), 'rise_ns': [t * 1e9 for t in rise],
                         'fall_ns': [t * 1e9 for t in fall]}
    return all(v['pass'] for v in details.values()), details


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    assert not args.output.exists()
    directory = args.directory.resolve()
    manifest = directory / 'input_manifest.json'
    source = json.loads(manifest.read_text())
    verify(source['sha256'])
    pins = dict(source['sha256'])
    pins[str(manifest)] = digest(manifest)
    pins[str(Path(__file__).resolve())] = digest(Path(__file__))
    required = set(itertools.product(('ss', 'tt', 'ff', 'sf', 'fs'), (1.62, 1.8, 1.95),
                                     (-40, 27, 125), (-200, 200), (20, 200)))
    assert source['requested_points'] == len(required) == 180
    actual = set()
    points = []
    counts = Counter()
    for circuit in sorted(directory.glob('*/loaded.cir')):
        match = re.fullmatch(r'(ss|tt|ff|sf|fs)_([0-9.]+)V_(-?\d+)C_phase(-?\d+)ps_edge(\d+)ps', circuit.parent.name)
        assert match
        corner, v, temperature, phase, edge = match.groups()
        point = (corner, float(v), int(temperature), int(phase), int(edge))
        assert point not in actual and point in required
        actual.add(point)
        deck = circuit.read_text()
        assert f'.param VDD={float(v):g}' in deck
        assert f'.options device temp={temperature}' in deck
        assert re.search(r'(?m)^\.lib "[^\n]+" ' + corner + r'$', deck)
        assert str(circuit) in source['sha256']
        receipt = circuit.parent / 'assessment.json'
        if not receipt.exists():
            continue
        record = json.loads(receipt.read_text())
        assert (record['corner'], record['supply_v'], record['temperature_c'], record['phase_ps'], record['edge_ps']) == point
        assert record['exit_code'] == 0 and record['simulation_completed']
        verify(record['sha256']);pins.update(record['sha256']);pins[str(receipt)] = digest(receipt)
        log = (circuit.parent / 'run.log').read_text()
        assert not any(s in log for s in ('Unrecognized dot line', 'Simulation aborted', 'Netlist error'))
        text = (circuit.parent / 'loaded.prn').read_text()
        assert 'End of Xyce(TM) Simulation' in text
        rows = [list(map(float, line.split())) for line in text.splitlines()
                if line.split() and line.split()[0].isdigit()]
        assert rows and rows[0][1] == 0 and rows[-1][1] >= 90e-9 - 1e-14
        assert all(len(r) == 8 and all(map(math.isfinite, r)) for r in rows)
        assert all(a[1] < b[1] for a, b in zip(rows, rows[1:]))
        direction = 'UP' if int(phase) > 0 else 'DN'
        passed, details = score(rows, float(v), direction)
        control, _ = score(rows, float(v), 'DN' if direction == 'UP' else 'UP')
        assert passed == record['direction_and_two_event_capture_pass']
        for name, measurements in details.items():
            original = record['receiver_events'][name]
            for own, old in [('rise_ns','rising_edges_ns'), ('fall_ns','falling_edges_ns')]:
                assert len(measurements[own]) == len(original[old])
                assert all(abs(a-b) < 1e-7 for a,b in zip(measurements[own],original[old]))
        points.append({'receipt': str(receipt), 'sha256': digest(receipt), 'point': point,
                       'pass': passed, 'wrong_direction_rejected': not control, 'remeasured': details})
        counts[corner] += 1
    assert actual == required
    verify(pins)
    result = {'requested_points': 180, 'completed_points': len(points),
              'complete': len(points) == 180, 'all_completed_pass': bool(points) and all(p['pass'] for p in points),
              'all_wrong_direction_controls_rejected': bool(points) and all(p['wrong_direction_rejected'] for p in points),
              'corners': dict(counts), 'points': points, 'input_pins': pins,
              'release_qualified': False, 'selected': False,
              'scope': 'Exact45 primitive PVT x +/-200ps x20/200ps; complete90ns native waves independently remeasured',
              'limitations': ['17-cell event receiver only; nonlinear synchronizers/reset generation omitted',
                              'Fixed max routeRC/static aggressors, ideal rails; no statistical MTBF or wholePLL proof']}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('points','input_pins')}))
    if not (result['all_completed_pass'] and result['all_wrong_direction_controls_rejected']
            and (args.allow_partial or result['complete'])):
        raise RuntimeError('Coupled receiver audit failed or incomplete')


if __name__ == '__main__':
    main()
