"""Completed-only independent electrical checks for the named-point repairs."""
import json
import shlex
import time
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path
from runtime_common import ROOT, save, sha
from resources import lease
from native_C_roundoff import assess
from native_C_passivity_v2 import assess_caps
from native_physical_connections import assess as physical
from native_wire_values import assess as wires
from audit_keeper_native_R_contraction import parse


def run():
    base = ROOT / 'build/signoff400'
    controls = base / 'selected_single_point_RC_controls_1706'
    repeated = base / 'selected_repeated_RC_labels_1705'
    paths = [controls / 'assessment.json', repeated / 'assessment.json', Path(__file__).resolve()]
    for p in paths[:2]:
        record = json.loads(p.read_text())
        for name, digest in record['artifacts'].items():
            if sha(name) != digest:
                raise ValueError('completed control changed: ' + name)
    helper_names = ['native_C_roundoff.py', 'native_C_passivity_v2.py',
                    'native_physical_connections.py', 'native_wire_values.py',
                    'native_device_identity.py', 'audit_keeper_native_R_contraction.py']
    paths += [Path(__file__).with_name(n) for n in helper_names]
    pins = {str(p): sha(p) for p in paths}
    out = base / 'selected_single_point_RC_assessment_1707'
    out.mkdir(exist_ok=False)
    results = []
    with lease(1, 4, time.clock_gettime(time.CLOCK_BOOTTIME) + 600):
        for case in sorted(p for p in controls.iterdir() if p.is_dir() and p.name.endswith('fixed1')):
            before, after = [(case / n).read_text() for n in ['before.spice', 'after.spice']]
            ext = (case / 'RotatedCrop.res.ext').read_text()
            locations = defaultdict(set)
            for line in ext.splitlines():
                if line.startswith('rnode '):
                    fields = shlex.split(line)
                    locations[fields[1]].add(tuple(fields[4:6]))
            result = dict(case=case.name, charge=assess(before, after),
                          physical_connections=physical(before, after),
                          wire_values=wires(ext, after),
                          passivity=assess_caps(parse(after)['caps']),
                          duplicate_names_at_distinct_points={n: sorted(v) for n, v in locations.items() if len(v) > 1})
            results.append(result)
        rows = json.loads(paths[1].read_text())['results']
        repaired = [row for row in rows if row['engine'] == 'magic_single_RC_points_1704']
        label_control_pass = len(repaired) == 2 and all(
            abs(F(row['effective_A_AFAR_ohms_exact']) - F(199, 40)) <= F(199, 40) / 2**23
            and row['formal_ports_preserved'] and not row['duplicate_names_at_distinct_points']
            for row in repaired)
        baseline_reproduced = any(row['engine'] == 'magic_precise_ground_ports_1700'
            and row['repeated_labels'] and F(row['effective_A_AFAR_ohms_exact']) == F(3, 2)
            for row in rows)
        passed = len(results) == 4 and label_control_pass and baseline_reproduced and all(
            r['charge']['native_devices_and_C_conserved']
            and r['physical_connections']['per_physical_device_connections_verified']
            and r['wire_values']['per_native_wire_resistance_values_verified']
            and r['passivity']['linear_C_PSD_certified']
            and not r['duplicate_names_at_distinct_points'] for r in results)
        for name, digest in pins.items():
            if sha(name) != digest:
                raise ValueError('assessment input changed')
        save(out / 'assessment.json', dict(input_sha256=pins, results=results,
             repeated_label_failure_reproduced=baseline_reproduced,
             repaired_analytical_wire_R_preserved=label_control_pass,
             all_control_checks_pass=passed, RC_export_fixed=False, release_ready=False))
        print(json.dumps(dict(all_control_checks_pass=passed, results=[dict(case=r['case'],
             charge=r['charge']['native_devices_and_C_conserved'],
             physical=r['physical_connections']['per_physical_device_connections_verified'],
             wires=r['wire_values']['per_native_wire_resistance_values_verified'],
             wire_failure_examples=r['wire_values']['failures'][:2],
             passivity=r['passivity']['linear_C_PSD_certified'],
             duplicate_names=len(r['duplicate_names_at_distinct_points'])) for r in results]), indent=2))


if __name__ == '__main__':
    run()
