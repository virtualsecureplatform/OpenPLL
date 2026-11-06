"""Run the selected-layout diagnostic matrix with one common gain pair.

All five calibrated corner registries are required before starting. Unsupported
codes remain measurement requests; this development runner cannot qualify release.
"""
import argparse
import json
from pathlib import Path
from common_v3 import PROFILE, save, sha, spec, verify
from selected_physical_rtl import source_pins
from selected_model_registry import validate
from run_selected_mixed_signal_v4 import run

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


def startup_presets(path, coarse, seed, polarity):
    if path is None:
        values = {corner: dict(coarse=coarse, seed=seed, polarity=polarity) for corner in CORNERS}
    else:
        values = json.loads(path.read_text())
        if not isinstance(values, dict) or set(values) != set(CORNERS):
            raise ValueError('explicit presets must cover exactly five corners')
    for corner, value in values.items():
        if not isinstance(value, dict) or set(value) != {'coarse', 'seed', 'polarity'}:
            raise ValueError('coarse, seed and polarity required for ' + corner)
        if any(type(v) is not int for v in value.values()) or not 0 <= value['coarse'] <= 47 or not 8 <= value['seed'] <= 247 or value['polarity'] not in (0, 1):
            raise ValueError('invalid startup preset for ' + corner)
    return values


def execute(paths, output, ki=4, kp=0, coarse=20, seed=111, polarity=1, presets_path=None):
    if not 1 <= ki <= 255 or not 0 <= kp <= 31:
        raise ValueError('invalid common gains')
    preset_digest = sha(presets_path) if presets_path is not None else None
    presets = startup_presets(presets_path, coarse, seed, polarity)
    profile = spec()
    if tuple(profile["corners"]) != CORNERS or profile["reference_phase_offsets_ns"] != [0, 10, 20, 30] or len(profile["scenarios"]) != 3:
        raise ValueError("matrix does not match release profile")
    models = inventory(paths)
    output.mkdir(parents=True, exist_ok=False)
    pins = source_pins()
    for path in (Path(__file__).resolve(), Path(__file__).with_name("run_selected_mixed_signal_v4.py"),
                 Path(__file__).with_name("selected_model_registry.py"), Path(__file__).with_name("selected_clock_timing.py"), PROFILE):
        pins[str(path)] = sha(path)
    if presets_path is not None:
        pins[str(presets_path.resolve())] = preset_digest
    requests = []
    for corner in CORNERS:
        if corner not in models:
            requests.append(dict(corner=corner, reason='missing_corner_registry'))
            continue
        path, model = models[corner]
        preset = presets[corner]
        pins[str(path)] = sha(path)
        for domain in ('analog', 'interface'):
            pins.update(model[domain]['input_sha256'])
        for point in model['points']:
            pins[point['receipt']] = point['receipt_sha256']
        if not any(p['coarse'] == preset['coarse'] and p['fine'] == preset['seed'] for p in model['points']):
            requests.append(dict(corner=corner, coarse=preset['coarse'], fine=preset['seed'],
                                 reason='missing_measured_startup_point'))
        if 'detector_rtl' not in model['interface']:
            raise ValueError('registry interface requires detector_rtl')
        detector = str(Path(model['interface']['detector_rtl']).resolve())
        if detector not in model['interface']['input_sha256']:
            raise ValueError('detector must be pinned by interface identity')
        if not isinstance(model['interface'].get('clock_timing'),str):raise ValueError('explicit clock timing required for '+corner)
        clock_path=Path(model['interface']['clock_timing']).resolve()
        if model['interface']['input_sha256'].get(str(clock_path))!=sha(clock_path):raise ValueError('clock timing must be pinned by interface identity')
        from selected_clock_timing import load
        load(clock_path,model)
    report = dict(state='needs_native_calibration' if requests else 'matrix_running',
                  expected_cases=60, records=[], measurement_requests=requests,
                  ki=ki, kp=kp, startup_defaults=dict(coarse=coarse, seed=seed, polarity=polarity),
                  startup_presets=presets, input_sha256=pins, diagnostic=True,
                  functional_matrix_pass=False, physical_models_qualified=False,
                  release_ready=False)
    save(output/'assessment.json', report)
    if requests:
        verify(pins)
        return report
    for corner in CORNERS:
        path, model = models[corner]
        preset = presets[corner]
        receipts = [Path(p['receipt']) for p in model['points']]
        detector = Path(model['interface']['detector_rtl']).resolve()
        for scenario in range(3):
            for phase in (0, 10, 20, 30):
                verify(pins)
                directory = output/f'{corner}_scenario{scenario}_phase{phase}'
                result = run(receipts, detector, directory, ki, kp, preset['coarse'], preset['seed'],
                             preset['polarity'], scenario, phase, path, Path(model['interface']['clock_timing']).resolve())
                report['records'].append(dict(corner=corner, scenario=scenario, startup_preset=preset,
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
    p.add_argument('--presets', type=Path, help='JSON mapping each corner to coarse, seed and polarity; scalar options are defaults when omitted')
    a = p.parse_args()
    result = execute(a.registry, a.output.resolve(), a.ki, a.kp,
                     a.coarse, a.seed, a.polarity, a.presets.resolve() if a.presets else None)
    print(json.dumps(result))
    raise SystemExit(exit_status(result))
