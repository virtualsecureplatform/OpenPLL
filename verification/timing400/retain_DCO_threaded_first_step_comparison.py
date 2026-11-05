#!/usr/bin/env python3
"""Retain and compare the first common full-R serial/threaded accepted steps."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process


def read_prefix(path):
    text = path.read_text()
    if not text.endswith('\n'): text = text[:text.rfind('\n') + 1]
    lines = text.splitlines()
    assert lines[0].split() == ['Index', 'TIME', 'V(PLLOUT)', 'I(VVPWR)']
    rows = []
    retained = [lines[0]]
    for line in lines[1:]:
        if not line.strip(): continue
        fields = line.split()
        assert len(fields) == 4 and int(fields[0]) == len(rows)
        row = tuple(map(float, fields[1:]))
        assert all(math.isfinite(value) for value in row)
        assert not rows or row[0] > rows[-1][0]
        rows.append(row); retained.append(line)
        if len(rows) == 2: break
    assert len(rows) == 2 and rows[0][0] == 0
    assert math.isclose(rows[1][0], 10e-12, rel_tol=1e-12, abs_tol=1e-25)
    return '\n'.join(retained) + '\n', rows


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    old = base / 'DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_002'
    new = base / 'DCO_domain_nom_tt27_c0_f247_80ns_stock_threaded_002'
    receipt = old / 'stopped_for_controlled_stock_threaded_solver_comparison.json'
    assert not process(json.loads(receipt.read_text())['pid'])['live']
    state = json.loads((new / 'status.json').read_text())
    native = process(state['native_pid'])
    assert native['live'] and native['argv'][-1] == str((new / 'point.cir').resolve())
    old_option = '.options LINSOL TYPE=KLU TR_PARTITION=0 TR_AMD=0 KLU_REPIVOT=0'
    new_option = '.options LINSOL TYPE=SHYLU_BASKER TR_PARTITION=0 TR_AMD=0'
    old_deck = (old / 'point.cir').read_text()
    assert old_deck.count(old_option) == 1
    assert old_deck.replace(old_option, new_option) == (new / 'point.cir').read_text()
    old_text, first = read_prefix(old / 'point.cir.prn')
    new_text, second = read_prefix(new / 'point.cir.prn')
    assert [row[0] for row in first] == [row[0] for row in second]
    dv = max(abs(a[1] - b[1]) for a, b in zip(first, second))
    di = max(abs(a[2] - b[2]) for a, b in zip(first, second))
    out = base / 'DCO_stock_threaded_first_step_comparison_001'; out.mkdir(exist_ok=False)
    left = out / 'retained_serial_prefix.prn'; left.write_text(old_text)
    right = out / 'retained_threaded_prefix.prn'; right.write_text(new_text)
    paths = [Path(__file__), owner, receipt, old / 'input_manifest.json', new / 'input_manifest.json',
             old / 'point.cir', new / 'point.cir',
             base / 'stock_threaded_active_wait_controls_001/assessment.json']
    result = dict(first_common_positive_time_step_compared=True,
        observed_utc=datetime.now(timezone.utc).isoformat(), source_native_identity=native,
        samples_compared=2, last_compared_time_s=first[-1][0],
        maximum_sampled_voltage_difference_V=dv, maximum_sampled_supply_current_difference_A=di,
        physical_deck_identical_except_solver_option=True, retained_live_prefix_only=True,
        full_native_completion_verified=False, full_DCO_performance_improvement_demonstrated=False,
        frequency_or_calibration_qualified=False, release_qualified=False, adopted=False,
        deadline_uptime=deadline, input_sha256={str(path.resolve()): digest(path) for path in paths},
        artifacts={str(path.resolve()): digest(path) for path in [left, right]})
    save(out / 'assessment.json', result)
    print(json.dumps({key: value for key, value in result.items()
                      if key not in ['input_sha256', 'artifacts', 'source_native_identity']}, indent=2))


if __name__ == '__main__':
    main()
