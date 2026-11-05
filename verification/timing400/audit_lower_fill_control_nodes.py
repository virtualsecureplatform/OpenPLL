#!/usr/bin/env python3
"""Resolve actual substrate identities in lower-fill extraction controls.

An automatically named substrate is not a floating capacitor-only electrode.
These controls constrain CAD interpretation; they do not validate a substitute
implant mask or establish an enclosure for manufacturing FOM behavior.
"""
from decimal import Decimal
from pathlib import Path
import re
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def capacitance(token):
    suffix = {'f': Decimal('1e-15'), 'p': Decimal('1e-12'), 'n': Decimal('1e-9')}
    return Decimal(token[:-1])*suffix[token[-1]] if token[-1] in suffix else Decimal(token)


def main():
    base = ROOT/'build/timing400/release_001'
    source = base/'lower_fill_capacitance_controls_001'
    receipt = verify(source/'assessment.json')
    out = base/'lower_fill_control_node_audit_001'
    assert not out.exists()
    records = {}
    paths = [Path(__file__).resolve(), source/'assessment.json']
    for name, result in receipt['cases'].items():
        ext = source/name/'LOWER_FILL_CONTROL.ext'
        spice = source/name/'control.spice'
        paths += [ext, spice]
        substrates = re.findall(r'^substrate "([^"]+)"', ext.read_text(), re.M)
        assert len(substrates) == 1
        caps = []
        for line in result['capacitor_records']:
            _, a, b, value, *_ = line.split()
            caps.append((a, b, capacitance(value)))
        records[name] = dict(substrate_node=substrates[0],
            sig_substrate_f=str(sum((c for a,b,c in caps if {a,b}=={'SIG',substrates[0]}), Decimal(0))),
            sig_explicit_well_f=str(sum((c for a,b,c in caps if {a,b}=={'SIG','VPWR'}), Decimal(0))),
            capacitor_records=result['capacitor_records'])
    assert records['ohmic_p_tap']['substrate_node'].startswith('a_')
    assert records['ohmic_p_tap']['sig_substrate_f'] == str(Decimal('6.87704e-15'))
    assert records['nwell_ohmic_n_tap']['substrate_node'] == 'VSUBS'
    assert Decimal(records['nwell_ohmic_n_tap']['sig_explicit_well_f']) == Decimal('5.97383e-15')
    # Independent series reduction is valid only for the explicitly floating
    # poly electrode in this isolated linear control, with ideal bulk reference.
    lines = receipt['cases']['poly_drawing']['capacitor_records']
    caps = [line.split() for line in lines]
    floating = {b for row in caps for b in row[1:3]} - {'SIG', 'VSUBS'}
    assert len(floating) == 1
    floating = next(iter(floating))
    def branch(a,b):
        return sum((capacitance(row[3]) for row in caps if set(row[1:3])=={a,b}), Decimal(0))
    a, b, direct = branch('SIG',floating), branch(floating,'VSUBS'), branch('SIG','VSUBS')
    assert a > 0 and b > 0
    effective = direct + a*b/(a+b)
    baseline = Decimal(records['no_tile']['sig_substrate_f'])
    out.mkdir()
    save(out/'assessment.json', dict(input_sha256={str(p):sha(p) for p in paths},
        controls=records, ohmic_p_tap_auto_name_is_substrate_not_floating=True,
        ohmic_n_tap_couples_to_existing_well_node=True,
        isolated_poly_floating_effective_capacitance_f=str(effective),
        baseline_control_capacitance_f=str(baseline),
        isolated_poly_effective_added_capacitance_f=str(effective-baseline),
        floating_poly_reduction_assumes_ideal_bulk_reference=True,
        ohmic_surrogate_is_manufacturing_fom_model=False,
        full_fom_material_coverage_qualified=False, process_enclosure_qualified=False,
        native_analog_jobs_added=0, release_qualified=False, adopted=False, scope=__doc__))
    print('Lower-fill node audit passed: P-tap auto-name is substrate; poly floating branch independently reduced; FOM material model remains open.')


if __name__ == '__main__':
    main()
