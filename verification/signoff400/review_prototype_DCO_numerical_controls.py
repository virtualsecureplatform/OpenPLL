"""Compare retained full-cycle native observations without inventing a convergence gate."""
import argparse
import json
from pathlib import Path
from common_v3 import save, sha, verify


def run(pairs, output):
    pins = {str(Path(__file__).resolve()): sha(Path(__file__).resolve())}
    results = []
    corners = set()
    for baseline, strict in pairs:
        rows = []
        manifests = []
        for point in (baseline, strict):
            receipt = point/'all_cycle_assessment/assessment.json'
            metrics = point/'all_cycle_assessment/all_cycle_metrics.json'
            manifest = point/'input_manifest.json'
            assessment = json.loads(receipt.read_text())
            verify(assessment['input_sha256']); verify(assessment['artifacts'])
            if not assessment['all_captured_measurement_cycles_assessed']:
                raise ValueError('complete native cycle review required')
            rows.append(json.loads(metrics.read_text()))
            manifests.append(json.loads(manifest.read_text()))
            for path in (receipt, metrics, manifest):
                pins[str(path)] = sha(path)
        a, b = rows
        keys = ('corner', 'coarse_code', 'fine_code', 'temperature_c', 'supply_v',
                'measurement_start_s', 'measurement_end_s')
        if any(a[key] != b[key] for key in keys):
            raise ValueError('native operating points or observation intervals differ')
        if a['corner'] in corners:
            raise ValueError('duplicate corner')
        corners.add(a['corner'])
        # Candidate and nominal RC identity must be shared; simulator commands
        # intentionally differ in output step, maximum step and tolerances.
        shared = set(manifests[0]['input_sha256']) & set(manifests[1]['input_sha256'])
        rc = [p for p in shared if p.endswith('/nom.spice')]
        gds = [p for p in shared if p.endswith('.gds')]
        if len(rc) != 1 or len(gds) != 1 or any(
                manifests[0]['input_sha256'][p] != manifests[1]['input_sha256'][p]
                for p in rc+gds):
            raise ValueError('same native RC and geometry required')
        fa, fb = a['average_frequency_hz'], b['average_frequency_hz']
        results.append(dict(corner=a['corner'], baseline=str(baseline), strict=str(strict),
            coarse_code=a['coarse_code'], fine_code=a['fine_code'],
            baseline_average_frequency_hz=fa, strict_average_frequency_hz=fb,
            frequency_shift_ppm=(fb/fa-1)*1e6,
            average_period_shift_ps=(1/fb-1/fa)*1e12,
            baseline_period_interval_s=a['observed_period_interval_s'],
            strict_period_interval_s=b['observed_period_interval_s'],
            baseline_duty_interval=a['observed_duty_interval'],
            strict_duty_interval=b['observed_duty_interval']))
    if corners != {'tt', 'ff', 'ss', 'sf', 'fs'}:
        raise ValueError('five native corners required')
    verify(pins)
    output.mkdir(parents=True, exist_ok=False)
    detail = output/'comparison.json'
    save(detail, dict(points=results))
    save(output/'assessment.json', dict(input_sha256=pins,
        artifacts={str(detail): sha(detail)}, five_corner_numerical_comparison_complete=True,
        maximum_observed_frequency_shift_ppm=max(abs(r['frequency_shift_ppm']) for r in results),
        maximum_observed_average_period_shift_ps=max(abs(r['average_period_shift_ps']) for r in results),
        observed_difference_is_certified_error_bound=False,
        numerical_convergence_qualified=False, final_parent_loading_complete=False,
        physical_models_qualified=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pair', nargs=2, type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run([(a.resolve(), b.resolve()) for a, b in args.pair], args.output.resolve())
