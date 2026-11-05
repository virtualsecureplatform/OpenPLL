#!/usr/bin/env python3
"""Independently audit the720-case lower-mode input index, not behavior."""
import json
import re
from decimal import Decimal
from itertools import product
from pathlib import Path
from characterize_bbpd import sha, verify


def main():
    root = Path('build/timing450/interface_characterization').resolve()
    path = root/'receiver_loaded_reset_remaining_modes_prepared_001/preparation.json'
    output = root/'receiver_loaded_reset_remaining_modes_deck_audit_001.json'
    assert not output.exists()
    recipe = json.loads(path.read_text())
    old_path = root/'receiver_loaded_reset_all_modes_prepared_001/preparation.json'
    revised_path = root/'receiver_loaded_reset_100MHz_aligned_prepared_001/preparation.json'
    old, revised = [json.loads(p.read_text()) for p in (old_path, revised_path)]
    assert old['prepared_case_count'] == 900 and revised['prepared_case_count'] == 180
    fields = ('mode_mhz', 'corner', 'supply_v', 'temperature_c', 'phase_ps', 'edge_ps')
    sources = revised['prepared_cases'] + [c for c in old['prepared_cases'] if c['mode_mhz'] in (250, 300, 400)]
    expected = {tuple(c[k] for k in fields): c for c in sources}
    assert len(sources) == len(expected) == 720
    assert recipe['prepared_case_count'] == len(recipe['prepared_cases']) == 720
    pins = dict(recipe['source_sha256'])
    pins.update({str(p): sha(p) for p in (path, old_path, revised_path, Path(__file__).resolve())})
    verify(pins)
    seen = set()
    profiles = {}
    for case in recipe['prepared_cases']:
        key = tuple(case[k] for k in fields)
        assert key not in seen and key in expected
        seen.add(key)
        parent = expected[key]
        assert case['directory'] == parent['directory'] and case['deck_sha256'] == parent['deck_sha256']
        deck_path = Path(case['directory'])/'loaded.cir'
        assert sha(deck_path) == case['deck_sha256']
        assert pins[str(deck_path)] == case['deck_sha256']
        deck = deck_path.read_text()
        mode = case['mode_mhz']
        start = Decimal('207.05') if mode == 100 else Decimal('187.05')
        assert Decimal(str(case['withdrawal_start_ns'])) == start
        assert abs(Decimal(str(case['withdrawal_half_supply_ns'])) - start - Decimal('.01')) < Decimal('1e-10')
        assert abs(Decimal(str(case['withdrawal_end_ns'])) - start - Decimal('1.52')) < Decimal('1e-10')
        pulse = re.search(r'^VCOMMAND COMMAND_RUN 0 PWL\(0 \{VDD\} ([0-9.]+)n \{VDD\} ([0-9.]+)n 0 ([0-9.]+)n 0 ([0-9.]+)n \{VDD\}\)$', deck, re.M)
        assert pulse
        assert tuple(map(Decimal, pulse.groups())) == (start, start+Decimal('.02'), start+Decimal('1.50'), start+Decimal('1.52'))
        clock = re.search(r'^VPLL PLLOUT 0 PULSE\(0 \{VDD\} 0n 200p 200p ([0-9.]+)n ([0-9.]+)n\)$', deck, re.M)
        assert clock
        plateau, period = map(Decimal, clock.groups())
        assert abs(period*mode - 1000) < Decimal('3e-7')
        assert abs(plateau+Decimal('.2')-period/2) < Decimal('1e-9')
        assert case['simulation_time_ns'] == 450 and '.tran 5p 450n 0 5p' in deck
        profiles[mode] = profiles.get(mode, 0) + 1
    assert seen == set(product((100, 250, 300, 400), ('tt', 'ff', 'ss', 'sf', 'fs'),
                               (1.62, 1.8, 1.95), (-40, 27, 125), (-250, 250), (20, 200)))
    assert profiles == {100:180, 250:180, 300:180, 400:180}
    verify(pins)
    result = {'preparation_audit_pass': True, 'independently_compared_decks': 720,
              'exact_mode_PVT_phase_edge_coverage_verified': True, 'cases_by_mode_mhz': profiles,
              'prepared_source_deck_identity_verified': True, 'withdrawal_profiles_verified': True,
              'no_450MHz_cases': True, 'unique_evidence_pins_verified': len(pins), 'sha256': pins,
              'native_simulation_launched': False, 'pilot_behavior_validation_pending': True,
              'release_qualified': False, 'selected': False,
              'scope': 'Exact720-case input-index/deck/clock/withdrawal-profile audit only. '
                       'Corrected100MHz and other lower-mode native loaded-event qualification remains pending; '
                       'does not establish full PVT/MTBF/reset/acquisition/wholePLL/release qualification.'}
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'sha256'}))


if __name__ == '__main__':
    main()
