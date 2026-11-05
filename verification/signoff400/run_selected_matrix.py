"""Run the selected-layout diagnostic matrix with one common gain pair.

All five calibrated corner registries are required before starting. Unsupported
codes remain measurement requests; this development runner cannot qualify release.
"""
import argparse
import json
from pathlib import Path
from common_v3 import PROFILE, save, sha, source_pins, spec, verify
from selected_model_registry import validate
from run_selected_mixed_signal import run

CORNERS = ('tt', 'ff', 'ss', 'sf', 'fs')


def inventory(paths):
    models = {}
    for path in paths:
        path = path.resolve()
        value = validate(json.loads(path.read_text()))
        corner = value['analog']['operating_point']['corner']
        if corner in models:
            raise ValueError('duplicate corner registry: ' + corner)
        models[corner] = (path, value)
    return models


def execute(paths, output, ki=4, kp=0, coarse=20, seed=111, polarity=1):
    if not 1 <= ki <= 255 or not 0 <= kp <= 31:
        raise ValueError('invalid common gains')
    if not 0 <= coarse <= 47 or not 8 <= seed <= 247 or polarity not in (0, 1):
        raise ValueError('invalid common startup preset')
    profile = spec()
    if tuple(profile["corners"]) != CORNERS or profile["reference_phase_offsets_ns"] != [0, 10, 20, 30] or len(profile["scenarios"]) != 3:
        raise ValueError("matrix does not match release profile")
    models = inventory(paths)
    output.mkdir(parents=True, exist_ok=False)
    pins = source_pins()
    for path in (Path(__file__).resolve(), Path(__file__).with_name("run_selected_mixed_signal.py"),
                 Path(__file__).with_name("selected_model_registry.py"), PROFILE):
        pins[str(path)] = sha(path)
    requests = []
    for corner in CORNERS:
        if corner not in models:
            requests.append(dict(corner=corner, reason='missing_corner_registry'))
            continue
        path, model = models[corner]
        pins[str(path)] = sha(path)
        for domain in ('analog', 'interface'):
            pins.update(model[domain]['input_sha256'])
        for point in model['points']:
            pins[point['receipt']] = point['receipt_sha256']
        if not any(p['coarse'] == coarse and p['fine'] == seed for p in model['points']):
            requests.append(dict(corner=corner, coarse=coarse, fine=seed,
                                 reason='missing_measured_startup_point'))
        if 'detector_rtl' not in model['interface']:
            raise ValueError('registry interface requires detector_rtl')
        detector = str(Path(model['interface']['detector_rtl']).resolve())
        if detector not in model['interface']['input_sha256']:
            raise ValueError('detector must be pinned by interface identity')
    report = dict(state='needs_native_calibration' if requests else 'matrix_running',
                  expected_cases=60, records=[], measurement_requests=requests,
                  ki=ki, kp=kp, coarse=coarse, seed=seed, polarity=polarity,
                  input_sha256=pins, diagnostic=True,
                  functional_matrix_pass=False, physical_models_qualified=False,
                  release_ready=False)
    save(output/'assessment.json', report)
    if requests:
        verify(pins)
        return report
    for corner in CORNERS:
        path, model = models[corner]
        receipts = [Path(p['receipt']) for p in model['points']]
        detector = Path(model['interface']['detector_rtl']).resolve()
        for scenario in range(3):
            for phase in (0, 10, 20, 30):
                verify(pins)
                directory = output/f'{corner}_scenario{scenario}_phase{phase}'
                result = run(receipts, detector, directory, ki, kp, coarse, seed,
                             polarity, scenario, phase, path)
                report['records'].append(dict(corner=corner, scenario=scenario,
                    phase_offset_ns=phase, assessment=str(directory/'assessment.json'),
                    assessment_sha256=sha(directory/'assessment.json'),
                    functional_trace_pass=bool(result.get('functional_trace_pass')),
                    state=result['state']))
                for request in result.get('measurement_requests', []):
                    request = dict(request, corner=corner, reason='unsupported_tuning_code')
                    if request not in report['measurement_requests']:
                        report['measurement_requests'].append(request)
                save(output/'assessment.json', report)
                # The same incomplete curve would fail subsequent cases too.
                if report['measurement_requests']:
                    report['state'] = 'needs_native_calibration'
                    verify(pins)
                    save(output/'assessment.json', report)
                    return report
    verify(pins)
    report['functional_matrix_pass'] = (len(report['records']) == 60 and
        all(r['functional_trace_pass'] for r in report['records']))
    report['state'] = 'diagnostic_matrix_completed'
    save(output/'assessment.json', report)
    return report


def exit_status(report):
    if report['measurement_requests']:
        return 3
    return 0 if report['functional_matrix_pass'] else 1


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--registry', type=Path, action='append', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--ki', type=int, default=4)
    p.add_argument('--kp', type=int, default=0)
    p.add_argument('--coarse', type=int, default=20)
    p.add_argument('--seed', type=int, default=111)
    p.add_argument('--polarity', type=int, choices=(0, 1), default=1)
    a = p.parse_args()
    result = execute(a.registry, a.output.resolve(), a.ki, a.kp,
                     a.coarse, a.seed, a.polarity)
    print(json.dumps(result))
    raise SystemExit(exit_status(result))
