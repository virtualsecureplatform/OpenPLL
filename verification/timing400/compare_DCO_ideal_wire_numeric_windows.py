#!/usr/bin/env python3
"""Await the identified numerical diagnostic, then compare matched intervals.

This is a read-only comparison of ideal-wire data, with joint changes in time
step/tolerances/duration. It cannot qualify physical calibration or independent
one-at-a-time convergence tests.
"""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process


def edges(path, duration):
    lines = path.read_text().splitlines()
    assert lines[0].split() == ['Index', 'TIME', 'V(PLLOUT)', 'I(VVPWR)']
    assert lines[-1] == 'End of Xyce(TM) Simulation'
    data = []
    for line in lines[1:-1]:
        row = line.split()
        assert len(row) == 4 and int(row[0]) == len(data)
        data.append(tuple(float(value) for value in row[1:]))
    assert all(math.isfinite(value) for row in data for value in row)
    assert data[0][0] == 0 and data[-1][0] >= duration * 1e-9 * (1 - 1e-12)
    assert all(a[0] < b[0] for a, b in zip(data, data[1:]))
    return [a[0] + (.9 - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
        for a, b in zip(data, data[1:]) if a[1] < .9 <= b[1]]


def frequency(events, start, end):
    selected = [t for t in events if start * 1e-9 <= t < end * 1e-9]
    assert len(selected) >= 4
    return dict(start_ns=start, end_ns=end, periods=len(selected) - 1,
        mhz=(len(selected) - 1) / (selected[-1] - selected[0]) * 1e-6)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    baseline = base / 'DCO_native_zero_wire_R_nom_tt27_c0_f247_80ns_001'
    refined = base / 'DCO_native_zero_wire_R_nom_tt27_c0_f247_25ns_numeric_002'
    original_status = json.loads((refined / 'status.json').read_text())
    runner = process(original_status['runner_pid'])
    native = process(original_status['native_pid'])
    assert runner['live'] and native['live']
    assert native['argv'][-1] == str((refined / 'point.cir').resolve())
    args.output.mkdir(exist_ok=False)
    save(args.output / 'owner.json', dict(original_owner=str(owner.resolve()), deadline_uptime=deadline,
        started_utc=datetime.now(timezone.utc).isoformat(), runner_pid=os.getpid(),
        source_runner_identity=runner, source_native_identity=native, budget_restarted=False))
    paths = [Path(__file__).resolve(), owner, baseline / 'assessment.json',
        baseline / 'input_manifest.json', refined / 'input_manifest.json']
    pins = {str(path.resolve()): digest(path) for path in paths}
    save(args.output / 'preparation_manifest.json', dict(input_sha256=pins,
        no_native_launch=True, matched_windows_ns=[[15, 20], [20, 25], [15, 25]],
        original_deadline_uptime=deadline))
    def status(state, **more):
        save(args.output / 'status.json', dict(state=state, runner_pid=os.getpid(),
            deadline_uptime=deadline, release_qualified=False, adopted=False, **more))
    proof_path = refined / 'assessment.json'
    status('waiting_for_identified_numeric_diagnostic', native=native)
    while not proof_path.exists():
        if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            status('timeout_inconclusive'); return
        now_runner, now_native = process(runner['pid']), process(native['pid'])
        valid_runner = now_runner['live'] and now_runner['argv'] == runner['argv']
        valid_native = now_native['live'] and now_native['argv'] == native['argv']
        if not valid_runner and not valid_native:
            status('source_handles_missing_no_terminal_assessment', observed_runner=now_runner,
                observed_native=now_native); return
        time.sleep(5)
    new = json.loads(proof_path.read_text())
    if new['native_exit'] != 0 or not new['completed_diagnostic_oscillation']:
        status('source_numeric_diagnostic_nonpass', native_exit=new['native_exit'],
            source_assessment_sha256=digest(proof_path)); return
    old = json.loads((baseline / 'assessment.json').read_text())
    assert old['native_exit'] == 0 and old['native_ideal_wire_reference'] and new['native_ideal_wire_reference']
    for source in [old, new]:
        for name, value in {**source['input_sha256'], **source['artifacts']}.items():
            assert digest(Path(name)) == value, name
    a, b = old['parameters'], new['parameters']
    for key in ['candidate', 'coarse', 'fine', 'corner', 'temperature', 'external_cap_ff']:
        assert a[key] == b[key], key
    # The pulse-width/period difference is outside the observed25ns prefix.
    old_deck = (baseline / 'point.cir').read_text().splitlines()
    new_deck = (refined / 'point.cir').read_text().splitlines()
    def physical(rows):
        return [row for row in rows if not row.startswith(('.tran ', '.options TIMEINT ', 'VRESET '))]
    assert physical(old_deck) == physical(new_deck)
    assert next(row for row in old_deck if row.startswith('VRESET ')).startswith('VRESET RESET_N 0 PULSE(0 1.8 5n 50p 50p ')
    assert next(row for row in new_deck if row.startswith('VRESET ')) == 'VRESET RESET_N 0 PULSE(0 1.8 5n 50p 50p 25n 50n)'
    old_edges = edges(baseline / 'point.cir.prn', 80)
    new_edges = edges(refined / 'point.cir.prn', 25)
    compared = []
    for start, end in [(15, 20), (20, 25), (15, 25)]:
        first, second = frequency(old_edges, start, end), frequency(new_edges, start, end)
        compared.append(dict(baseline=first, refined=second,
            signed_frequency_change_ppm=(second['mhz'] / first['mhz'] - 1) * 1e6))
    pins[str(proof_path.resolve())] = digest(proof_path)
    for folder in [baseline, refined]:
        path = folder / 'point.cir.prn'; pins[str(path.resolve())] = digest(path)
    assert all(digest(Path(name)) == value for name, value in pins.items())
    save(args.output / 'assessment.json', dict(matched_ideal_wire_numeric_windows_compared=True,
        comparisons=compared, common_observed_stimulus_and_physical_netlist_verified=True,
        changes=dict(maximum_step_ps=[a['max_step_ps'], b['max_step_ps']],
            reltol=[a['reltol'], b['reltol']], abstol=[a['abstol'], b['abstol']], duration_ns=[80, 25]),
        independent_one_at_a_time_convergence_qualified=False,
        physical_finite_R_calibration_or_settling_qualified=False,
        release_qualified=False, adopted=False, deadline_uptime=deadline, input_sha256=pins))
    status('completed_diagnostic_comparison', comparisons=compared)


if __name__ == '__main__': main()
