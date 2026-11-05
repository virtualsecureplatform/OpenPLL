#!/usr/bin/env python3
"""Repeat extracted timing with an explicit additional characterized model suite."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from closure_audit import GROUPS
from run import REPO, TOOLS, run


def summarize(log):
    rows = {}
    for block in log.split('Startpoint:')[1:]:
        group = re.search(r'Path Group: ([^\n]+)', block)
        kind = re.search(r'Path Type: ([^\n]+)', block)
        value = re.search(r'(-?\d+\.\d+)\s+slack \(', block)
        if group and kind and value:
            key = kind[1] + '/' + group[1]
            rows[key] = min(rows.get(key, float(value[1])), float(value[1]))
    expected = {kind + '/' + group for kind in ('max', 'min') for group in GROUPS}
    if set(rows) != expected:
        raise RuntimeError('Incomplete extended-model timing matrix')
    if any(code in log for code in ('STA-1648', 'STA-1650', 'Error:')):
        raise RuntimeError('STA failed or SPEF names do not correspond')
    passed = all(value >= (.1 if key.startswith('max/') else .05)
                 for key, value in rows.items()) and '(VIOLATED)' not in log
    return rows, passed


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bbpd_bounds(evidence):
    if (evidence.get('single_point_pulses_observed') is not True
            or evidence.get('temperature_option_accepted') is not True
            or evidence.get('analysis_window_ns') != [5, 85]):
        raise RuntimeError('Missing accepted BBPD pulse measurements')
    waves = evidence.get('output_waveforms', {})
    if set(waves) != {'BBPD[0]', 'BBPD[1]'}:
        raise RuntimeError('Incomplete BBPD interfaces')
    values = {}
    for key in ('rising_slew_20_80_ns', 'falling_slew_80_20_ns', 'high_pulse_widths_ns'):
        samples = []
        for wave in waves.values():
            row = wave.get(key, [])
            if (wave.get('complete_two_pulses') is not True or len(row) != 2
                    or any(not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in row)):
                raise RuntimeError('Incomplete or invalid BBPD waveform measurements')
            samples.extend(row)
        values[key] = samples
    step = .025
    rise = math.ceil((max(values['rising_slew_20_80_ns']) + step) / step) * step
    fall = math.ceil((max(values['falling_slew_80_20_ns']) + step) / step) * step
    high = math.floor((min(values['high_pulse_widths_ns']) - step) / step) * step
    if high <= 0:
        raise RuntimeError('Measured BBPD pulse leaves no positive high-time bound')
    return {'rise_ns': round(rise, 9), 'fall_ns': round(fall, 9),
            'high_ns': round(high, 9), 'guard_ns': step,
            'scope': 'Conservative bounds from one loaded SS/1.62 V/125 C/50 ps point; not full PVT/phase qualification'}


def bbpd_pvt_bounds(points):
    expected = {(c, v, t) for c in ('ss', 'tt', 'ff', 'sf', 'fs')
                for v in (1.62, 1.8, 1.95) for t in (-40, 27, 125)}
    observed, bounds = set(), []
    for point in points:
        key = (point.get('corner'), point.get('supply_v'), point.get('temperature_c'))
        if (key not in expected or key in observed
                or point.get('phase_ps') != 50 or point.get('edge_ps') != 20
                or point.get('simulation_completed') is not True or point.get('exit_code') != 0
                or point.get('two_full_pulses_observed') is not True):
            raise RuntimeError('Incomplete, duplicate or unsupported BBPD PVT point')
        observed.add(key)
        bounds.append(bbpd_bounds({'single_point_pulses_observed': True,
                                  'temperature_option_accepted': True,
                                  'analysis_window_ns': [5, 85],
                                  'output_waveforms': point.get('output_waveforms')}))
    if observed != expected:
        raise RuntimeError('Missing required BBPD PVT points')
    return {'rise_ns': max(b['rise_ns'] for b in bounds),
            'fall_ns': max(b['fall_ns'] for b in bounds),
            'high_ns': min(b['high_ns'] for b in bounds), 'guard_ns': .025,
            'scope': '45 loaded PVT points at 50 ps phase offset/20 ps input edges; reduced fixed-rail MOS; phase/slew and nonlinear receiver qualification remain open'}


def bounded_constraints(text, bounds):
    text, count = re.subn(
        r'(create_clock -name EVENT_\$name -period 40 -waveform )\{0 [\d.]+\}( \$port)',
        lambda m: m[1] + '{0 ' + str(bounds['high_ns']) + '}' + m[2], text)
    if count != 1:
        raise RuntimeError('Unexpected BBPD pulse-clock definition')
    text += '\n# Measured loaded BBPD point; input and propagated-clock source slew.\n'
    text += 'if {[llength $bbpd_ports] != 2} {error "incomplete measured BBPD ports"}\n'
    for direction, key in [('rise', 'rise_ns'), ('fall', 'fall_ns')]:
        text += f'set_input_transition -{direction} {bounds[key]} $bbpd_ports\n'
        text += 'foreach port $bbpd_ports {\n'
        text += '    set name [get_full_name $port]\n'
        text += f'    set_clock_transition -{direction} {bounds[key]} [get_clocks EVENT_$name]\n}}\n'
    return text


def verify_bbpd_slews(log, bounds):
    found = set()
    for line in log.splitlines():
        row = line.split()
        if (len(row) == 8 and row[-2] in ('BBPD[0]', 'BBPD[1]')
                and row[-1] == '(in)' and row[-3] in ('^', 'v')):
            value = float(row[2])
            expected = bounds['rise_ns' if row[-3] == '^' else 'fall_ns']
            if not math.isfinite(value) or not math.isclose(value, expected, abs_tol=1e-6):
                raise RuntimeError('Measured BBPD source slew was not applied')
            found.add((row[-2], row[-3]))
    if found != {(port, edge) for port in ('BBPD[0]', 'BBPD[1]') for edge in ('^', 'v')}:
        raise RuntimeError('Missing measured BBPD source slew evidence')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--model-suite', type=Path, required=True)
    parser.add_argument('--mode-mhz', type=int, choices=[100, 250, 300, 400, 450], default=450)
    parser.add_argument('--output', type=Path, required=True)
    bbpd = parser.add_mutually_exclusive_group()
    bbpd.add_argument('--bbpd-characterization', type=Path,
                        help='Pinned completed loaded BBPD point; apply conservative pulse/slew bounds')
    bbpd.add_argument('--bbpd-pvt-characterization', type=Path,
                      help='Pinned 45-point loaded BBPD matrix at 50 ps phase/20 ps input edge')
    args = parser.parse_args()
    root = args.candidate.resolve()
    baseline = root / f'reports_{args.mode_mhz}'
    assessment = json.loads((baseline / 'assessment.json').read_text())
    baseline_inputs = []
    for name, digest in assessment['sha256'].items():
        path = Path(name)
        if not path.is_absolute():
            path = root.parents[2] / path
        if sha(path) != digest:
            raise RuntimeError(f'Stale baseline evidence: {path}')
        baseline_inputs.append(path)
    for name, digest in assessment['model_sha256'].items():
        if sha(Path(name)) != digest:
            raise RuntimeError(f'Stale baseline library: {name}')
        baseline_inputs.append(Path(name))
    suite = json.loads(args.model_suite.read_text())
    if set(suite) != {'ss', 'tt', 'ff'}:
        raise RuntimeError('Additional suite must explicitly name ss, tt and ff')
    models = {name: Path(path).resolve() for name, path in suite.items()}
    metadata = {}
    bounds, characterization_inputs = None, []
    if args.bbpd_characterization:
        evidence_path = args.bbpd_characterization.resolve()
        evidence = json.loads(evidence_path.read_text())
        bounds = bbpd_bounds(evidence)
        manifest = evidence_path.parent / 'input_manifest.json'
        if sha(manifest) != evidence['input_manifest_sha256']:
            raise RuntimeError('Stale BBPD input manifest')
        evidence_hashes = {**evidence['artifact_sha256'],
                           **json.loads(manifest.read_text())['sha256']}
        for name, digest in evidence_hashes.items():
            if sha(Path(name)) != digest:
                raise RuntimeError(f'Stale BBPD characterization: {name}')
        characterization_inputs = [evidence_path, manifest, *map(Path, evidence_hashes)]
    if args.bbpd_pvt_characterization:
        evidence_path = args.bbpd_pvt_characterization.resolve()
        evidence = json.loads(evidence_path.read_text())
        if (evidence.get('requested_points') != 45 or evidence.get('completed_points') != 45
                or evidence.get('all_simulations_completed') is not True
                or evidence.get('all_two_full_pulses_observed') is not True
                or len(evidence.get('receipts', {})) != 45):
            raise RuntimeError('Missing complete BBPD PVT characterization')
        manifest = evidence_path.parent / 'input_manifest.json'
        if sha(manifest) != evidence['input_manifest_sha256']:
            raise RuntimeError('Stale BBPD PVT input manifest')
        evidence_hashes = {**json.loads(manifest.read_text())['sha256'], **evidence['receipts']}
        points = []
        for name in evidence['receipts']:
            point = json.loads(Path(name).read_text())
            points.append(point)
            evidence_hashes.update(point['sha256'])
        for name, digest in evidence_hashes.items():
            if sha(Path(name)) != digest:
                raise RuntimeError(f'Stale BBPD PVT characterization: {name}')
        bounds = bbpd_pvt_bounds(points)
        characterization_inputs = [evidence_path, manifest, *map(Path, evidence_hashes)]
    for name, path in models.items():
        text = path.read_text()
        library = re.search(r'library\s*\(\s*"?([^\s"()]+)', text)
        voltage = re.search(r'\bnom_voltage\s*:\s*([\d.]+)', text)
        temperature = re.search(r'\bnom_temperature\s*:\s*(-?[\d.]+)', text)
        if not library or f'__{name}_' not in library[1] or not voltage or not temperature:
            raise RuntimeError(f'Missing or conflicting characterized model metadata: {path}')
        if float(voltage[1]) > 1.95:
            raise RuntimeError('Model exceeds the approved supply ceiling')
        metadata[name] = {'voltage_v': float(voltage[1]), 'temperature_c': float(temperature[1]),
                          'library': library[1], 'path': str(path)}
        if bounds:
            for direction in ('rise', 'fall'):
                for level, expected in [('lower', 20), ('upper', 80)]:
                    value = re.search(r'slew_' + level + '_threshold_pct_' + direction + r'\s*:\s*([\d.]+)', text)
                    if not value or float(value[1]) != expected:
                        raise RuntimeError('BBPD measurement and library slew thresholds differ')
            if not re.search(r'time_unit\s*:\s*"1ns"', text):
                raise RuntimeError('BBPD measurement requires library time units of ns')
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'assessment.json').unlink(missing_ok=True)
    inputs = [args.model_suite.resolve(), baseline / 'assessment.json', Path(__file__),
              Path(__file__).with_name('closure_audit.py'), Path(__file__).with_name('run.py'),
              root / 'route.odb', root / 'route.v', *root.glob('route.*.normalized.spef'),
              *models.values()]
    inputs.extend(characterization_inputs)
    inputs.extend([*baseline_inputs, *baseline.glob('*_timing.tcl'), Path(TOOLS['openroad'])])
    measured_constraints = None
    if bounds:
        original_constraints = baseline / 'constraints.tcl'
        measured_constraints = args.output.resolve() / 'bbpd_constraints.tcl'
        measured_constraints.write_text(bounded_constraints(original_constraints.read_text(), bounds))
        inputs += [original_constraints, measured_constraints]
    initial = {str(path): sha(path) for path in inputs}
    result = {'release_qualified': False, 'selected': False, 'mode_mhz': args.mode_mhz,
              'models': metadata, 'timing_ns': {}, 'gates': {}, 'electrical_violated_rows': {},
              'limitations': ['Additional characterized points do not replace the required exact PVT grid',
                              'Interface/CDC/pulse assumptions retain their diagnostic scope']}
    if bounds:
        result['bbpd_measured_point_bounds'] = bounds
    for name, model in models.items():
        result['timing_ns'][name] = {}
        for rc in ('min', 'nom', 'max'):
            source = baseline / f'{name}_{rc}_timing.tcl'
            script = source.read_text()
            original = assessment['models'][name]
            if script.count(original) != 1:
                raise RuntimeError('Unexpected baseline model loading recipe')
            recipe = args.output / f'{name}_{rc}_timing.tcl'
            script = script.replace(original, str(model))
            if bounds:
                source_constraints = str(baseline / 'constraints.tcl')
                if script.count('source ' + source_constraints + '\n') != 1:
                    raise RuntimeError('Unexpected baseline constraint loading recipe')
                script = script.replace('source ' + source_constraints + '\n',
                                        'source ' + str(measured_constraints) + '\n')
            recipe.write_text(script)
            log = recipe.with_suffix('.log')
            run('openroad', ['-exit', recipe], log)
            rows, passed = summarize(log.read_text())
            if bounds:
                verify_bbpd_slews(log.read_text(), bounds)
            result['timing_ns'][name][rc] = rows
            result['gates'][name + '/' + rc] = passed
            result['electrical_violated_rows'][name + '/' + rc] = log.read_text().count('(VIOLATED)')
            inputs.extend([source, recipe, log])
    for path, digest in initial.items():
        if sha(Path(path)) != digest:
            raise RuntimeError(f'Input changed during additional characterization: {path}')
    result['diagnostic_timing_pass'] = all(result['gates'].values())
    result['sha256'] = {str(path): sha(path) for path in inputs}
    (args.output / 'assessment.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'diagnostic_timing_pass': result['diagnostic_timing_pass'],
                      'gates': result['gates'], 'electrical_violated_rows': result['electrical_violated_rows']}))
    return 0 if result['diagnostic_timing_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
