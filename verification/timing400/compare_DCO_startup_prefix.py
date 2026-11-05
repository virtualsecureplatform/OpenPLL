#!/usr/bin/env python3
"""Retain an early-cycle numerical comparison without claiming full completion."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process


def parse(text):
    if not text.endswith('\n'): text = text[:text.rfind('\n') + 1]
    lines = text.splitlines()
    assert lines[0].split() == ['Index', 'TIME', 'V(PLLOUT)', 'I(VVPWR)']
    rows = []
    for line in lines[1:]:
        if line == 'End of Xyce(TM) Simulation': break
        fields = line.split()
        assert len(fields) == 4 and int(fields[0]) == len(rows)
        rows.append(tuple(float(value) for value in fields[1:]))
    edges = [a[0] + (.9 - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
        for a, b in zip(rows, rows[1:]) if a[1] < .9 <= b[1] and a[0] >= 5e-9]
    return text, rows, edges


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    baseline = base / 'DCO_native_zero_wire_R_nom_tt27_c0_f247_80ns_001'
    refined = base / 'DCO_native_zero_wire_R_nom_tt27_c0_f247_25ns_numeric_002'
    out = base / 'DCO_ideal_wire_startup_prefix_comparison_001'; out.mkdir(exist_ok=False)
    initial = json.loads((refined / 'status.json').read_text())
    native = process(initial['native_pid']); assert native['live']
    runner = process(initial['runner_pid']); assert runner['live']
    save(out / 'owner.json', dict(runner_pid=os.getpid(), source_native=native, source_runner=runner,
        original_owner=str(owner.resolve()), deadline_uptime=deadline, budget_restarted=False))
    def status(state, **extra):
        save(out / 'status.json', dict(state=state, runner_pid=os.getpid(), deadline_uptime=deadline,
            release_qualified=False, adopted=False, **extra))
    old_proof = json.loads((baseline / 'assessment.json').read_text())
    assert old_proof['native_exit'] == 0 and old_proof['native_ideal_wire_reference']
    old_manifest = json.loads((baseline / 'input_manifest.json').read_text())
    new_manifest = json.loads((refined / 'input_manifest.json').read_text())
    shared = old_manifest['input_sha256'].keys() & new_manifest['input_sha256'].keys()
    for name in shared:
        assert old_manifest['input_sha256'][name] == new_manifest['input_sha256'][name]
        assert digest(Path(name)) == old_manifest['input_sha256'][name], name
    for key in ['candidate', 'coarse', 'fine', 'corner', 'temperature', 'external_cap_ff']:
        assert old_manifest['parameters'][key] == new_manifest['parameters'][key]
    def fixed_cards(folder):
        return [line for line in (folder / 'point.cir').read_text().splitlines()
                if not line.startswith(('.tran ', '.options TIMEINT ', 'VRESET '))]
    assert fixed_cards(baseline) == fixed_cards(refined)
    assert 'PULSE(0 1.8 5n 50p 50p 80n 160n)' in (baseline / 'point.cir').read_text()
    assert 'PULSE(0 1.8 5n 50p 50p 25n 50n)' in (refined / 'point.cir').read_text()
    old_wave = baseline / 'point.cir.prn'
    _, _, old_edges = parse(old_wave.read_text()); assert len(old_edges) >= 6
    status('waiting_for_six_post_reset_rising_edges')
    while True:
        if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            status('timeout_inconclusive'); return
        content, rows, new_edges = parse((refined / 'point.cir.prn').read_text())
        if len(new_edges) >= 6: break
        current_native, current_runner = process(native['pid']), process(runner['pid'])
        native_live = current_native['live'] and current_native['argv'] == native['argv']
        runner_live = current_runner['live'] and current_runner['argv'] == runner['argv']
        if not native_live and not runner_live:
            status('source_ended_before_required_startup_edges', rising_edges=len(new_edges)); return
        time.sleep(30)
    prefix = out / 'retained_refined_live_prefix.prn'; prefix.write_text(content)
    first, second = old_edges[:6], new_edges[:6]
    # Compare the same cycle indices, so startup drift is not confounded by
    # selecting a different number of periods at an absolute window boundary.
    old_mhz = 3 / (first[5] - first[2]) * 1e-6
    new_mhz = 3 / (second[5] - second[2]) * 1e-6
    paths = [Path(__file__).resolve(), owner, baseline / 'assessment.json', old_wave,
        baseline / 'input_manifest.json', refined / 'input_manifest.json',
        baseline / 'point.cir', refined / 'point.cir']
    save(out / 'assessment.json', dict(startup_cycle_prefix_compared=True,
        observed_utc=datetime.now(timezone.utc).isoformat(), baseline_six_rising_edges_s=first,
        refined_six_rising_edges_s=second, first_compared_edge_index=2, last_compared_edge_index=5,
        baseline_startup_frequency_mhz=old_mhz, refined_startup_frequency_mhz=new_mhz,
        signed_startup_frequency_change_ppm=(new_mhz / old_mhz - 1) * 1e6,
        edge_time_changes_s=[b - a for a, b in zip(first, second)],
        retained_prefix_last_time_s=rows[-1][0], live_prefix_only=True,
        full25ns_completion_verified=False, settled_calibration_criterion_applied=False,
        independent_one_at_a_time_convergence_qualified=False,
        physical_finite_R_frequency_or_calibration_qualified=False,
        release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256={str(path.resolve()): digest(path) for path in paths},
        artifacts={str(prefix.resolve()): digest(prefix)}))
    status('completed_startup_prefix_diagnostic_full_run_qualification_pending')


if __name__ == '__main__': main()
