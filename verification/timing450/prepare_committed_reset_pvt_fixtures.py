#!/usr/bin/env python3
"""Prepare corner-matched fixed diode translations without changing physical cell/route RC."""
import argparse
import hashlib
import json
from pathlib import Path
from diode_translation_probe_v2 import translated_model


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-fixture', type=Path, required=True)
    parser.add_argument('--diode-qualification', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    base = args.base_fixture.resolve()
    qualification_path = args.diode_qualification.resolve()
    receipt_path = base / 'extraction.json'
    receipt = json.loads(receipt_path.read_text())
    qualification = json.loads(qualification_path.read_text())
    assert receipt['mapped_cells'] == 98 and receipt['used_cell_types'] == 31
    assert receipt['mapped_connections_match_expanded_source'] and receipt['physical_definitions_unchanged']
    assert receipt['fixed_model_corner'] == 'ss' and receipt['fixed_model_temperature_c'] == 125
    assert qualification['model_equivalence_screen_passed'] and not qualification['pll_release_qualified']
    assert set(qualification['corners']) == {'tt', 'ff', 'ss', 'sf', 'fs'}
    assert set(qualification['temperatures_c']) == {-40, 27, 125}
    pins = {**receipt['sha256'], **qualification['evidence_sha256']}
    cache = {}
    for path, wanted in pins.items():
        cache[path] = sha(path)
        assert cache[path] == wanted, path
    circuit_path = base / 'receiver.spice'
    assert sha(circuit_path) == receipt['receiver_sha256']
    for path in (circuit_path, receipt_path, qualification_path, Path(__file__).resolve(),
                 Path(__file__).with_name('diode_translation_probe_v2.py').resolve()):
        pins[str(path)] = sha(path)
    electrical = [Path(p) for p in qualification['evidence_sha256']
                  if p.endswith('/receiver_macro_reset_diode_translation_v2/summary.json')]
    assert len(electrical) == 1
    grid = json.loads(electrical[0].read_text())
    assert grid['effective_geometry'] == {'area_um2': .6417, 'perimeter_um': 3.24}
    original = circuit_path.read_text()
    aj, pj = grid['corner_parameters']['ss']
    original_model = translated_model(125, aj, pj).replace('openpll_pw2nd_candidate', 'macro_reset_diode_fixed')
    assert original.count(original_model) == 1 and original.endswith(original_model)
    physical_prefix = original[:-len(original_model)]
    args.output.mkdir(parents=True, exist_ok=False)
    records = {}
    for corner in qualification['corners']:
        aj, pj = grid['corner_parameters'][corner]
        for temperature in qualification['temperatures_c']:
            folder = args.output / f'{corner}_{temperature}C'
            folder.mkdir()
            target = folder / 'receiver.spice'
            model = translated_model(temperature, aj, pj).replace('openpll_pw2nd_candidate', 'macro_reset_diode_fixed')
            generated = physical_prefix + model
            assert generated[:-len(model)] == physical_prefix
            target.write_text(generated)
            unchanged_base = generated == original
            assert unchanged_base == (corner == 'ss' and temperature == 125)
            result = {
                'sha256': pins,
                'receiver_sha256': sha(target),
                'mapped_cells': 98, 'used_cell_types': 31,
                'mapped_connections_match_expanded_source': True,
                'physical_definitions_unchanged_except_fixed_diode_model': True,
                'external_routed_rc_unchanged': True,
                'physical_prefix_sha256': hashlib.sha256(physical_prefix.encode()).hexdigest(),
                'fixed_model_corner': corner, 'fixed_model_temperature_c': temperature,
                'qualified_diode_geometry': grid['effective_geometry'],
                'diode_model_equivalence_screen_passed': True,
                'base_ss125_reproduced_byte_identical': unchanged_base,
                'release_qualified': False, 'selected': False,
                'limitations': ['Nominal internal cell RC and fixed routed RC; no process/temperature RC qualification',
                                'Diode translation valid only for recorded corner, temperature, geometry and tested bias envelope',
                                'Prepared fixture only; no native event/reset consumption, MTBF or whole-PLL qualification'],
            }
            assessment = folder / 'extraction.json'
            assessment.write_text(json.dumps(result, indent=2) + '\n')
            records[folder.name] = {'assessment': str(assessment.resolve()), 'assessment_sha256': sha(assessment),
                                   'receiver_sha256': result['receiver_sha256'], 'corner':corner, 'temperature_c':temperature}
    report = {'preparation_pass': True, 'prepared_corner_temperature_fixtures': len(records),
              'records': records, 'source_pins_verified':len(pins), 'sha256':pins,
              'physical_cells_and_route_rc_preserved': True, 'base_ss125_reproduced_byte_identical': True,
              'native_results_pending': True, 'release_qualified':False, 'selected':False}
    (args.output/'assessment.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('records','sha256')}))


if __name__ == '__main__':
    main()
