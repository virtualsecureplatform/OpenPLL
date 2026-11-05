#!/usr/bin/env python3
"""Prepare all 180 loaded-reset PVT/phase/edge decks; no simulations or signoff."""
import itertools
import json
import re
from pathlib import Path
from characterize_bbpd import sha, verify


def main():
    root = Path('build/timing450/interface_characterization').resolve()
    template = root/'receiver_loaded_macro_reset_ss125_dn_edge200_prepared_001'
    fixtures = root/'receiver_committed_macro_reset_pvt_fixtures_001'
    output = root/'receiver_loaded_reset_pvt_grid_prepared_001'
    assert not output.exists()
    manifest = json.loads((template/'input_manifest.json').read_text())
    pins = dict(manifest['sha256'])
    for p in [template/'input_manifest.json', template/'preparation.json',
              Path(__file__).resolve()]:
        pins[str(p)] = sha(p)
    fixture_views = {}
    for corner, temperature in itertools.product(('tt','ff','ss','sf','fs'),(-40,27,125)):
        directory = fixtures/f'{corner}_{temperature}C'
        receipt = directory/'extraction.json'
        data = json.loads(receipt.read_text())
        assert data['fixed_model_corner'] == corner
        assert data['fixed_model_temperature_c'] == temperature
        for path, digest in data['sha256'].items():
            assert path not in pins or pins[path] == digest
            pins[path] = digest
        assert sha(directory/'receiver.spice') == data['receiver_sha256']
        for p in [receipt,directory/'receiver.spice']:
            pins[str(p)] = sha(p)
        fixture_views[corner,temperature] = directory/'receiver.spice'
    verify(pins)
    base = (template/'loaded.cir').read_text()
    include = next(line for line in base.splitlines() if line.startswith('.include ') and 'receiver_committed_macro_reset_pvt_fixtures_001/ss_125C/' in line)
    lib = next(line for line in base.splitlines() if line.startswith('.lib '))
    assert lib.endswith(' ss')
    output.mkdir()
    cases = []
    for corner, supply, temperature, phase, edge in itertools.product(
            ('tt','ff','ss','sf','fs'),(1.62,1.8,1.95),(-40,27,125),(-250,250),(20,200)):
        deck = base.replace(include, f'.include "{fixture_views[corner,temperature]}"')
        deck = deck.replace(lib,lib[:-3]+' '+corner)
        deck = deck.replace('.param VDD=1.62',f'.param VDD={supply:g}')
        deck = deck.replace('.options device temp=125',f'.options device temp={temperature}')
        deck = deck.replace('VDIV CLKDIVR 0 PULSE(0 {VDD} 9.75n ',f'VDIV CLKDIVR 0 PULSE(0 {{VDD}} {10+phase/1000:g}n ')
        for source in ('VREF REF ','VDIV CLKDIVR '):
            line = next(line for line in deck.splitlines() if line.startswith(source))
            assert line.count('200p 200p') == 1
            deck = deck.replace(line,line.replace('200p 200p',f'{edge}p {edge}p'))
        directory = output/f'{corner}_{supply:g}V_{temperature}C_{phase:+d}ps_{edge}ps'
        directory.mkdir()
        circuit = directory/'loaded.cir'
        circuit.write_text(deck)
        cases.append({'directory':str(directory),'corner':corner,'supply_v':supply,
                      'temperature_c':temperature,'phase_ps':phase,'edge_ps':edge,
                      'deck_sha256':sha(circuit)})
    assert len(cases)==180 and len({case['directory'] for case in cases})==180
    verify(pins)
    report = {'prepared_cases':cases,'prepared_case_count':180,
              'source_sha256':pins,'simulation_completed':False,
              'release_qualified':False,'selected':False,
              'scope':'45 primitive PVT x2 signed phase x2 REF/DIV edges at450MHz. Matching fixed diode fixtures; nominal cell RC/fixed route RC and ideal committed controls. No native, MTBF or wholePLL qualification.'}
    (output/'preparation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'prepared_case_count':180,'output':str(output)}))


if __name__ == '__main__':
    main()
