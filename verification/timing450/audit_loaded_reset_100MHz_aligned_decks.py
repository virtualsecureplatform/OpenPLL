#!/usr/bin/env python3
"""Independently audit the180 revised100MHz stimulus decks; no behavioral pass."""
import json
import re
from decimal import Decimal
from itertools import product
from pathlib import Path
from characterize_bbpd import sha, verify


def main():
    root = Path('build/timing450/interface_characterization').resolve()
    path = root/'receiver_loaded_reset_100MHz_aligned_prepared_001/preparation.json'
    output = root/'receiver_loaded_reset_100MHz_aligned_deck_audit_001.json'
    assert not output.exists()
    recipe = json.loads(path.read_text())
    original_path = root/'receiver_loaded_reset_all_modes_prepared_001/preparation.json'
    original = json.loads(original_path.read_text())
    originals = {Path(c['directory']).name: c for c in original['prepared_cases'] if c['mode_mhz'] == 100}
    assert recipe['prepared_case_count'] == len(recipe['prepared_cases']) == len(originals) == 180
    pins = dict(recipe['source_sha256'])
    pins.update({str(p): sha(p) for p in (path, original_path, Path(__file__).resolve())})
    verify(pins)
    found = set()
    for case in recipe['prepared_cases']:
        key = tuple(case[k] for k in ('corner', 'supply_v', 'temperature_c', 'phase_ps', 'edge_ps'))
        assert key not in found
        found.add(key)
        source = Path(case['source_deck'])
        deck = Path(case['directory'])/'loaded.cir'
        before, after = source.read_text(), deck.read_text()
        old = originals[Path(case['directory']).name]
        assert source == Path(old['directory'])/'loaded.cir'
        assert sha(source) == case['source_deck_sha256'] == old['deck_sha256']
        assert sha(deck) == case['deck_sha256']
        pins[str(deck)] = case['deck_sha256']
        pulse = r'^VCOMMAND COMMAND_RUN 0 PWL\(0 \{VDD\} ([0-9.]+)n \{VDD\} ([0-9.]+)n 0 ([0-9.]+)n 0 ([0-9.]+)n \{VDD\}\)$'
        b, a = re.search(pulse, before, re.M), re.search(pulse, after, re.M)
        assert b and a
        bt, at = [tuple(map(Decimal, match.groups())) for match in (b, a)]
        assert bt == tuple(map(Decimal, ('187.05', '187.07', '188.55', '188.57')))
        assert at == tuple(map(Decimal, ('207.05', '207.07', '208.55', '208.57')))
        assert tuple(x-y for x, y in zip(at, bt)) == (Decimal(20),)*4
        assert at[2]-at[1] == Decimal('1.48')
        assert at[1]-at[0] == at[3]-at[2] == Decimal('.02')
        assert after.replace(a[0], b[0]) == before
        assert case['mode_mhz'] == 100 and case['simulation_time_ns'] == 450
        assert case['withdrawal_start_ns'] == 207.05 and case['withdrawal_half_supply_ns'] == 207.06
        clock = re.search(r'^VPLL PLLOUT 0 PULSE\(0 \{VDD\} 0n 200p 200p ([0-9.]+)n ([0-9.]+)n\)$', after, re.M)
        plateau, period = map(Decimal, clock.groups())
        assert period == 10 and plateau+Decimal('.2') == period/2
        assert at[0]-bt[0] == 2*period and at[3] < Decimal('210')
        assert '.tran 5p 450n 0 5p' in after
        assert float(re.search(r'^\.param VDD=([0-9.]+)$', after, re.M)[1]) == case['supply_v']
        assert float(re.search(r'^\.options device temp=([-0-9.]+)$', after, re.M)[1]) == case['temperature_c']
        assert re.search(r'^\.lib .+ (tt|ff|ss|sf|fs)$', after, re.M)[1] == case['corner']
    assert found == set(product(('tt', 'ff', 'ss', 'sf', 'fs'), (1.62, 1.8, 1.95), (-40, 27, 125), (-250, 250), (20, 200)))
    verify(pins)
    result = {'deck_preparation_audit_pass': True, 'prepared_cases': 180,
              'exact_cartesian_coverage_verified': True, 'only_command_withdrawal_shifted': True,
              'withdrawal_shift_ns': 20, 'clock_period_ns': 10, 'simulation_time_ns': 450,
              'unique_evidence_pins_verified': len(pins), 'sha256': pins,
              'native_simulation_launched': False, 'loaded_event_behavior_validation_pending': True,
              'release_qualified': False, 'selected': False,
              'scope': 'Exact180-deck100MHz preparation/identity audit only. Same physical circuit/RC/clocks; '
                       'actual loaded-event/fresh/stale/control/PVT behavior remains unqualified.'}
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'sha256'}))


if __name__ == '__main__':
    main()
