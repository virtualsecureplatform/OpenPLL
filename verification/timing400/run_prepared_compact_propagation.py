#!/usr/bin/env python3
"""Run a prepared combinational characterization deck once within total12h.

Uses KLU and explicit single-thread BLAS. Records propagation and raw output
slew crossings without filtering ambiguous waveforms. No library adoption.
"""
import argparse
from array import array
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import time

from characterize_compact_propagation import XYCE, admit_one, crossings
from run_dco_qualification import sha, save


def main():
    deadline = time.monotonic()+43200
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    plan_path, out = args.plan.resolve(), args.output.resolve()
    plan = json.loads(plan_path.read_text())
    cases = plan['fixtures']
    assert cases and plan['pvt']['supply_v'] == 1.8
    pins = dict(plan['input_sha256'])
    for p in (plan_path, Path(__file__).resolve(), Path(__file__).with_name('characterize_compact_propagation.py'), XYCE):
        pins[str(p.resolve())] = sha(p)
    for path, digest in pins.items():
        assert sha(Path(path)) == digest, path
    deck = plan_path.parent/'batch.cir'
    assert pins[str(deck)] == sha(deck)
    out.mkdir(parents=True, exist_ok=False)
    with (plan_path.parent/'native_run.json').open('x') as stream:
        json.dump(dict(runner_pid=os.getpid(), output=str(out),
            started_utc=datetime.now(timezone.utc).isoformat(), automatic_identical_retry=False), stream, indent=2)

    def status(state, **fields):
        save(out/'status.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
            state=state, total_budget_s=43200, release_qualified=False, **fields))

    def remaining():
        value = deadline-time.monotonic()
        if value <= 0:
            status('timeout_inconclusive')
            raise TimeoutError('total characterization budget reached')
        return value

    while True:
        remaining()
        try:
            admit_one(out)
            break
        except AssertionError as error:
            status('waiting_for_native_capacity', reason=str(error))
            time.sleep(min(30, remaining()))
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    command = [str(XYCE), '-linsolv', 'KLU', '-quiet', '-o', str(out/'batch'), str(deck)]
    with (out/'run.log').open('x') as stream:
        child = subprocess.Popen(command, env=env, stdout=stream, stderr=subprocess.STDOUT)
        save(out/'launch.json', dict(pid=child.pid, command=command, input_sha256=pins,
            total_budget_s=43200, thread_policy='OMP/OPENBLAS/MKL=1', release_qualified=False))
        status('native_running', native_pid=child.pid)
        try:
            code = child.wait(timeout=remaining())
        except subprocess.TimeoutExpired:
            child.terminate()
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            status('timeout_inconclusive', native_pid=child.pid)
            return
    if code:
        status('native_nonpass', exit_code=code)
        return
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


if __name__ == '__main__':
    main()
