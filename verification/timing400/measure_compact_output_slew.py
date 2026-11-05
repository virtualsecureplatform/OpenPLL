#!/usr/bin/env python3
"""Measure output slew from a terminal propagation batch without rerunning SPICE.

Raw threshold measurements only; no numerical or timing-library qualification.
"""
import argparse
from array import array
import json
import math
from pathlib import Path
import time

from check_compact_clock_tree import verify
from run_dco_qualification import sha, save


def edges(times, values, level, rising):
    result = []
    for i in range(1, len(times)):
        a, b = values[i-1], values[i]
        if (a < level <= b) if rising else (a > level >= b):
            result.append(times[i-1] + (times[i]-times[i-1])*(level-a)/(b-a))
    return result


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    batch, out = args.batch.resolve(), args.output.resolve()
    receipt = verify(batch/'assessment.json')
    assert receipt['passing'] == receipt['fixtures'] and receipt['all_native_waveform_events_terminal']
    plan = json.loads((batch/'plan.json').read_text())
    cases = plan['fixtures']
    assert len(cases) == receipt['fixtures']
    out.mkdir(parents=True, exist_ok=False)
    files = [Path(__file__).resolve(), Path(__file__).with_name('check_compact_clock_tree.py'),
             batch/'assessment.json', batch/'plan.json', batch/'batch.prn']
    pins = {str(p.resolve()): sha(p) for p in files}
    times = array('d')
    values = [array('d') for _ in range(2*len(cases))]
    terminal = False
    with (batch/'batch.prn').open() as stream:
        expected = ['Index', 'TIME']
        for i in range(len(cases)):
            expected.extend([f'V(IN_{i})', f'V(OUT_{i})'])
        assert stream.readline().split() == expected
        for line in stream:
            if 'End of Xyce(TM) Simulation' in line:
                assert not terminal
                terminal = True
                continue
            row = line.split()
            if not row:
                continue
            assert not terminal and row[0].isdigit() and int(row[0]) == len(times)
            numbers = list(map(float, row[1:]))
            assert len(numbers) == 1+len(values) and all(map(math.isfinite, numbers))
            times.append(numbers[0])
            for series, value in zip(values, numbers[1:]):
                series.append(value)
            assert time.monotonic()-started < 43200
    assert terminal and times[0] == 0 and times[-1] >= 34e-9-1e-15
    assert all(a < b for a, b in zip(times, times[1:]))
    records = []
    for i, case in enumerate(cases):
        record = dict(case_index=i, passed=False)
        try:
            incoming, outgoing = values[2*i:2*i+2]
            for rising in (False, True):
                label = 'rise' if rising else 'fall'
                low, high = (.36, 1.44) if rising else (1.44, .36)
                for kind, signal in [('input', incoming), ('output', outgoing)]:
                    first = edges(times, signal, low, rising)
                    middle = edges(times, signal, .9, rising)
                    last = edges(times, signal, high, rising)
                    assert len(first) == len(middle) == len(last) == 2
                    assert all(a < b < c for a, b, c in zip(first, middle, last))
                    slews = [(b-a)*1e9 for a, b in zip(first, last)]
                    record[f'{kind}_{label}_slew_ns'] = slews
                    if kind == 'input':
                        expected_slew = .6*case['full_ramp_ps']/1000
                        # The source stimulus is piecewise linear; allow two
                        # declared 2 ps maximum steps for threshold sampling.
                        assert all(abs(s-expected_slew) <= .004 for s in slews)
                assert time.monotonic()-started < 43200
            record['passed'] = True
        except AssertionError:
            record['reason'] = 'threshold event order/count or input-ramp correspondence failed'
        records.append(record)
    for path, digest in pins.items():
        assert sha(Path(path)) == digest, path
    save(out/'assessment.json', dict(input_sha256=pins, artifacts={},
        fixtures=len(records), passing=sum(r['passed'] for r in records), records=records,
        pvt=plan['pvt'], measurement='20-80% rise and 80-20% fall, two complete events each',
        native_jobs_added=0, numerical_convergence_qualified=False,
        physical_timing_qualified=False, release_qualified=False, scope=__doc__))
    print(f'Output-slew measurements: {sum(r["passed"] for r in records)}/{len(records)}', flush=True)


if __name__ == '__main__':
    main()
