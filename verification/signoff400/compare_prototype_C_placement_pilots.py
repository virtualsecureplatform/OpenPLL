"""Measure native C-placement sensitivity; this is not an uncertainty bound."""
import argparse
import json
import math
from pathlib import Path
from common_v3 import save, sha, verify


def compare(a, b):
    for field in ('corner', 'temperature_c', 'supply_v', 'coarse_code', 'fine_code',
                  'measurement_start_s', 'measurement_end_s'):
        if a[field] != b[field]:raise ValueError('native point mismatch: '+field)
    frequencies = [float(m['average_frequency_hz']) for m in (a, b)]
    if not all(math.isfinite(f) and f > 0 for f in frequencies):
        raise ValueError('positive finite native frequencies required')
    if any(m['complete_measured_cycles'] < 3 for m in (a, b)):
        raise ValueError('at least three independently reviewed cycles required')
    return dict(driver_frequency_hz=frequencies[0], farthest_frequency_hz=frequencies[1],
        observed_frequency_difference_ppm=abs(frequencies[1]/frequencies[0]-1)*1e6,
        observed_average_period_difference_s=abs(1/frequencies[0]-1/frequencies[1]),
        observed_frequency_interval_hz=[min(frequencies), max(frequencies)],
        numerical_convergence_uncertainty_included=False,
        physical_placement_uncertainty_bound_established=False,
        parent_loading_complete=False, validated_for_prototype=False, release_ready=False)


def run(driver, farthest, output):
    points = [driver, farthest]
    paths = []
    records = []
    for point in points:
        receipt = point/'assessment.json'; cycle = point/'all_cycle_assessment/assessment.json'
        power = point/'supply_power_assessment/assessment.json'
        paths.extend((receipt, cycle, power, point/'input_manifest.json', point/'all_cycle_assessment/all_cycle_metrics.json'))
        record, cr, pr = [json.loads(p.read_text()) for p in (receipt, cycle, power)]
        for r in (record, cr, pr):verify(r['input_sha256']);verify(r.get('artifacts', {}))
        if not record['native_worker_completed'] or not cr['all_captured_measurement_cycles_assessed'] or not pr['native_two_fixed_rail_power_observed']:
            raise ValueError('completed independent native reviews required')
        manifest = json.loads((point/'input_manifest.json').read_text())
        command = manifest['command']
        if ('--tran-uic' in command) != ('--tran-uic' in json.loads((driver/'input_manifest.json').read_text())['command']):
            raise ValueError('initialization methods differ')
        netlist = Path(command[command.index('--rcx-netlist')+1])
        model_receipt = netlist.parent/'assessment.json';paths.append(model_receipt)
        model = json.loads(model_receipt.read_text());verify(model['input_sha256']);verify(model['artifacts'])
        if not model['bounded_floating_C_terminal_reduction_verified'] or not model['each_fixed_supply_dynamic_C_operator_passivity_certified']:
            raise ValueError('bounded passive model required')
        records.append(model)
    if [r['attachment'] for r in records] != ['driver', 'farthest']:
        raise ValueError('ordered distinct placement cases required')
    for field in ('candidate_gds_sha256', 'assembled_candidate_gds_sha256'):
        if records[0][field] != records[1][field]:raise ValueError('physical candidate mismatch')
    pins = {str(p):sha(p) for p in [*paths, Path(__file__).resolve()]}
    metrics = [json.loads((p/'all_cycle_assessment/all_cycle_metrics.json').read_text()) for p in points]
    result = compare(*metrics);verify(pins)
    output.mkdir(parents=True, exist_ok=False)
    save(output/'metrics.json', result)
    save(output/'assessment.json',dict(input_sha256=pins, artifacts={str(output/'metrics.json'):sha(output/'metrics.json')},
        native_placement_sensitivity_measured=True, diagnostic=True,
        uncertainty_bound_established=False, validated_for_prototype=False, release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('driver','farthest','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.driver.resolve(),a.farthest.resolve(),a.output.resolve())
