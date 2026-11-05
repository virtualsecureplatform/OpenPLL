#!/usr/bin/env python3
"""Parse a terminal combinational batch with the retained propagation semantics.

Raw finite-grid observations only; this does not create a qualified timing view.
"""
from array import array
import math
from pathlib import Path
import time
from characterize_compact_propagation import crossings
from run_dco_qualification import sha,save


def assess(plan,pins,out,deadline):
    cases=plan['fixtures']
    def status(state,**fields):
        save(out/'status.json',dict(state=state,release_qualified=False,**fields))
    def remaining():
        value=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if value<=0:raise TimeoutError('characterization campaign deadline reached')
        return value
    status('assessing_terminal_native_waveform')
    columns = [f'V({kind}_{i})' for i in range(len(cases)) for kind in ('IN', 'OUT')]
    times = array('d')
    values = [array('d') for _ in columns]
    terminal = False
    with (out/'batch.prn').open() as stream:
        assert stream.readline().split() == ['Index', 'TIME', *columns]
        for line in stream:
            if 'End of Xyce(TM) Simulation' in line:
                assert not terminal
                terminal = True
                continue
            row = line.split()
            if not row:
                continue
            assert not terminal and int(row[0]) == len(times)
            numbers = list(map(float, row[1:]))
            assert len(numbers) == len(columns)+1 and all(map(math.isfinite, numbers))
            times.append(numbers[0])
            for series, value in zip(values, numbers[1:]):
                series.append(value)
            if len(times)%1000 == 0:
                remaining()
    assert terminal and times[0] == 0 and times[-1] >= 34e-9-1e-15
    assert all(a < b for a, b in zip(times, times[1:]))
    records = []
    for i, case in enumerate(cases):
        remaining()
        incoming, outgoing = values[2*i:2*i+2]
        record = dict(case_index=i, passed=False, strict_output_slew_passed=False,
                      output_min_v=min(outgoing), output_max_v=max(outgoing))
        try:
            assert abs(incoming[0]) < 1e-6
            assert outgoing[0] >= 1.62 if case['inverted'] else outgoing[0] <= .18
            assert min(outgoing) < .18 and max(outgoing) > 1.62
            for rising in (False, True):
                starts = crossings(times, incoming, .9, rising)
                ends = crossings(times, outgoing, .9, rising != case['inverted'])
                assert len(starts) == len(ends) == 2
                delays = []
                for t in starts:
                    selected = [u for u in ends if t-1e-9 < u < t+5e-9]
                    assert len(selected) == 1
                    delays.append((selected[0]-t)*1e9)
                record['input_rise_delay_ns' if rising else 'input_fall_delay_ns'] = delays
            record['passed'] = True
        except AssertionError:
            record['reason'] = 'DC rail or propagation threshold/event correspondence failed'
        raw = {f'{"rise" if d else "fall"}_{level}': crossings(times, outgoing, level, d)
               for d in (False, True) for level in (.36, .9, 1.44)}
        strict = True
        for rising in (False, True):
            label = 'rise' if rising else 'fall'
            levels = (.36, .9, 1.44) if rising else (1.44, .9, .36)
            first, middle, last = [raw[f'{label}_{v}'] for v in levels]
            ordered = len(first) == len(middle) == len(last) == 2 and all(a < b < c for a, b, c in zip(first, middle, last))
            strict &= ordered
            if ordered:
                record[f'output_{label}_slew_ns'] = [(b-a)*1e9 for a, b in zip(first, last)]
        record['strict_output_slew_passed'] = strict
        if not strict:
            record['raw_output_threshold_crossings_ns'] = {k: [t*1e9 for t in v] for k, v in raw.items()}
        records.append(record)
    for path, digest in pins.items():
        assert sha(Path(path)) == digest, path
    remaining()
    artifacts = {str(p): sha(p) for p in out.iterdir() if p.is_file() and p.name != 'status.json'}
    passing = sum(r['passed'] for r in records)
    slew_passing = sum(r['strict_output_slew_passed'] for r in records)
    save(out/'assessment.json', dict(input_sha256=pins, artifacts=artifacts,
        fixtures=len(records), passing=passing, strict_output_slew_passing=slew_passing,
        records=records, pvt=plan['pvt'], all_native_waveform_events_terminal=True,
        numerical_domain_enclosure_qualified=False, physical_timing_qualified=False,
        release_qualified=False, scope=__doc__))
    status('terminal_assessment', fixtures=len(records), passing=passing,
           strict_output_slew_passing=slew_passing)
    print(f'Propagation {passing}/{len(records)}, strict slew {slew_passing}/{len(records)}', flush=True)

