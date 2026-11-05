#!/usr/bin/env python3
"""Audit a controlled partial trace; establish no settled frequency/model bound."""
import json
import math
from pathlib import Path
import re
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    point = base / 'DCO_domain_nom_tt27_c0_f247_80ns_wire_preconditioned_gear_002'
    handoff_path = base / 'DCO_Gear_to_bounded_reuse_handoff_001/handoff.json'
    handoff = json.loads(handoff_path.read_text())
    receipt_path = point / 'assessment.json'
    assert digest(receipt_path) == handoff['prior_assessment_sha256']
    assert not process(handoff['source_native_pid'])['live']
    assert not process(handoff['source_runner_pid'])['live']
    receipt = json.loads(receipt_path.read_text())
    assert receipt['native_exit'] == -15 and not receipt.get('timed_out', False)
    assert not receipt['completed_full_native_transient']
    for path, sha in receipt['artifacts'].items():
        assert digest(Path(path)) == sha, path
    wave = point / 'point.cir.prn'
    rows = []
    text = wave.read_text()
    assert text.endswith('\n') and 'End of Xyce(TM) Simulation' not in text
    lines = text.splitlines()
    assert lines[0].split() == ['Index', 'TIME', 'V(PLLOUT)', 'I(VVPWR)']
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = line.split()
        assert len(fields) == 4 and int(fields[0]) == len(rows)
        row = tuple(map(float, fields[1:]))
        assert all(math.isfinite(value) for value in row)
        assert not rows or row[0] > rows[-1][0]
        rows.append(row)
    assert len(rows) == receipt['samples'] and rows[0][0] == 0
    assert rows[-1][0] == receipt['simulation_time_s'] < 20e-9
    solves = []
    for line in (point / 'native.log').read_text().splitlines():
        match = re.fullmatch(r'OpenPLL_wire_PC call=(\d+) alpha=(\S+) iterations=(\d+) scaled_true_relative_residual=(\S+) seconds=(\S+) status=(\d+)', line)
        if match:
            call, residual, code = int(match[1]), float(match[4]), int(match[6])
            assert call == len(solves)+1 and math.isfinite(residual) and residual <= 1e-12 and code == 0
            solves.append(residual)
    assert len(solves) == receipt['adapter_linear_solves']
    edges = {'rise': [], 'fall': []}
    for left, right in zip(rows, rows[1:]):
        direction = 'rise' if left[1] < .9 <= right[1] else 'fall' if left[1] > .9 >= right[1] else None
        if direction:
            crossing = left[0]+(.9-left[1])*(right[0]-left[0])/(right[1]-left[1])
            if crossing >= 5.05e-9:
                edges[direction].append(crossing)
    assert len(edges['rise']) >= 4 and len(edges['fall']) >= 4
    prepared = base / 'DCO_bounded_reuse_trial_prepared_001/point.cir'
    original = (point / 'point.cir').read_text()
    assert original == prepared.read_text()
    paths = [Path(__file__).resolve(), handoff_path, receipt_path, wave, point / 'native.log',
             point / 'point.cir', base / 'pending_Gear_DCO_monitor_001/first_step_comparison.json', prepared]
    out = base / 'retained_Gear_before_bounded_reuse_audit_001'
    out.mkdir(exist_ok=False)
    save(out / 'assessment.json', dict(input_sha256={str(p): digest(p) for p in paths},
        controlled_interruption_verified=True, source_native_and_owner_terminal=True,
        samples=len(rows), last_accepted_time_s=rows[-1][0],
        reported_linear_solve_residuals_checked=len(solves), maximum_reported_residual=max(solves),
        independent_Jacobian_residual_recomputed_for_all_steps=False,
        post_reset_edges_s=edges,
        first_rising_interval_ns=(edges['rise'][1]-edges['rise'][0])*1e9,
        first_falling_interval_ns=(edges['fall'][1]-edges['fall'][0])*1e9,
        configured_measurement_window_reached=False, settled_frequency_qualified=False,
        new_trial_deck_byte_identical=True,
        physical_oscillation_failure_inferred=False, native_simulation_started_or_retried=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    print(json.dumps(dict(samples=len(rows), logged_linear_solves=len(solves),
                          post_reset_rises=len(edges['rise']), post_reset_falls=len(edges['fall']))))


if __name__ == '__main__':
    main()
