#!/usr/bin/env python3
"""Validate boundary-observation bookkeeping with an ideal edge-triggered oracle.

Synthetic evidence only: this does not measure physical setup/hold or count as
a native capture-boundary pass. Faults must not produce passing controls.
"""
import argparse
from bisect import bisect_right
import json
from pathlib import Path

from run_compact_capture_boundaries import observe
from run_dco_qualification import sha, save


def value_at(points, t):
    index = bisect_right([p[0] for p in points], t)-1
    if index < 0:
        return points[0][1]
    if index == len(points)-1:
        return points[index][1]
    a, b = points[index:index+2]
    return a[1]+(b[1]-a[1])*(t-a[0])/(b[0]-a[0])


def oracle(case):
    # A separate ideal DFF evaluates actual source voltages on each clock
    # edge. It does not use the preparer's expected-value or sentinel fields.
    q = case['reset_value']
    output_points = [(0, q*1.8)]
    for edge in (10, 20):
        data = value_at(case['data'], edge-1e-6)
        control = value_at(case['control'], edge-1e-6)
        captured = int(data > .9) if control > .9 else case['reset_value']
        output_points.extend([(edge+.04, q*1.8), (edge+.06, captured*1.8)])
        q = captured
    times_ns = [i*.002 for i in range(14001)]
    values = [[value_at(points, t) for t in times_ns]
              for points in (case['clock'], case['data'], case['control'], output_points)]
    return [t*1e-9 for t in times_ns], values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    plan_path, out = args.plan.resolve(), args.output.resolve()
    plan = json.loads(plan_path.read_text())
    pins = {str(p): sha(p) for p in (plan_path, Path(__file__).resolve(),
            Path(__file__).with_name('run_compact_capture_boundaries.py').resolve())}
    assert len(plan['fixtures']) == 198
    observations, controls = 0, 0
    for case in plan['fixtures']:
        times, values = oracle(case)
        result = observe(times, values, case)
        observations += 1
        if case['sentinel']:
            assert result['sentinel_passed'], (case['master'], case['kind'], case['offset_ps'])
            controls += 1
    case = next(c for c in plan['fixtures'] if c['kind'] == 'data_rise' and c['offset_ps'] == -1000)
    times, values = oracle(case)
    faults = []
    wrong_expected = {**case, 'sentinel_expected_final_value': 0}
    assert not observe(times, values, wrong_expected)['sentinel_passed']
    faults.append('wrong_capture_expectation')
    glitched = list(values)
    glitched[-1] = [0 if 24e-9 <= t < 25e-9 else v for t, v in zip(times, values[-1])]
    assert not observe(times, glitched, case)['sentinel_passed']
    faults.append('extra_output_pulse_with_correct_final_value')
    for label, modified in (
        ('missing_clock_edge', [[0]*len(times), *values[1:]]),
        ('missing_changing_input_edge', [values[0], [0]*len(times), *values[2:]]),
        ('wrong_pretest_state', [*values[:3], [1.8]*len(times)])):
        try:
            observe(times, modified, case)
        except AssertionError:
            faults.append(label)
        else:
            raise AssertionError('failed to reject '+label)
    assert observations == 198 and controls == 36 and len(faults) == 5
    out.mkdir(parents=True, exist_ok=False)
    save(out/'assessment.json', dict(input_sha256=pins, synthetic_observations=observations,
        synthetic_separated_controls_passed=controls, negative_controls_rejected=faults,
        native_jobs_added=0, physical_timing_qualified=False, release_qualified=False,
        scope=__doc__))
    print(f'Observer validated on{observations}synthetic captures, {controls}controls and{len(faults)}faults')


if __name__ == '__main__':
    main()
