#!/usr/bin/env python3
"""Independently compare prepared mode decks against the frozen 450MHz grid."""
import itertools
import json
import re
from pathlib import Path
from characterize_bbpd import sha, verify


def main():
    root = Path('build/timing450/interface_characterization').resolve()
    directory = root / 'receiver_loaded_reset_all_modes_prepared_001'
    recipe_path = directory / 'preparation.json'
    output = root / 'receiver_loaded_reset_all_modes_deck_audit_001.json'
    assert not output.exists()
    recipe = json.loads(recipe_path.read_text())
    spec_path = Path('verification/engineering.json').resolve()
    spec = json.loads(spec_path.read_text())
    old_audit_path = root / 'receiver_loaded_reset_pvt_grid_deck_audit_001.json'
    old_audit = json.loads(old_audit_path.read_text())
    assert old_audit['pass'] and old_audit['complete_cartesian_coverage']
    verify(old_audit['sha256'])
    verify(recipe['source_sha256'])
    expected = set(itertools.product(spec['modes_mhz'], spec['corners'], spec['voltages'],
                                     spec['temperatures_c'], (-250, 250), (20, 200)))
    observed = set()
    pins = {str(p): sha(p) for p in (recipe_path, spec_path, old_audit_path, Path(__file__).resolve())}
    for case in recipe['prepared_cases']:
        key = tuple(case[k] for k in ('mode_mhz', 'corner', 'supply_v', 'temperature_c', 'phase_ps', 'edge_ps'))
        assert key not in observed
        observed.add(key)
        mode, corner, supply, temperature, phase, edge = key
        circuit = Path(case['directory']) / 'loaded.cir'
        source = Path(case['source_deck'])
        assert source.parent.name == f'{corner}_{supply:g}V_{temperature}C_{phase:+d}ps_{edge}ps'
        for path, wanted in ((circuit, case['deck_sha256']), (source, case['source_deck_sha256'])):
            assert sha(path) == wanted
            pins[str(path)] = wanted
        deck, base = circuit.read_text(), source.read_text()
        clock = re.search(r'^VPLL PLLOUT 0 PULSE\(0 \{VDD\} 0n ([\d.]+)p ([\d.]+)p ([\d.]+)n ([\d.]+)n\)$', deck, re.M)
        assert clock
        rise_ps, fall_ps, plateau_ns, period_ns = map(float, clock.groups())
        assert rise_ps == fall_ps == 200
        assert abs(period_ns * mode - 1000) < 3e-7
        assert abs((plateau_ns + rise_ps / 1000) - period_ns / 2) < 1e-9
        duration = 350 if mode == 450 else 450
        assert case['simulation_time_ns'] == duration
        assert f'.tran 5p {duration}n 0 5p' in deck
        if mode == 450:
            assert deck == base and case['byte_identical_to_450MHz_source']
        else:
            assert not case['byte_identical_to_450MHz_source']
            normalized = re.sub(r'^VPLL PLLOUT 0 PULSE.*$', 'PLL_CLOCK', deck, flags=re.M)
            normalized = normalized.replace('.tran 5p 450n 0 5p', '.tran 5p 350n 0 5p')
            reference = re.sub(r'^VPLL PLLOUT 0 PULSE.*$', 'PLL_CLOCK', base, flags=re.M)
            assert normalized == reference, circuit
    assert observed == expected and len(observed) == recipe['prepared_case_count'] == 900
    verify(pins)
    verify(recipe['source_sha256'])
    result = {'pass': True, 'independently_compared_decks': 900,
              'complete_cartesian_coverage': True, 'all_other_circuit_bytes_preserved': True,
              'unchanged_450MHz_decks': 180, 'source_pins': recipe['source_sha256'], 'sha256': pins,
              'release_qualified': False, 'selected': False,
              'scope': 'Prepared decks only; mode-aware native/replay auditing and all behavioral qualification remain pending.'}
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('source_pins', 'sha256')}))


if __name__ == '__main__':
    main()
