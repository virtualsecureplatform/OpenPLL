#!/usr/bin/env python3
"""Compare matched raw samples; no continuous/PVT timing bound is inferred."""
import json
from pathlib import Path
from compile_local_C_operators_v2 import digest, save


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    campaign = base / 'compact_nominal_15PVT_completion_001'
    campaign_plan = json.loads((campaign / 'plan.json').read_text())
    completed = json.loads((campaign / 'case_results.json').read_text())
    new = next(case for case in completed if case['label'] == 'sf_p125')
    inputs = {str(Path(__file__).resolve()): digest(Path(__file__)),
              str(campaign / 'plan.json'): digest(campaign / 'plan.json')}
    points = []
    for entry in [*campaign_plan['reused_completed_points'], new]:
        receipt_path = Path(entry['assessment'])
        assert digest(receipt_path) == entry['assessment_sha256']
        plan_path = Path(entry['plan'])
        plan = json.loads(plan_path.read_text())
        receipt = json.loads(receipt_path.read_text())
        assert receipt['fixtures'] == receipt['passing'] == 891
        assert receipt['all_native_waveform_events_terminal']
        assert len(receipt['records']) == len(plan['fixtures']) == 891
        for name, sha in {**receipt['input_sha256'], **receipt['artifacts']}.items():
            prior_sha = inputs.setdefault(name, sha)
            assert prior_sha == sha, name
        inputs[str(receipt_path)] = digest(receipt_path)
        inputs[str(plan_path)] = digest(plan_path)
        points.append((plan, receipt))
    assert all(plan['fixtures'] == points[0][0]['fixtures'] for plan, _ in points)
    assert points[-1][0]['pvt'] == dict(corner='sf', supply_v=1.8, temperature_c=125)
    assert len({tuple(sorted(plan['pvt'].items())) for plan, _ in points}) == 4
    # Revalidate raw artifacts and source inputs once per distinct path.
    for name, sha in inputs.items():
        assert digest(Path(name)) == sha, name
    old = points[:-1]
    fresh = points[-1]
    lower, upper, all_values = [], [], []
    for index, case in enumerate(fresh[0]['fixtures']):
        for key in ('input_rise_delay_ns', 'input_fall_delay_ns'):
            for repetition in range(2):
                before = [receipt['records'][index][key][repetition] for _, receipt in old]
                value = fresh[1]['records'][index][key][repetition]
                lo, hi = min(before), max(before)
                item = dict(case_index=index, master=case['master'], input=case['input'],
                    full_ramp_ps=case['full_ramp_ps'], external_load_pf=case['external_load_pf'],
                    measurement=key, repetition=repetition,
                    previous_sample_min_ns=lo, previous_sample_max_ns=hi,
                    SF125_delay_ns=value, extension_below_min_ps=max(0, (lo-value)*1000),
                    extension_above_max_ps=max(0, (value-hi)*1000))
                all_values.append(item)
                if value < lo:
                    lower.append(item)
                if value > hi:
                    upper.append(item)
    assert len(all_values) == 3564
    out = base / 'SF125_compact_sample_comparison_001'
    out.mkdir(exist_ok=False)
    save(out / 'completed_case_snapshot.json', new)
    save(out / 'sample_comparisons.json', all_values)
    save(out / 'assessment.json', dict(input_sha256=inputs,
        compared_PVT_points=[plan['pvt'] for plan, _ in points], matched_delay_samples=3564,
        SF125_samples_below_previous_sample_min=len(lower),
        SF125_samples_above_previous_sample_max=len(upper),
        extensions_below_min_over_1ps=sum(item['extension_below_min_ps'] > 1 for item in lower),
        extensions_above_max_over_1ps=sum(item['extension_above_max_ps'] > 1 for item in upper),
        largest_lower_extensions=sorted(lower, key=lambda item: item['extension_below_min_ps'], reverse=True)[:20],
        largest_upper_extensions=sorted(upper, key=lambda item: item['extension_above_max_ps'], reverse=True)[:20],
        strict_output_slew_passing=fresh[1]['strict_output_slew_passing'],
        strict_output_slew_ambiguous_indices=[r['case_index'] for r in fresh[1]['records'] if not r['strict_output_slew_passed']],
        one_ps_threshold_is_reporting_only=True, excluded_fixtures=0,
        native_simulations_started=0, conservative_timing_envelope_qualified=False,
        interpolation_or_numerical_uncertainty_qualified=False, release_qualified=False, adopted=False,
        scope='Matched finite-grid sample comparison only. An extension is relative to '
              'three earlier observed PVT points, not a specification violation or a '
              'qualified Liberty bound. All zero-load/ambiguous fixtures remain included.'))
    print(json.dumps(dict(samples=3564, new_lower_extrema=len(lower), new_upper_extrema=len(upper),
                         below_by_over_1ps=sum(i['extension_below_min_ps'] > 1 for i in lower),
                         above_by_over_1ps=sum(i['extension_above_max_ps'] > 1 for i in upper))))


if __name__ == '__main__':
    main()
