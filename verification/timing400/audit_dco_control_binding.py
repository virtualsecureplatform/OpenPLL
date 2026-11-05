#!/usr/bin/env python3
"""Audit native fixture instance order against the actual extracted DCO header.

Complements settled RTL encoding checks; no analog or assembled-top claim.
"""
import argparse
import json
from pathlib import Path
import re

from run_dco_qualification import ROOT, sha, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    base = ROOT/'build/timing400/release_001/dco_control_encoding_001'
    source = base/'assessment.json'
    report = json.loads(source.read_text())
    assert report['steady_encoding_matches_native_fixture']
    assert report['actual_registered_code_pairs_checked'] == 12288
    assert report['records'][1]['wrong_polarity_rejected']
    assert not report['release_qualified'] and not report['calibration_model_qualified']
    pins = {str(p): sha(p) for p in (source, Path(__file__).resolve())}
    for group in (report['input_sha256'], report['artifacts']):
        for name, digest in group.items():
            assert sha(name) == digest, name
            pins[name] = digest
    original = ROOT/'build/timing450/dco_c1_fine_load_001/tt_screen_160/dco_postlayout_tt_coarse_01_code_128.spice'
    provenance = json.loads(original.with_suffix('.provenance.json').read_text())
    model = Path(provenance['parameters']['rcx_netlist'])
    top = provenance['parameters']['subckt_name']
    declaration, = re.findall(r'^\.subckt\s+'+re.escape(top)+r'\s+([^\n]+(?:\n\+[^\n]*)*)', model.read_text(), re.M)
    expected = declaration.replace('\n+', ' ').split()
    assert len(expected) == len(set(expected)) == 308
    assert {n for n in expected if n.startswith('DCO_THERM[')} == {f'DCO_THERM[{i}]' for i in range(255)}
    assert {n for n in expected if n.startswith('COARSETHERMAL_CODE[')} == {f'COARSETHERMAL_CODE[{i}]' for i in range(47)}
    decks = sorted((base/'native_fixture_basis').glob('*.cir'))
    assert len(decks) == 304
    for path in [original, *decks]:
        instance, = re.findall(r'^XDUT\s+([^\n]+(?:\n\+[^\n]*)*)', path.read_text(), re.M)
        tokens = instance.replace('\n+', ' ').split()
        assert tokens[-1] == top and tokens[:-1] == expected, path
    out.mkdir(parents=True, exist_ok=False)
    save(out/'assessment.json', dict(input_sha256=pins, extracted_dco_subckt=top,
        extracted_port_count=len(expected), exact_ordered_instance_bindings_checked=305,
        fine_control_ports=255, coarse_control_ports=47,
        steady_rtl_pairs_previously_checked=12288, wrong_polarity_control_rejected=True,
        native_fixture_instance_order_verified=True, native_simulations_added=0,
        dynamic_glitch_or_phase_response_qualified=False, assembled_connectivity_qualified=False,
        calibration_model_qualified=False, whole_pll_qualification_cases_passed=0,
        release_qualified=False, scope=__doc__))
    print('Verified305ordered native fixture bindings to the308-port extracted macro')


if __name__ == '__main__':
    main()
