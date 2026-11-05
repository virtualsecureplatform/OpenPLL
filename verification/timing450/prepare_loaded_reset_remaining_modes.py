#!/usr/bin/env python3
"""Index720 audited lower-mode decks, including revised100MHz stimulus."""
import json
from itertools import product
from pathlib import Path
from characterize_bbpd import sha, verify
from loaded_reset_withdrawal_profile import validate_withdrawal


def main():
    root = Path('build/timing450/interface_characterization').resolve()
    output = root/'receiver_loaded_reset_remaining_modes_prepared_001'
    assert not output.exists()
    old_path = root/'receiver_loaded_reset_all_modes_prepared_001/preparation.json'
    revised_path = root/'receiver_loaded_reset_100MHz_aligned_prepared_001/preparation.json'
    old_audit_path = root/'receiver_loaded_reset_all_modes_deck_audit_001.json'
    revised_audit_path = root/'receiver_loaded_reset_100MHz_aligned_deck_audit_001.json'
    old, revised, old_audit, revised_audit = [json.loads(p.read_text()) for p in
        (old_path, revised_path, old_audit_path, revised_audit_path)]
    assert old['prepared_case_count'] == 900 and revised['prepared_case_count'] == 180
    assert old_audit['pass'] and old_audit['independently_compared_decks'] == 900
    assert revised_audit['deck_preparation_audit_pass'] and revised_audit['prepared_cases'] == 180
    pins = {}
    for mapping in (old_audit['sha256'], revised_audit['sha256']):
        for path, digest in mapping.items():
            assert path not in pins or pins[path] == digest
            pins[path] = digest
    for path in (old_path, revised_path, old_audit_path, revised_audit_path, Path(__file__).resolve(),
                 Path(__file__).with_name('loaded_reset_withdrawal_profile.py').resolve()):
        pins[str(path)] = sha(path)
    verify(pins)
    cases = []
    seen = set()
    for original in revised['prepared_cases'] + [c for c in old['prepared_cases'] if c['mode_mhz'] in (250, 300, 400)]:
        case = dict(original)
        case['withdrawal_start_ns'] = 207.05 if case['mode_mhz'] == 100 else 187.05
        case['withdrawal_half_supply_ns'] = case['withdrawal_start_ns'] + .01
        case['withdrawal_end_ns'] = case['withdrawal_start_ns'] + 1.52
        case['simulation_time_ns'] = 450
        case['stimulus_family'] = 'revised100MHz207ns' if case['mode_mhz'] == 100 else 'original187ns'
        deck = Path(case['directory'])/'loaded.cir'
        assert sha(deck) == case['deck_sha256']
        validate_withdrawal(deck.read_text(), case['mode_mhz'], case['withdrawal_start_ns'], case)
        key = tuple(case[k] for k in ('mode_mhz', 'corner', 'supply_v', 'temperature_c', 'phase_ps', 'edge_ps'))
        assert key not in seen
        seen.add(key)
        cases.append(case)
    assert seen == set(product((100, 250, 300, 400), ('tt', 'ff', 'ss', 'sf', 'fs'),
                               (1.62, 1.8, 1.95), (-40, 27, 125), (-250, 250), (20, 200)))
    assert len(cases) == 720
    cases.sort(key=lambda c: tuple(c[k] for k in ('mode_mhz', 'corner', 'supply_v', 'temperature_c', 'phase_ps', 'edge_ps')))
    verify(pins)
    output.mkdir()
    result = {'prepared_case_count': 720, 'prepared_cases': cases, 'source_sha256': pins,
              'modes_mhz': [100, 250, 300, 400], 'revised100MHz_cases': 180,
              'original_other_lower_mode_cases': 540, 'duplicates_450MHz_natives': False,
              'native_simulation_launched': False, 'pilot_behavior_validation_pending': True,
              'release_qualified': False, 'selected': False,
              'scope': 'Index of720 independently audited prepared lower-mode PVT/phase/edge decks. '
                       'Existing180450MHz native grid remains separate. Corrected100MHz and other-mode '
                       'pilot loaded/fresh/stale/control/independent qualification required before broader launch. '
                       'FixedRC/ideal committed controls; full reset/acquisition/MTBF/wholePLL remain outstanding.'}
    (output/'preparation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('prepared_cases', 'source_sha256')}))


if __name__ == '__main__':
    main()
