#!/usr/bin/env python3
"""Prepare loaded-reset decks for every required mode without launching simulations."""
import json
from pathlib import Path
from characterize_bbpd import sha, verify


def main():
    root = Path('build/timing450/interface_characterization').resolve()
    original = root / 'receiver_loaded_reset_pvt_grid_prepared_001/preparation.json'
    audit_path = root / 'receiver_loaded_reset_pvt_grid_deck_audit_001.json'
    engineering = Path('verification/engineering.json').resolve()
    output = root / 'receiver_loaded_reset_all_modes_prepared_001'
    assert not output.exists()
    recipe = json.loads(original.read_text())
    spec = json.loads(engineering.read_text())
    audit = json.loads(audit_path.read_text())
    assert recipe['prepared_case_count'] == 180
    pins = dict(recipe['source_sha256'])
    for path in (original, audit_path, engineering, Path(__file__).resolve()):
        pins[str(path)] = sha(path)
    # Independently audited prepared decks are immutable inputs.
    for case in recipe['prepared_cases']:
        path = Path(case['directory']) / 'loaded.cir'
        assert sha(path) == case['deck_sha256']
        pins[str(path)] = case['deck_sha256']
    verify(pins)
    assert spec['modes_mhz'] == [100, 250, 300, 400, 450]
    assert spec['reference_mhz'] == 25
    output.mkdir()
    cases = []
    old_clock = 'VPLL PLLOUT 0 PULSE(0 {VDD} 0n 200p 200p 0.911111111n 2.222222222n)'
    for mode in spec['modes_mhz']:
        period_ns = 1000 / mode
        # PULSE's plateau excludes the 200ps rising edge; preserve 50% threshold duty.
        plateau_ns = period_ns / 2 - 0.2
        assert plateau_ns > 0
        for source in recipe['prepared_cases']:
            source_path = Path(source['directory']) / 'loaded.cir'
            deck = source_path.read_text()
            assert deck.count(old_clock) == 1 and deck.count('.tran 5p 350n 0 5p') == 1
            duration_ns = 350 if mode == 450 else 450
            if mode != 450:
                new_clock = ('VPLL PLLOUT 0 PULSE(0 {VDD} 0n 200p 200p '
                             f'{plateau_ns:.9f}n {period_ns:.9f}n)')
                deck = deck.replace(old_clock, new_clock)
                deck = deck.replace('.tran 5p 350n 0 5p', '.tran 5p 450n 0 5p')
            directory = output / f'{mode}MHz' / source_path.parent.name
            directory.mkdir(parents=True)
            circuit = directory / 'loaded.cir'
            circuit.write_text(deck)
            cases.append({**{k: v for k, v in source.items() if k not in ('directory', 'deck_sha256')},
                          'mode_mhz': mode, 'simulation_time_ns': duration_ns,
                          'directory': str(directory), 'deck_sha256': sha(circuit),
                          'source_deck': str(source_path),
                          'source_deck_sha256': source['deck_sha256'],
                          'byte_identical_to_450MHz_source': mode == 450})
    assert len(cases) == 900 and len({c['directory'] for c in cases}) == 900
    verify(pins)
    receipt = {'prepared_case_count': 900, 'prepared_cases': cases, 'source_sha256': pins,
               'modes_mhz': spec['modes_mhz'], 'simulation_completed': False,
               'release_qualified': False, 'selected': False,
               'scope': 'Five required modes x45 primitive PVT x2 signed phases x2 REF/DIV edges. '
                        '450MHz decks unchanged; lower modes extend to450ns for slower receiver response. '
                        'Fixed extracted RC, matching diode models, ideal committed controls. '
                        'Mode-aware replay/window audits required before launch; no behavioral, MTBF, acquisition or wholePLL qualification.'}
    (output / 'preparation.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'prepared_case_count': len(cases), 'output': str(output)}))


if __name__ == '__main__':
    main()
