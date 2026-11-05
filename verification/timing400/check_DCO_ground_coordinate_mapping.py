#!/usr/bin/env python3
"""Audit the full DCO boundary substitution independently of its generator."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import re
import time
from compile_local_C_operators_v2 import digest, save


def statements(path):
    result = []
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('*'):
            continue
        if line.startswith('+'):
            result[-1].extend(line[1:].split())
        else:
            result.append(line.split())
    return result


def bias(path):
    result = {}
    for line in path.read_text().splitlines():
        match = re.fullmatch(r'\s*\.IC\s+V\(([^)]+)\)\s*=\s*([-+.eE0-9]+)\s*', line, re.I)
        assert match, line
        name = match[1].upper()
        assert name not in result
        result[name] = Decimal(match[2])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    prior = base / 'DCO_domain_nom_tt27_c0_f247_80ns_savedIC_001'
    current = base / 'DCO_domain_nom_tt27_c0_f247_80ns_canonical_ground_001'
    manifest = json.loads((current / 'input_manifest.json').read_text())
    pins = manifest['input_sha256'].copy()
    for name, value in pins.items():
        assert digest(Path(name)) == value, name
    old, new = statements(prior / 'point.cir'), statements(current / 'point.cir')
    # Derive grounded nodes from the original electrical constraints, without
    # importing the transformation helper or trusting its mapping receipt.
    sources = [row for row in old if row[0].upper().startswith('V')]
    removed = {}
    for row in sources:
        if len(row) == 4 and row[2] == '0' and Decimal(row[3]) == 0:
            assert row[1].upper() not in removed
            removed[row[1].upper()] = row[0]
    assert len(removed) == 296
    new_sources = {row[0]: row for row in new if row[0].upper().startswith('V')}
    assert len(sources) == 307 and len(new_sources) == 11
    for row in sources:
        if row[0] not in removed.values():
            assert new_sources[row[0]] == row
    assert new_sources['VVPWR'] == ['VVPWR', 'VPWR', '0', '1.8']
    old_x = [row for row in old if row[0].upper().startswith('X')]
    new_x = [row for row in new if row[0].upper().startswith('X')]
    assert len(old_x) == len(new_x) == 1
    assert len(old_x[0][1:-1]) == 308
    assert old_x[0][0] == new_x[0][0] and old_x[0][-1] == new_x[0][-1]
    changed = 0
    for original, actual in zip(old_x[0][1:-1], new_x[0][1:-1], strict=True):
        expected = '0' if original.upper() in removed else original
        assert actual == expected
        changed += original != actual
    assert changed == 296
    # All non-boundary statements must be token-identical, except the IC path.
    def retained(rows):
        return [row for row in rows if not row[0].upper().startswith(('V', 'X'))
                and not (row[0].lower() == '.include' and row[1].endswith('.ic"'))]
    assert retained(old) == retained(new)
    old_ic = Path(json.loads((prior / 'input_manifest.json').read_text())['parameters']['initial_bias'])
    old_bias = bias(old_ic)
    new_bias = bias(current / 'initial_bias_canonical_ground.ic')
    assert len(old_bias) == 174508 and len(new_bias) == 174212
    assert all(old_bias[node] == 0 for node in removed)
    assert new_bias == {node: value for node, value in old_bias.items() if node not in removed}
    mapping = json.loads((current / 'ground_coordinate_mapping.json').read_text())
    assert mapping['aliases'] == {node: '0' for node in removed}
    controls_path = base / 'zero_voltage_canonicalization_controls_001/assessment.json'
    controls = json.loads(controls_path.read_text())
    assert controls['native_voltage_constraint_canonicalization_controls_passed']
    for name, value in controls['artifacts'].items():
        assert digest(Path(name)) == value, name
    for path in [Path(__file__).resolve(), owner, controls_path,
                 prior / 'input_manifest.json', current / 'input_manifest.json']:
        pins[str(path.resolve())] = digest(path)
    args.output.mkdir(exist_ok=False)
    save(args.output / 'assessment.json', dict(
        independent_full_boundary_and_initial_charge_mapping_passed=True,
        external_zero_voltage_constraints_removed=len(removed),
        physical_macro_ports_checked=308, physical_macro_source_byte_identical=True,
        unchanged_retained_initial_voltages=len(new_bias),
        all_removed_initial_voltages_exactly_zero=True,
        source_and_numerical_directives_unchanged=True,
        physical_wire_nodes_eliminated=0, physical_circuit_approximated=False,
        performance_improvement_demonstrated=False,
        DCO_timing_or_frequency_qualified=False, release_qualified=False, adopted=False,
        deadline_uptime=deadline, input_sha256=pins))
    print('PASS: all308 macro ports,296 zero constraints and174212 retained initial voltages checked independently.')


if __name__ == '__main__':
    main()
