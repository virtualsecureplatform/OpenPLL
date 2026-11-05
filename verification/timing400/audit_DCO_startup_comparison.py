#!/usr/bin/env python3
"""Independently validate retained startup data, without qualifying calibration."""
import argparse
import json
import math
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest, save


def read_wave(path, terminal=False):
    lines = path.read_text().splitlines()
    assert lines[0].split() == ['Index', 'TIME', 'V(PLLOUT)', 'I(VVPWR)']
    marker = 'End of Xyce(TM) Simulation'
    if terminal:
        assert lines[-1] == marker
    if marker in lines:
        assert lines[-1] == marker
        lines = lines[:-1]
    rows = []
    for line in lines[1:]:
        fields = line.split()
        assert len(fields) == 4 and int(fields[0]) == len(rows)
        row = tuple(map(float, fields[1:]))
        assert all(math.isfinite(value) for value in row)
        assert row[0] >= 0 and (not rows or row[0] > rows[-1][0])
        rows.append(row)
    assert rows and rows[0][0] == 0
    edges = []
    for left, right in zip(rows, rows[1:]):
        if left[0] >= 5e-9 and left[1] < .9 <= right[1]:
            fraction = (.9 - left[1]) / (right[1] - left[1])
            assert 0 < fraction <= 1
            edges.append(left[0] + fraction * (right[0] - left[0]))
    return rows, edges


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    base = Path(__file__).resolve().parents[2] / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    baseline = base / 'DCO_native_zero_wire_R_nom_tt27_c0_f247_80ns_001'
    old_proof = json.loads((baseline / 'assessment.json').read_text())
    assert old_proof['native_exit'] == 0 and old_proof['native_ideal_wire_reference']
    assert not old_proof['physical_wire_R_present']
    for name, expected in old_proof['artifacts'].items():
        assert digest(Path(name)) == expected, name
    old_rows, old_edges = read_wave(baseline / 'point.cir.prn', terminal=True)
    assert old_rows[-1][0] >= 80e-9 * (1 - 1e-12) and len(old_edges) >= 6
    folder = base / 'DCO_ideal_wire_startup_prefix_comparison_001'
    report_path = folder / 'assessment.json'
    if not report_path.exists():
        print('Completed baseline integrity passed; startup comparison is pending. No audit pass recorded.')
        return 2
    report = json.loads(report_path.read_text())
    for name, expected in {**report['input_sha256'], **report['artifacts']}.items():
        assert digest(Path(name)) == expected, name
    rows, edges = read_wave(folder / 'retained_refined_live_prefix.prn')
    assert len(edges) >= 6 and rows[-1][0] >= edges[5]
    assert report['first_compared_edge_index'] == 2 and report['last_compared_edge_index'] == 5
    for key, values in [('baseline_six_rising_edges_s', old_edges),
                        ('refined_six_rising_edges_s', edges)]:
        assert len(report[key]) == 6
        assert all(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-22)
                   for a, b in zip(report[key], values[:6]))
    old_mhz = 3e-6 / (old_edges[5] - old_edges[2])
    new_mhz = 3e-6 / (edges[5] - edges[2])
    ppm = (new_mhz / old_mhz - 1) * 1e6
    assert len(report['edge_time_changes_s']) == 6
    assert all(math.isclose(saved, new - old, rel_tol=1e-12, abs_tol=1e-22)
               for saved, old, new in zip(report['edge_time_changes_s'], old_edges[:6], edges[:6]))
    for key, value in [('baseline_startup_frequency_mhz', old_mhz),
                       ('refined_startup_frequency_mhz', new_mhz),
                       ('signed_startup_frequency_change_ppm', ppm),
                       ('retained_prefix_last_time_s', rows[-1][0])]:
        allowance = 1e-22 if key.endswith('_s') else (1e-8 if key.endswith('_ppm') else 1e-9)
        assert math.isclose(report[key], value, rel_tol=1e-12, abs_tol=allowance), key
    assert report['live_prefix_only'] and report['deadline_uptime'] == deadline
    for key in ['full25ns_completion_verified', 'settled_calibration_criterion_applied',
                'independent_one_at_a_time_convergence_qualified',
                'physical_finite_R_frequency_or_calibration_qualified', 'release_qualified', 'adopted']:
        assert report[key] is False, key
    result = dict(startup_comparison_independently_verified=True,
        baseline_startup_frequency_mhz=old_mhz, refined_startup_frequency_mhz=new_mhz,
        signed_startup_frequency_change_ppm=ppm, retained_samples=len(rows),
        startup_diagnostic_only=True, calibration_qualified=False, release_qualified=False,
        adopted=False, deadline_uptime=deadline,
        input_sha256={str(path.resolve()): digest(path) for path in
                      [Path(__file__), owner, report_path, baseline / 'assessment.json']})
    if args.output:
        args.output.mkdir(exist_ok=False)
        save(args.output / 'assessment.json', result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
