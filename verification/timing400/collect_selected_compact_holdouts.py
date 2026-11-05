#!/usr/bin/env python3
"""Wait for selected controls and retain all matched delay differences."""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    source = base / 'selected_compact_numerical_holdouts_sf_m40_001'
    owner = json.loads((source / 'owner.json').read_text())
    deadline = owner['deadline_uptime']
    out = base / 'selected_compact_holdout_comparison_001'
    out.mkdir(exist_ok=False)
    save(out / 'owner.json', dict(runner_pid=os.getpid(), source_runner_pid=owner['runner_pid'],
        started_utc=datetime.now(timezone.utc).isoformat(), deadline_uptime=deadline,
        native_process_started_or_retried=False))
    terminal = source / 'assessment.json'
    while not terminal.exists():
        live = process(owner['runner_pid'])
        if not live['live'] or time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            save(out / 'status.json', dict(state='source_incomplete_or_deadline',
                source_runner=live, release_qualified=False))
            return
        assert any(arg.endswith('run_selected_compact_numerical_holdouts.py') for arg in live['argv'])
        save(out / 'status.json', dict(state='waiting_for_selected_native_controls',
            source_runner_live=True, deadline_uptime=deadline, release_qualified=False))
        time.sleep(min(5, max(.01, deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    results = json.loads(terminal.read_text())['cases']
    if len(results) != 5 or not all(case.get('assessment') for case in results):
        save(out / 'assessment.json', dict(source_cases=results, selected_controls_complete=False,
            numerical_domain_enclosure_qualified=False, release_qualified=False))
        return
    pins = {str(p): digest(p) for p in (Path(__file__).resolve(), terminal, source / 'plan.json', source / 'owner.json')}
    data = {}
    for case in results:
        plan_path, receipt_path = Path(case['plan']), Path(case['assessment'])
        assert digest(plan_path) == case['plan_sha256']
        assert digest(receipt_path) == case['assessment_sha256']
        plan, receipt = json.loads(plan_path.read_text()), json.loads(receipt_path.read_text())
        assert receipt['all_native_waveform_events_terminal'] and receipt['fixtures'] == 4
        assert receipt['pvt'] == plan['pvt'] == dict(corner='sf', supply_v=1.8, temperature_c=-40)
        for path, sha in receipt['artifacts'].items():
            assert digest(Path(path)) == sha, path
            pins[path] = sha
        pins[str(plan_path)] = digest(plan_path)
        pins[str(receipt_path)] = digest(receipt_path)
        data[case['label']] = (plan, receipt)
    baseline_plan, baseline = data['subset_baseline']
    assert baseline_plan['original_case_indices'] == [87, 839, 874, 875]
    original_path = base / 'compact_nominal_15PVT_completion_001/sf_m40/run_001/assessment.json'
    original = json.loads(original_path.read_text())
    pins[str(original_path)] = digest(original_path)
    comparisons, missing = [], []

    def compare(label, left, right, left_repetition, right_repetition, case_index, measurement):
        left_values, right_values = left.get(measurement), right.get(measurement)
        if left_values is None or right_values is None:
            missing.append(dict(control=label, original_case_index=case_index, measurement=measurement))
            return
        a, b = left_values[left_repetition], right_values[right_repetition]
        assert math.isfinite(a) and math.isfinite(b)
        comparisons.append(dict(control=label, original_case_index=case_index,
            measurement=measurement, left_repetition=left_repetition,
            right_repetition=right_repetition, left_delay_ns=a, right_delay_ns=b,
            signed_difference_ps=(b-a)*1000, absolute_difference_ps=abs(b-a)*1000))

    for index, original_index in enumerate(baseline_plan['original_case_indices']):
        for measurement in ('input_rise_delay_ns', 'input_fall_delay_ns'):
            for repetition in range(2):
                compare('subset_context_vs_original_batch', original['records'][original_index],
                    baseline['records'][index], repetition, repetition, original_index, measurement)
            compare('baseline_second_vs_first', baseline['records'][index], baseline['records'][index],
                    0, 1, original_index, measurement)
            for label, (plan, receipt) in data.items():
                assert plan['fixtures'] == baseline_plan['fixtures']
                if label == 'subset_baseline':
                    continue
                for repetition in range(2):
                    compare(label, baseline['records'][index], receipt['records'][index],
                            repetition, repetition, original_index, measurement)
                if label == 'duration_only':
                    compare('duration_third_vs_second', receipt['records'][index], receipt['records'][index],
                            1, 2, original_index, measurement)
    summaries = []
    for label in sorted({row['control'] for row in comparisons}):
        selected = [row for row in comparisons if row['control'] == label]
        summaries.append(dict(control=label, matched_samples=len(selected),
            maximum_absolute_difference_ps=max(row['absolute_difference_ps'] for row in selected),
            largest_differences=sorted(selected, key=lambda row: row['absolute_difference_ps'], reverse=True)[:5]))
    for path, sha in pins.items():
        assert digest(Path(path)) == sha, path
    save(out / 'comparisons.json', comparisons)
    save(out / 'assessment.json', dict(input_sha256=pins, selected_controls_complete=True,
        summaries=summaries, missing_measurements=missing,
        source_propagation_passes={label: receipt['passing'] for label, (_, receipt) in data.items()},
        source_strict_slew_passes={label: receipt['strict_output_slew_passing'] for label, (_, receipt) in data.items()},
        all_selected_source_inputs_independently_reaudited_here=False,
        terminal_producer_input_checks_consumed=True, raw_native_artifacts_revalidated=True,
        numerical_uncertainty_acceptance_limit_selected=False,
        numerical_domain_enclosure_qualified=False, physical_timing_qualified=False,
        release_qualified=False, adopted=False,
        scope='Selected four-fixture SF-40 comparisons only. Retain individual controls, '
              'subset-context effects and repeated-opportunity drift; do not infer a '
              'bound over unmeasured slew/load/PVT or adopt a timing library.'))
    save(out / 'status.json', dict(state='completed_selected_control_comparison', release_qualified=False))


if __name__ == '__main__':
    main()
