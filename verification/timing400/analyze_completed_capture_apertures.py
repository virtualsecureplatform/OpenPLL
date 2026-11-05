#!/usr/bin/env python3
"""Derive sampled capture transitions and delay observations; qualify no limits."""
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    source = base / 'compact_capture_boundaries_fs125_001'
    plan_path = source / 'plan.json'
    receipt_path = source / 'run_001/assessment.json'
    review_path = base / 'capture_boundaries_fs125_review_001/assessment.json'
    review = json.loads(review_path.read_text())
    # Consume the already reviewed terminal receipt, rather than mutable status.
    for path in (plan_path, receipt_path):
        assert digest(path) == review['input_sha256'][str(path)]
    plan = json.loads(plan_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    assert receipt['all_native_waveform_events_terminal']
    assert receipt['observation_integrity_passing'] == receipt['fixtures'] == 198
    assert receipt['separated_controls_passing'] == 36
    assert plan['pvt'] == receipt['pvt']
    groups = defaultdict(list)
    rows = []
    for index, (case, observed) in enumerate(zip(plan['fixtures'], receipt['records'], strict=True)):
        assert observed['case_index'] == index and observed['observation_integrity_passed']
        edges = observed['post_test_50percent_edges_ns']
        # Retain signed edge offsets: an async output may move before the clock.
        offsets = {direction: [(t-case['clock_center_ns'])*1000 for t in times]
                   for direction, times in edges.items()}
        row = dict(case_index=index, master=case['master'], kind=case['kind'],
                   input_minus_clock_ps=case['offset_ps'], outcome=observed['outcome'],
                   output_edge_minus_clock_ps=offsets,
                   post_test_output_edge_count=sum(map(len, edges.values())))
        groups[(case['master'], case['kind'])].append(row)
        rows.append(row)
    assert len(groups) == 18 and all(len(items) == 11 for items in groups.values())
    summaries = []
    for (master, kind), items in sorted(groups.items()):
        items.sort(key=lambda row: row['input_minus_clock_ps'])
        brackets = []
        sampled_offsets = {row['input_minus_clock_ps'] for row in items}
        for left, right in zip(items, items[1:]):
            if left['outcome'] != right['outcome']:
                lo, hi = left['input_minus_clock_ps'], right['input_minus_clock_ps']
                proposals = [lo+(hi-lo)*fraction for fraction in (.25, .5, .75)]
                assert not sampled_offsets.intersection(proposals)
                brackets.append(dict(left_ps=lo, right_ps=hi,
                    left_outcome=left['outcome'], right_outcome=right['outcome'],
                    unsimulated_refinement_offsets_ps=proposals))
        summaries.append(dict(master=master, kind=kind,
            sampled_outcomes=[row['outcome'] for row in items],
            observed_transition_brackets=brackets,
            bracket_interior_behavior_known=False,
            monotonicity_between_samples_proven=False))
    pins = {str(p): digest(p) for p in (Path(__file__).resolve(), plan_path, receipt_path, review_path)}
    out = base / 'completed_capture_aperture_analysis_001'
    out.mkdir(exist_ok=False)
    with (out / 'observations.csv').open('x', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['master', 'kind', 'input_minus_clock_ps', 'outcome',
                         'rising_output_minus_clock_ps', 'falling_output_minus_clock_ps'])
        for row in rows:
            edges = row['output_edge_minus_clock_ps']
            writer.writerow([row['master'], row['kind'], row['input_minus_clock_ps'],
                row['outcome'], json.dumps(edges['rising']), json.dumps(edges['falling'])])
    result = dict(input_sha256=pins, pvt=plan['pvt'], fixtures=len(rows),
        full_clock_ramp_ps=200, full_changing_input_ramp_ps=200, external_load_pf=.005,
        groups=summaries, observations=rows,
        proposed_new_points=sum(len(b['unsimulated_refinement_offsets_ps'])
            for group in summaries for b in group['observed_transition_brackets']),
        native_jobs_started=0, setup_hold_recovery_removal_qualified=False,
        delay_degradation_acceptance_criterion_selected=False,
        physical_timing_qualified=False, release_qualified=False, adopted=False,
        scope='Existing FS125 sparse samples only; brackets describe observed outcome changes, '
              'not conservative timing limits or metastability bounds. Delay degradation, '
              'other ramp/load/PVT points and numerical convergence remain unqualified.')
    for path, sha in pins.items():
        assert digest(path) == sha
    (out / 'assessment.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(groups=len(summaries), proposed_new_points=result['proposed_new_points'],
                          output=str(out))))


if __name__ == '__main__':
    main()
