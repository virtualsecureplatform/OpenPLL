"""Review schematic range experiments without claiming physical tuning coverage."""
import argparse
import json
from pathlib import Path

from common_v3 import save, sha, verify
from review_prototype_DCO_band_coverage import bracket


def run(schematic, points, output):
    source = schematic/'assessment.json'
    definition = json.loads(source.read_text())
    if not definition.get('schematic_only') or definition.get('architecture_selected'):
        raise ValueError('unselected schematic experiment required')
    model = schematic/'schematic.spice'
    pins = {str(source): sha(source), str(model): sha(model), str(Path(__file__).resolve()): sha(Path(__file__).resolve())}
    def merge(values):
        for name, digest in values.items():
            if name in pins and pins[name] != digest:
                raise ValueError('conflicting evidence digest')
            pins[name] = digest
    merge(definition['input_sha256']); merge(definition['artifacts'])
    groups = {}
    for point in points:
        receipt, manifest, review, metrics = [point/p for p in
            ('assessment.json', 'input_manifest.json', 'all_cycle_assessment/assessment.json',
             'all_cycle_assessment/all_cycle_metrics.json')]
        a, m, r, data = [json.loads(p.read_text()) for p in (receipt, manifest, review, metrics)]
        if not a.get('schematic_only') or not a.get('native_worker_completed') or not r.get('all_captured_measurement_cycles_assessed'):
            raise ValueError('completed schematic waveform and cycle review required')
        if a['input_sha256'].get(str(source)) != sha(source) or a['input_sha256'].get(str(model)) != sha(model):
            raise ValueError('cannot combine different schematic hardware')
        command = m['command']
        if command[command.index('--rcx-netlist')+1] != str(model):
            raise ValueError('native fixture model differs')
        if (data['temperature_c'], data['supply_v']) != (27, 1.8):
            raise ValueError('prototype operating point differs')
        for name in ('corner', 'coarse_code', 'fine_code'):
            if a[name] != data[name] or m[name] != data[name]:
                raise ValueError('native operating point mismatch')
        fine = data['fine_code']
        if fine not in (8, 247):
            raise ValueError('both prototype fine endpoints required')
        group = groups.setdefault((data['corner'], data['coarse_code']), {})
        if fine in group:
            raise ValueError('duplicate native endpoint')
        group[fine] = data['observed_frequency_interval_hz']
        for record in (a, r):
            merge(record['input_sha256']); merge(record.get('artifacts', {}))
        for p in (receipt, manifest, review, metrics):
            merge({str(p): sha(p)})
    results = []
    for (corner, coarse), endpoints in sorted(groups.items()):
        if set(endpoints) != {8, 247}:
            raise ValueError('incomplete endpoint pair')
        results.append(dict(corner=corner, coarse_code=coarse, endpoints_hz=endpoints,
                            **bracket(endpoints[8], endpoints[247], 400e6)))
    if not results:
        raise ValueError('native observations required')
    verify(pins)
    output.mkdir(parents=True, exist_ok=False)
    detail = output/'bands.json'; save(detail, results)
    covered = sorted({r['corner'] for r in results if r['observed_endpoint_bracket']})
    save(output/'assessment.json', dict(input_sha256=pins, artifacts={str(detail): sha(detail)},
         schematic_source_sha256=sha(source), observed_bracketing_corners=covered,
         all_five_corners_have_observed_schematic_brackets=covered==['ff', 'fs', 'sf', 'ss', 'tt'],
         routed_interconnect_and_parent_loads_included=False,
         interior_monotonicity_or_numerical_uncertainty_qualified=False,
         physical_candidate_selected=False, analog_tuning_qualified=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schematic', type=Path, required=True)
    parser.add_argument('--point', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.schematic.resolve(), [p.resolve() for p in args.point], args.output.resolve())
