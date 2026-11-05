#!/usr/bin/env python3
"""Measure sampled-detector transition brackets; never qualify a whole PLL.

Read only terminal point receipts. A live campaign may yield partial curves;
these are reported but cannot produce an all-PVT bracket result.
"""
import argparse
import itertools
import json
from pathlib import Path
from characterize_bbpd import sha, verify, read_rows, measure

PHASES = tuple(range(-200, 201, 25))
GROUPS = tuple(itertools.product(('ss', 'tt', 'ff', 'sf', 'fs'),
                                 (1.62, 1.8, 1.95), (-40, 27, 125), (20, 200)))


def summarize(points, groups=GROUPS, phases=PHASES):
    groups, phases = tuple(groups), tuple(phases)
    if tuple(sorted(set(phases))) != phases or not phases:
        raise RuntimeError('Phase grid must be unique and increasing')
    expected = {(g, p) for g in groups for p in phases}
    indexed = {}
    for point in points:
        group = tuple(point[k] for k in ('corner', 'supply_v', 'temperature_c', 'edge_ps'))
        key = group, point['phase_ps']
        if key not in expected or key in indexed:
            raise RuntimeError('Duplicate or unexpected PVT/phase point')
        indexed[key] = point
    curves = []
    for group in groups:
        states = []
        for phase in phases:
            point = indexed.get((group, phase))
            state = None
            if point and point['simulation_completed'] and point['one_active_output']:
                active = [name for name, wave in point['output_waveforms'].items()
                          if wave['complete_two_pulses']]
                if len(active) == 1 and active[0] in ('BBPD[0]', 'BBPD[1]'):
                    state = 'DN' if active[0] == 'BBPD[0]' else 'UP'
            states.append(state)
        complete = all((group, p) in indexed for p in phases)
        valid = complete and all(s is not None for s in states)
        monotone = valid and all(a <= b for a, b in zip(states, states[1:]))
        bracket = None
        if monotone and 'DN' in states and 'UP' in states:
            first_up = states.index('UP')
            bracket = [phases[first_up - 1], phases[first_up]]
        curves.append(dict(zip(('corner', 'supply_v', 'temperature_c', 'edge_ps'), group),
                           complete=complete, exclusive_two_pulses_at_every_phase=valid,
                           monotone=bool(monotone), transition_bracket_ps=bracket,
                           phase_states=dict(zip(map(str, phases), states))))
    brackets = [c['transition_bracket_ps'] for c in curves]
    all_bracketed = bool(curves) and all(b is not None for b in brackets)
    # A deterministic grid bracket is a detector measurement, not a PLL error.
    return {'requested_points': len(expected), 'observed_points': len(indexed),
            'all_points_present': len(indexed) == len(expected),
            'all_curves_bracketed': all_bracketed,
            'maximum_absolute_transition_bound_ps':
                max(abs(x) for b in brackets for x in b) if all_bracketed else None,
            'curves': curves, 'release_qualified': False, 'selected': False,
            'whole_pll_phase_requirement_pass': False,
            'limitations': ['Deterministic two-opportunity grid; no metastability probability or settling proof',
                            'Lumped receiver capacitance and ideal supplies; no full-loop phase/jitter result']}


def analyze(directory):
    manifest = directory / 'input_manifest.json'
    source = json.loads(manifest.read_text())
    verify(source['sha256'])
    pins = {str(manifest): sha(manifest), str(Path(__file__).resolve()): sha(Path(__file__).resolve())}
    points = []
    for receipt in sorted(directory.glob('*/assessment.json')):
        point = json.loads(receipt.read_text())
        verify(point['sha256'])
        # Recompute from the native waveform rather than trusting status flags.
        if point['simulation_completed']:
            if point['exit_code'] != 0:
                raise RuntimeError('Completed receipt has a failing native exit code')
            waves = [Path(p) for p in point['sha256'] if p.endswith('/loaded.prn')]
            if len(waves) != 1:
                raise RuntimeError('Missing or ambiguous native waveform')
            measured = measure(read_rows(waves[0]), point['supply_v'])
            if measured != point['output_waveforms']:
                raise RuntimeError('Point receipt disagrees with native waveform')
            active = [name for name, w in measured.items() if w['complete_two_pulses']]
            exclusive = len(active) == 1 and all(w['maximum_v'] < .2 * point['supply_v']
                        for name, w in measured.items() if name not in active)
            if exclusive != point['one_active_output']:
                raise RuntimeError('Point receipt disagrees with native exclusivity')
        points.append(point)
        pins[str(receipt)] = sha(receipt)
        pins.update(point['sha256'])
    result = summarize(points)
    if source['requested_points'] != result['requested_points']:
        raise RuntimeError('Campaign grid does not match the expected phase transfer grid')
    verify(pins)
    result['sha256'] = pins
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.directory.resolve() in args.output.resolve().parents:
        raise RuntimeError('Write a fresh assessment outside the live campaign')
    result = analyze(args.directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('curves', 'sha256')}))


if __name__ == '__main__':
    main()
