#!/usr/bin/env python3
"""Prepare separate100MHz loaded-reset vectors; never launch analog."""
import json
from pathlib import Path
from characterize_bbpd import sha, verify


def main():
    root = Path('build/timing450/interface_characterization').resolve()
    source = root/'receiver_loaded_reset_all_modes_prepared_001/preparation.json'
    witness_path = root/'receiver_loaded_reset_100MHz_prewithdrawal_condition_audit_001.json'
    recipe = json.loads(source.read_text())
    witness = json.loads(witness_path.read_text())
    assert recipe['prepared_case_count'] == 900
    assert witness['mode_mhz'] == 100 and not witness['loaded_event_precondition_exercised']
    assert len(witness['records']) == 2
    for record in witness['records']:
        assert not record['physical_storage_loaded_before_withdrawal']
        assert record['first_stage_v'] >= .81 and record['final_storage_v'] < .81
    pins = dict(recipe['source_sha256'])
    for path, digest in witness['sha256'].items():
        assert path not in pins or pins[path] == digest
        pins[path] = digest
    for path in (source, witness_path, Path(__file__).resolve()):
        pins[str(path)] = sha(path)
    verify(pins)
    output = root/'receiver_loaded_reset_100MHz_aligned_prepared_001'
    assert not output.exists()
    cases = [case for case in recipe['prepared_cases'] if case['mode_mhz'] == 100]
    assert len(cases) == 180
    output.mkdir()
    prepared = []
    old = '187.05n {VDD} 187.07n 0 188.55n 0 188.57n {VDD}'
    new = '207.05n {VDD} 207.07n 0 208.55n 0 208.57n {VDD}'
    for case in cases:
        original = Path(case['directory'])/'loaded.cir'
        assert sha(original) == case['deck_sha256']
        pins[str(original)] = case['deck_sha256']
        text = original.read_text()
        assert text.count(old) == 1 and new not in text
        assert '.tran 5p 450n 0 5p' in text
        assert '0n 200p 200p 4.800000000n 10.000000000n)' in text
        changed = text.replace(old, new)
        assert changed.replace(new, old) == text
        directory = output/Path(case['directory']).name
        directory.mkdir()
        deck = directory/'loaded.cir'
        deck.write_text(changed)
        prepared.append(dict(case, source_deck=str(original), source_deck_sha256=sha(original),
                             directory=str(directory), deck_sha256=sha(deck),
                             source_withdrawal_start_ns=187.05, withdrawal_start_ns=207.05,
                             withdrawal_half_supply_ns=207.06, withdrawal_end_ns=208.57,
                             simulation_time_ns=450))
    verify(pins)
    result = {'prepared_case_count': 180, 'prepared_cases': prepared,
              'source_sha256': pins, 'mode_mhz': 100,
              'stimulus_change': 'Delay only command withdrawal20ns, two100MHzPLLperiods; preserve1.5ns low width/20psedges. '
                                 'Withdraw before next210nsREF opportunity after first170ns sampled event.',
              'native_simulation_launched': False, 'simulation_completed': False,
              'loaded_event_precondition_validation_pending': True,
              'release_qualified': False, 'selected': False,
              'scope': 'Separate180100MHzPVT/phase/edge deck preparation. All circuit, RC, clocks and native duration '
                       'unchanged; original900-case preparation and active pilots remain immutable. '
                       'Actual loaded/fresh/stale/control/PVT behavior still requires native qualification; '
                       'fixedRC/ideal committed controls/noMTBF/nofullPLL limitations remain.'}
    (output/'preparation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('prepared_cases', 'source_sha256')}))


if __name__ == '__main__':
    main()
