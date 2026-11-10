"""Completed-only electrical audit; coverage and wire-value gates stay explicit."""
import json
import time
from pathlib import Path

from runtime_common import ROOT, save, sha
from resources import identity, lease
from native_C_roundoff import assess
from native_C_passivity_v2 import assess_caps
from native_device_identity import compare_parameters
from audit_keeper_native_R_contraction import parse


def completed(directory):
    receipt = directory / 'assessment.json'
    record = json.loads(receipt.read_text())
    if record.get('native_process_completed') is not True:
        raise ValueError('normal native completion required: ' + str(directory))
    process = json.loads((directory / 'native.process.json').read_text())
    if identity(process['pid']) == process['birth']:
        raise ValueError('native producer still live')
    for name, digest in record['artifacts'].items():
        if sha(Path(name)) != digest:
            raise ValueError('completed artifact changed: ' + name)
    return receipt, record


def run():
    base = ROOT / 'build/signoff400'
    geometry = base / 'selected_corrected_full_RC_1671'
    converted = base / 'selected_completed_RC_reexport_1680'
    # All admission happens before creating output: active data is never parsed.
    gr, gd = completed(geometry)
    cr, cd = completed(converted)
    if cd['input_sha256'].get(str(gr)) != sha(gr):
        raise ValueError('conversion must bind this completed native geometry')
    reference = base / 'selected_precise_C_reference_1664/capacitance.spice'
    ref_receipt = reference.parent / 'assessment.json'
    rr = json.loads(ref_receipt.read_text())
    if rr['artifacts'][str(reference)] != sha(reference):
        raise ValueError('precise full reference changed')
    before, after = geometry / 'before.spice', converted / 'after.spice'
    helpers = ['native_C_roundoff.py', 'native_C_passivity_v2.py',
               'native_device_identity.py', 'audit_keeper_native_R_contraction.py',
               'compare_native_R_with_aliases.py', 'native_spice_comments.py']
    paths = [gr, cr, ref_receipt, reference, before, after,
             geometry / 'native.log', converted / 'native.log',
             Path(__file__).resolve(),
             *(Path(__file__).with_name(name) for name in helpers)]
    pins = {str(path): sha(path) for path in paths}
    out = base / 'selected_completed_RC_electrical_audit_1681'
    out.mkdir(exist_ok=False)
    try:
        with lease(1, 16, time.clock_gettime(time.CLOCK_BOOTTIME) + 7200):
            save(out / 'status.json', dict(state='auditing_completed_electrical_network'))
            text_before, text_after = before.read_text(), after.read_text()
            controls = {}
            controls['reference_to_before'] = assess(reference.read_text(), text_before)
            controls['before_to_final'] = assess(text_before, text_after)
            controls['physical_identity'] = compare_parameters(text_before, text_after)
            parsed = parse(text_after)
            controls['final_linear_C_passivity'] = assess_caps(parsed['caps'])
            bad_prefixes = ['OPENPLL_RC_BREAK_BOUNDS', 'OPENPLL_RC_NEGATIVE_AREA',
                            'OPENPLL_RC_BAD_AREA', 'OPENPLL_RC_BAD_CAP_BUDGET',
                            'OPENPLL_RC_EMPTY_CROSSPLANE_OVERLAP',
                            'OPENPLL_RC_EMPTY_DRIVER_OVERLAP']
            diagnostics = {}
            for log in [geometry / 'native.log', converted / 'native.log']:
                text = log.read_text()
                diagnostics[str(log)] = {p: text.count(p) for p in bad_prefixes}
            checks = dict(
                precise_reference_conserved=controls['reference_to_before']['native_devices_and_C_conserved'],
                final_charge_devices_ports_conserved=controls['before_to_final']['native_devices_and_C_conserved'],
                physical_device_parameters_conserved=controls['physical_identity']['per_physical_device_parameters_match'],
                all_62338_physical_devices_present=controls['physical_identity']['physical_device_count'] == 62338,
                actual_final_C_operator_PSD_certified=controls['final_linear_C_passivity']['linear_C_PSD_certified'],
                geometry_diagnostics_clear=not any(v for row in diagnostics.values() for v in row.values()),
                positive_wire_network_present=any(v > 0 for a, b, v in parsed['resistors']),
                no_negative_wire_R=all(v >= 0 for a, b, v in parsed['resistors']))
            save(out / 'electrical_report.json', dict(checks=checks, controls=controls,
                 geometry_diagnostics=diagnostics))
            for name, digest in pins.items():
                if sha(Path(name)) != digest:
                    raise ValueError('audit input changed: ' + name)
            save(out / 'assessment.json', dict(input_sha256=pins,
                 artifacts={str(out / 'electrical_report.json'): sha(out / 'electrical_report.json')},
                 electrical_checks_pass=all(checks.values()), checks=checks,
                 native_eligible_conductor_coverage_verified=False,
                 per_native_wire_resistance_values_verified=False,
                 RC_export_fixed=False, release_ready=False))
            save(out / 'status.json', dict(state='electrical_audit_complete',
                 electrical_checks_pass=all(checks.values()), additional_gates_pending=True))
    except BaseException as error:
        save(out / 'status.json', dict(state='stopped_without_qualification', reason=repr(error)))
        raise


if __name__ == '__main__':
    run()
