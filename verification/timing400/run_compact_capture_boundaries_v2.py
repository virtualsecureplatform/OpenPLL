#!/usr/bin/env python3
"""Run one capture-boundary batch with guarded admission and a total12h budget.

Preserves both successful and ambiguous captures and every post-test50% edge.
No constraint interpolation, library adoption or timing qualification occurs.
"""
import argparse
from array import array
from bisect import bisect_left
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import time

from characterize_compact_propagation import ROOT, XYCE, crossings
from guarded_native_admission import AdmissionDeferred, launch as guarded_launch, scan
from run_dco_qualification import sha, save


def logic_interval(times, values, start_ns, stop_ns):
    start, stop = bisect_left(times, start_ns*1e-9), bisect_left(times, stop_ns*1e-9)
    selected = values[start:stop]
    assert selected and times[start] < (start_ns+.01)*1e-9
    assert times[stop-1] > (stop_ns-.01)*1e-9
    low, high = min(selected), max(selected)
    state = 0 if high <= .18 else 1 if low >= 1.62 else None
    return dict(logic_value=state, minimum_v=low, maximum_v=high)


def observe(times, values, case):
    clk, data, control, output = values
    clock_edges = crossings(times, clk, .9, True)
    assert len(clock_edges) == 2
    assert all(abs(t*1e9-v) < 1e-6 for t, v in zip(clock_edges, (10, 20)))
    changing = control if case['kind'] == 'async_release' else data
    rising = case['kind'] != 'data_fall'
    edges = crossings(times, changing, .9, rising)
    assert len(edges) == 1 and abs(edges[0]*1e9-case['changing_input_center_ns']) < 1e-6
    assert abs(control[0]) < 1e-6
    assert (output[0] <= .18 if case['reset_value'] == 0 else output[0] >= 1.62)
    pre = logic_interval(times, output, 18, 18.5)
    assert pre['logic_value'] == case['pretest_value']
    final = logic_interval(times, output, 27, 28)
    observed = {label: [t*1e9 for t in crossings(times, output, .9, direction) if t >= 18.5e-9]
                for label, direction in (('rising', True), ('falling', False))}
    final_value = final['logic_value']
    outcome = ('ambiguous_or_unsettled' if final_value is None else
               'changed_value' if final_value == case['changed_value'] else 'pretest_value')
    result = dict(pretest=pre, final=final, outcome=outcome,
                  post_test_50percent_edges_ns=observed,
                  observed_input_minus_clock_ps=(edges[0]-clock_edges[-1])*1e12)
    if case['sentinel']:
        expected = case['sentinel_expected_final_value']
        expected_count = int(expected != case['pretest_value'])
        correct_direction = 'rising' if expected > case['pretest_value'] else 'falling'
        result['sentinel_passed'] = (final_value == expected and
            sum(map(len, observed.values())) == expected_count and
            (not expected_count or len(observed[correct_direction]) == 1))
    return result


def main():
    deadline = time.monotonic()+43200
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--canonical-workspace', required=True, type=Path)
    parser.add_argument('--controller-pid', required=True, type=int)
    args = parser.parse_args()
    assert ROOT == args.canonical_workspace.resolve(), 'Canonical host absolute script path required'
    path, out = args.plan.resolve(), args.output.resolve()
    plan = json.loads(path.read_text())
    assert len(plan['fixtures']) == 198 and plan['pvt']['supply_v'] == 1.8
    pins = {**plan['input_sha256'], str(path): sha(path),
            str(Path(__file__).resolve()): sha(Path(__file__).resolve())}
    for dependency in ('characterize_compact_propagation.py', 'run_dco_qualification.py', 'guarded_native_admission.py'):
        dep = Path(__file__).with_name(dependency).resolve()
        pins[str(dep)] = sha(dep)
    for name, digest in pins.items():
        assert sha(name) == digest, name
    out.mkdir(parents=True, exist_ok=False)
    with (path.parent/'native_run.json').open('x') as stream:
        json.dump(dict(runner_pid=os.getpid(), output=str(out),
                       started_utc=datetime.now(timezone.utc).isoformat(),
                       automatic_identical_retry=False), stream, indent=2)

    def status(state, **fields):
        save(out/'status.json', dict(state=state, observed_utc=datetime.now(timezone.utc).isoformat(),
             total_budget_s=43200, release_qualified=False, **fields))

    def remaining():
        value = deadline-time.monotonic()
        if value <= 0:
            status('timeout_inconclusive')
            raise TimeoutError('total12h check budget exhausted')
        return value

    command = [str(XYCE), '-linsolv', 'KLU', '-quiet', '-o', str(out/'batch'), str(path.parent/'batch.cir')]
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    with (out/'run.log').open('x') as log:
        while True:
            remaining()
            try:
                if len(scan()) >= 4:
                    raise AdmissionDeferred('four native slots occupied')
                child = guarded_launch(command, env, log, args.controller_pid,
                                       out/'guarded_admission.json')
                break
            except AdmissionDeferred as error:
                status('waiting_for_guarded_native_capacity', reason=str(error))
                time.sleep(min(30, remaining()))
        save(out/'launch.json', dict(pid=child.pid, command=command, input_sha256=pins,
                                   thread_policy='OMP/OPENBLAS/MKL=1'))
        status('native_running', native_pid=child.pid)
        try:
            code = child.wait(timeout=remaining())
        except (subprocess.TimeoutExpired, TimeoutError):
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
    status('assessing_terminal_waveform')
    times, columns = array('d'), plan['waveform_columns']
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
    assert terminal and times[0] == 0 and times[-1] >= plan['stop_ns']*1e-9-1e-15
    assert all(a < b for a, b in zip(times, times[1:]))
    records = []
    for i, case in enumerate(plan['fixtures']):
        remaining()
        record = dict(case_index=i, observation_integrity_passed=False)
        try:
            record.update(observe(times, values[4*i:4*i+4], case), observation_integrity_passed=True)
        except AssertionError:
            record['reason'] = 'initial state, pretest state, source timing or observation horizon failed'
        records.append(record)
    for name, digest in pins.items():
        assert sha(name) == digest, name
    remaining()
    controls = [r for r, c in zip(records, plan['fixtures']) if c['sentinel']]
    save(out/'assessment.json', dict(input_sha256=pins,
        artifacts={str(p): sha(p) for p in out.iterdir() if p.is_file() and p.name != 'status.json'},
        records=records, fixtures=len(records), observation_integrity_passing=sum(r['observation_integrity_passed'] for r in records),
        separated_controls=len(controls), separated_controls_passing=sum(r.get('sentinel_passed', False) for r in controls),
        all_native_waveform_events_terminal=True, pvt=plan['pvt'],
        setup_hold_recovery_removal_qualified=False, numerical_domain_enclosure_qualified=False,
        physical_timing_qualified=False, release_qualified=False, scope=__doc__))
    status('terminal_assessment', fixtures=len(records), separated_controls_passing=sum(r.get('sentinel_passed', False) for r in controls))


if __name__ == '__main__':
    main()
