"""Review completed independent gates and verify physical terminal ownership.

Passing this script supplies evidence for human/agent qualification review;
it does not change release models or declare the goal complete.
"""
import json
import time
from pathlib import Path
from runtime_common import ROOT, save, sha
from resources import lease
from audit_completed_RC_1681 import completed
from native_physical_connections import assess


def run():
    base = ROOT / 'build/signoff400'
    geometry = base / 'selected_corrected_full_RC_1671'
    converted = base / 'selected_completed_RC_reexport_1680'
    gr, gd = completed(geometry)
    cr, cd = completed(converted)
    paths = [base / name / 'assessment.json' for name in
             ['selected_completed_RC_electrical_audit_1681',
              'selected_completed_wire_values_1685',
              'selected_completed_RC_coverage_1687',
              'selected_reference_network_inventory_1690']]
    electrical, wires, coverage, inventory = [json.loads(p.read_text()) for p in paths]
    if cd['input_sha256'].get(str(gr)) != sha(gr):
        raise ValueError('conversion geometry binding changed')
    before, after = geometry / 'before.spice', converted / 'after.spice'
    for record in [electrical, wires, coverage, inventory]:
        for name, digest in record['input_sha256'].items():
            if sha(Path(name)) != digest:
                raise ValueError('gate input changed: ' + name)
        for name, digest in record.get('artifacts', {}).items():
            if sha(Path(name)) != digest:
                raise ValueError('gate output changed: ' + name)
    if wires['input_sha256'].get(str(after)) != sha(after):
        raise ValueError('wire gate must bind final export')
    if electrical['input_sha256'].get(str(after)) != sha(after):
        raise ValueError('electrical gate must bind final export')
    if coverage['input_sha256'].get(str(before)) != sha(before):
        raise ValueError('coverage gate must bind native reference')
    helpers = ['native_physical_connections.py', 'native_device_identity.py',
               'audit_keeper_native_R_contraction.py']
    pins = {str(p): sha(p) for p in [gr, cr, *paths, before, after,
            geometry / 'native.log', converted / 'native.log',
            Path(__file__).resolve(), *(Path(__file__).with_name(n) for n in helpers)]}
    out = base / 'selected_completed_RC_review_1693'
    out.mkdir(exist_ok=False)
    try:
        with lease(1, 16, time.clock_gettime(time.CLOCK_BOOTTIME) + 7200):
            physical = assess(before.read_text(), after.read_text())
            log_errors = {}
            for directory in [geometry, converted]:
                log = directory / 'native.log'
                log_errors[str(log)] = [line for line in log.read_text().splitlines()
                    if any(word in line.lower() for word in
                           ['error', 'missing terminal', 'not extracted as network',
                            'force label but no drive'])]
            checks = dict(
                completed_electrical_gates_pass=electrical['electrical_checks_pass'],
                per_wire_values_preserved=wires['per_native_wire_resistance_values_verified'],
                all_required_device_and_port_networks_output=coverage['device_and_port_output_coverage_verified'],
                coverage_count_matches_source_inventory=coverage['required_device_and_port_networks'] == inventory['required_device_and_port_networks'] == 19696,
                exactly_one_output_per_required_network=coverage['successful_native_network_markers'] == 19696,
                no_gate_or_bulk_only_source_remainder=all(inventory[k] == coverage[k] == 0 for k in ['gate_only_networks', 'bulk_only_networks']),
                capacitance_only_population_matches_source=coverage['capacitance_only_networks'] == inventory['capacitance_only_networks'] == 780557,
                physical_terminal_ownership_preserved=physical['per_physical_device_connections_verified'],
                all_physical_devices_checked=physical['physical_devices_checked'] == 62338,
                native_error_diagnostics_clear=not any(log_errors.values()))
            save(out / 'review_report.json', dict(checks=checks,
                 physical_terminal_ownership=physical, native_error_lines=log_errors))
            for name, digest in pins.items():
                if sha(Path(name)) != digest:
                    raise ValueError('review input changed: ' + name)
            save(out / 'assessment.json', dict(input_sha256=pins,
                 artifacts={str(out / 'review_report.json'): sha(out / 'review_report.json')},
                 checks=checks, all_review_checks_pass=all(checks.values()),
                 final_qualification_review_pending=True,
                 RC_export_fixed=False, release_ready=False))
    except BaseException as error:
        save(out / 'status.json', dict(state='stopped_without_qualification', reason=repr(error)))
        raise


if __name__ == '__main__':
    run()
