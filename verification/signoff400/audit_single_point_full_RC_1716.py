"""Audit every completed full-layout export gate for the physical-point repair."""
import json
import re
import shlex
import time
from collections import defaultdict
from pathlib import Path
from runtime_common import ROOT, save, sha
from resources import lease
from audit_completed_RC_1681 import completed
from native_C_roundoff import assess
from native_C_passivity_v2 import assess_caps
from native_physical_connections import assess as physical
from native_wire_values import assess as wires
from native_RC_coverage_v2 import assess as coverage
from audit_keeper_native_R_contraction import parse
from extract_keeper_flat_geometry_C import FLAT


def run():
    base = ROOT / 'build/signoff400'
    source = base / 'selected_single_point_full_RC_1714'
    receipt, record = completed(source)
    reference = base / 'selected_precise_C_reference_1664/capacitance.spice'
    ref_receipt = reference.parent / 'assessment.json'
    rr = json.loads(ref_receipt.read_text())
    if rr['artifacts'][str(reference)] != sha(reference):
        raise ValueError('completed precise reference changed')
    before, after = source / 'before.spice', source / 'after.spice'
    ext, res = source / (FLAT + '.ext'), source / (FLAT + '.res.ext')
    original = base / 'selected_keeper_contact_corrected_C_1573' / ext.name
    if sha(ext) != record['input_sha256'][str(original)]:
        raise ValueError('native source EXT identity changed')
    helpers = ['native_C_roundoff.py', 'native_C_passivity_v2.py',
               'native_physical_connections.py', 'native_wire_values.py',
               'native_RC_coverage_v2.py', 'native_device_identity.py',
               'audit_keeper_native_R_contraction.py', 'compare_native_R_with_aliases.py',
               'audit_completed_RC_1681.py', 'native_spice_comments.py']
    paths = [receipt, ref_receipt, reference, before, after, ext, res, source / 'native.log',
             Path(__file__).resolve(), *(Path(__file__).with_name(n) for n in helpers)]
    pins = {str(p): sha(p) for p in paths}
    out = base / 'selected_single_point_full_RC_audit_1716'
    out.mkdir(exist_ok=False)
    try:
        with lease(1, 16, time.clock_gettime(time.CLOCK_BOOTTIME) + 10800):
            save(out / 'status.json', dict(state='auditing_completed_full_physical_RC'))
            btext, atext, native = before.read_text(), after.read_text(), res.read_text()
            results = dict(reference_to_before=assess(reference.read_text(), btext),
                 charge=assess(btext, atext), physical_connections=physical(btext, atext),
                 wire_values=wires(native, atext), coverage=coverage(btext, native, ext.read_text()),
                 passivity=assess_caps(parse(atext)['caps']))
            positions = defaultdict(set)
            for line in native.splitlines():
                if line.startswith('rnode '):
                    f = shlex.split(line); positions[f[1]].add(tuple(f[4:6]))
            duplicate = {name: sorted(points) for name, points in positions.items() if len(points) > 1}
            log = (source / 'native.log').read_text()
            prefixes = ['OPENPLL_RC_BREAK_BOUNDS', 'OPENPLL_RC_NEGATIVE_AREA',
                        'OPENPLL_RC_BAD_AREA', 'OPENPLL_RC_BAD_CAP_BUDGET',
                        'OPENPLL_RC_EMPTY_CROSSPLANE_OVERLAP', 'OPENPLL_RC_EMPTY_DRIVER_OVERLAP']
            geometry_failures = {p: log.count(p) for p in prefixes}
            # These exact GDS boundary warnings are retained and counted. Other
            # native errors, orphan repairs or unextracted networks fail review.
            boundary = re.compile(r'^Error while reading cell "' + re.escape(FLAT)
                + r'" \(byte position \d+\): Warning:  Cell ' + re.escape(FLAT)
                + r' boundary was redefined\.$')
            warnings, errors = 0, []
            for line in log.splitlines():
                if boundary.fullmatch(line):
                    warnings += 1
                elif any(token in line.lower() for token in
                         ['error', 'orphaned node', 'missing terminal', 'not extracted as network', 'force label but no drive']):
                    errors.append(line)
            cov = results['coverage']
            checks = dict(
                precise_C_reference_conserved=results['reference_to_before']['native_devices_and_C_conserved'],
                device_charge_and_formal_ports_conserved=results['charge']['native_devices_and_C_conserved'],
                all_62338_physical_device_connections_preserved=results['physical_connections']['per_physical_device_connections_verified'] and results['physical_connections']['physical_devices_checked'] == 62338,
                every_native_wire_value_preserved=results['wire_values']['per_native_wire_resistance_values_verified'],
                all_19696_conductors_output_once=cov['device_and_port_output_coverage_verified'] and cov['required_device_and_port_networks'] == cov['successful_native_network_markers'] == 19696,
                actual_linear_C_PSD_certified=results['passivity']['linear_C_PSD_certified'],
                distinct_physical_points_have_distinct_names=not duplicate,
                no_native_geometry_failure=not any(geometry_failures.values()),
                no_native_export_errors_or_orphan_repairs=not errors,
                original_65_port_population_indexed='OPENPLL_RC_PORT_INDEX ports=65' in log)
            save(out / 'electrical_report.json', dict(results=results, checks=checks,
                 duplicate_names_at_distinct_points=duplicate, geometry_failures=geometry_failures,
                 known_GDS_boundary_warnings=warnings, other_native_error_lines=errors))
            for name, digest in pins.items():
                if sha(name) != digest:
                    raise ValueError('full audit input changed: ' + name)
            save(out / 'assessment.json', dict(input_sha256=pins,
                 artifacts={str(out / 'electrical_report.json'): sha(out / 'electrical_report.json')},
                 checks=checks, all_full_RC_checks_pass=all(checks.values()),
                 qualification_review_pending=True, RC_export_fixed=False, release_ready=False))
            save(out / 'status.json', dict(state='completed_full_RC_review_pending',
                 all_full_RC_checks_pass=all(checks.values())))
    except BaseException as error:
        save(out / 'status.json', dict(state='stopped_without_qualification', reason=repr(error)))
        raise


if __name__ == '__main__':
    run()
