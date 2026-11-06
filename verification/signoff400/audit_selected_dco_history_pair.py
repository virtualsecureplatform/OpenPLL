"""Audit a same-network static/history pair and recompute age-aligned frequencies.

This isolates the combined programming/reset boundary history intervention;
it does not separate programming from reset or qualify other codes.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import re

from common_v3 import save, sha, verify
from resources import identity
from selected_spice_device_conditions import matching, reference_deck
from assess_selected_detector_prefix import read_prefix
from compare_selected_dco_startup_aligned_v5 import aligned, metrics


def sources(path):
    result = {}
    for line in path.read_text().splitlines():
        fields = line.split(maxsplit=3)
        if len(fields) != 4 or fields[0] in result or fields[2] != '0':
            raise ValueError('unique grounded boundary voltage sources required')
        result[fields[0]] = fields
    return result


def run(static, history, inventory, provenance_path, output):
    if output.exists():
        raise FileExistsError(output)
    pins = {}
    def pin(path):
        pins[str(path)] = sha(path)
    manifests = []
    for directory in (static, history):
        for name in ('manifest.json', 'status.json', 'native.process.json',
                     'devices.spice', 'sources.spice', 'control.spice', 'control.raw'):
            pin(directory/name)
        manifest = json.loads((directory/'manifest.json').read_text())
        verify(manifest['input_sha256'])
        manifests.append(manifest)
        proc = json.loads((directory/'native.process.json').read_text())
        if identity(proc['pid']) == proc['birth']:
            raise ValueError('terminal native workers required')
        status = json.loads((directory/'status.json').read_text())
        complete = status['state'] == 'real_driver_DCO_diagnostic_complete'
        budget = status['state'] == 'stopped_without_qualification' and 'TimeoutError' in status.get('reason', '')
        if not (complete or budget):
            raise ValueError('normal completion or explicit budget termination required')
    if sha(static/'devices.spice') != sha(history/'devices.spice'):
        raise ValueError('physical network differs')
    if manifests[0]['observed_roles'] != manifests[1]['observed_roles']:
        raise ValueError('physical observation nodes differ')
    # Compare actual decks; only output/include locations and declared duration differ.
    def canonical(directory, duration):
        text = (directory/'control.spice').read_text().replace(str(directory), '<RUN>')
        expected = f'.tran 10p {duration}n 0 10p'
        if text.count(expected) != 1:
            raise ValueError('unexpected transient integration settings')
        return text.replace(expected, '.tran 10p <END> 0 10p')
    if canonical(static, 60) != canonical(history, 260):
        raise ValueError('solver/model/observation deck settings differ')
    a, b = sources(static/'sources.spice'), sources(history/'sources.spice')
    if set(a) != set(b):
        raise ValueError('boundary set differs')
    inv = json.loads(inventory.read_text()); verify(inv['input_sha256']); pin(inventory)
    controls = {v['driver_input_node']: v for v in inv['controls'].values()}
    reset = manifests[0]['observed_roles']['reset_driver_input']
    changed = []
    final_error = 0.0
    for name, left in a.items():
        right = b[name]
        if left[:3] != right[:3]:
            raise ValueError('source connectivity differs')
        node = left[1]
        if left == right:
            if node in controls or node == reset:
                raise ValueError('required history source unchanged')
            continue
        if node not in controls and node != reset:
            raise ValueError('unrelated boundary changed')
        match = re.fullmatch(r'PWL FILE "([^"]+)"', right[3])
        if match is None:
            raise ValueError('explicit recorded PWL required')
        path = Path(match[1]); pin(path)
        rows = [[float(v) for v in line.split()] for line in path.read_text().splitlines()]
        if not rows or any(len(row) != 2 or not all(math.isfinite(v) for v in row) for row in rows):
            raise ValueError('invalid recorded history')
        if any(y[0] <= x[0] for x, y in zip(rows, rows[1:])):
            raise ValueError('history time is not strictly increasing')
        if node in controls:
            dc = float(left[3])
            if dc != controls[node]['driver_input_for_final_bias_V']:
                raise ValueError('static control differs from independently inventoried final bias')
            error = abs(rows[-1][1] - dc)
            if error > .01:
                raise ValueError('final programming voltage differs by more than 10 mV')
            final_error = max(final_error, error)
        changed.append(node)
    if len(controls) != 302 or set(changed) != set(controls) | {reset}:
        raise ValueError('exactly 302 programming and one reset history changes required')
    # Bind both waveforms to the same independently retained full-native reference.
    provenance = json.loads(provenance_path.read_text())
    verify(provenance['input_sha256']); verify(provenance['artifacts']); pin(provenance_path)
    reference = provenance_path.parent/'signals.csv'
    assessment = provenance_path.parent/'assessment.json'
    for path in (reference, assessment):
        if provenance['artifacts'].get(str(path)) != sha(path):
            raise ValueError('reference artifact not pinned by native provenance')
        pin(path)
    physical = reference_deck(provenance); pin(physical)
    conditions = matching(static/'control.spice', physical)
    if matching(history/'control.spice', physical) != conditions:
        raise ValueError('device conditions differ')
    for manifest in manifests:
        for path, digest in manifest['input_sha256'].items():
            if path.endswith('/Xyce') or path.endswith('/model.spice'):
                if provenance['native_input_sha256'].get(path) != digest:
                    raise ValueError('native binary or physical model differs')
    with reference.open() as stream:
        reader = csv.reader(stream); names = next(reader)
        full = [[float(v) for v in row] for row in reader]
    assessed = json.loads(assessment.read_text())
    if assessed.get('samples') != len(full) or assessed.get('end_ns') != 260:
        raise ValueError('complete assessed native reference required')
    if assessed['coarse_code']['window_codes'] != [20] or assessed['dco_code']['window_codes'] != [111]:
        raise ValueError('reference programming differs')
    r, rm = aligned(full, names.index('v(pllout)'), names.index('v(xpll:__parent_r_node_617)'))
    results = {}
    for label, directory, manifest in zip(('static', 'history'), (static, history), manifests):
        rows, info = read_prefix(directory/'control.raw', manifest['observed_roles'])
        edges, startup = aligned(rows, 1, 2)
        if min(startup['end_age_ns'], rm['end_age_ns']) < 40:
            raise ValueError('40 ns common oscillator-age coverage required')
        results[label] = dict(startup=startup, waveform=info, comparisons=metrics(edges, r, 40))
    for name in ('audit_selected_dco_history_pair.py', 'compare_selected_dco_startup_aligned_v5.py',
                 'selected_spice_device_conditions.py', 'assess_selected_detector_prefix.py',
                 'assess_selected_detector_phase_probe_v2.py', 'common_v3.py', 'resources.py'):
        pin(Path(__file__).with_name(name).resolve())
    verify(pins)
    output.mkdir(parents=True)
    result = dict(input_sha256=pins, identical_physical_network=True,
        identical_solver_settings_except_declared_horizon=True,
        identical_physical_observation_nodes=True, changed_programming_sources=302,
        changed_reset_sources=1, unrelated_boundary_sources_unchanged=True,
        maximum_final_programming_voltage_difference_v=final_error,
        device_conditions=conditions, comparisons=results,
        intervention='combined programming and reset boundary histories, with corresponding simulation horizon',
        programming_and_reset_effects_separately_isolated=False,
        other_codes_qualified=False, numerical_convergence_qualified=False,
        frequency_correlation_qualified=False, release_ready=False)
    save(output/'assessment.json', result)
    print(json.dumps({k:v['comparisons'] for k,v in results.items()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('static', 'history', 'inventory', 'provenance', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(*(getattr(args, name).resolve() for name in ('static', 'history', 'inventory', 'provenance', 'output')))
