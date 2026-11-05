#!/usr/bin/env python3
"""Independently verify a mode-aware loaded-reset receipt, full clock schedule and evidence."""
import argparse
import hashlib
import json
import math
import re
from decimal import Decimal, ROUND_HALF_EVEN
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode-mhz', type=int, choices=(100,250,300,400,450), required=True)
    parser.add_argument('--withdraw-start-ns', type=float, choices=(187.05,207.05), required=True)
    args = parser.parse_args()
    assert not args.output.exists(), args.output
    cache = {}

    def digest(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def verify(path, expected):
        actual = digest(path)
        assert actual == expected, (str(path), expected, actual)
        assert str(path) not in cache or cache[str(path)] == actual
        cache[str(path)] = actual

    def read(path):
        path = path.resolve()
        value = json.loads(path.read_text())
        verify(path, digest(path))
        for key in ('sha256', 'source_pins', 'input_pins', 'artifacts'):
            for source, expected in value.get(key, {}).items():
                assert isinstance(expected, str), (key, source)
                verify(source, expected)
        return value

    directory = args.directory.resolve()
    terminal = read(directory / 'assessment.json')
    assert terminal['withdrawal_start_ns'] == args.withdraw_start_ns
    assert args.withdraw_start_ns == 187.05 or args.mode_mhz == 100
    assert terminal['mode_mhz'] == args.mode_mhz
    assert terminal['native_completed'] and terminal['terminal_checks_pass']
    assert terminal['independent_consumption_audit_pass']
    assert terminal['direction_control_rejected']
    assert len(terminal['commands']) == 4
    for command in terminal['commands']:
        argv = command['argv']
        assert argv[argv.index('--mode-mhz') + 1] == str(args.mode_mhz)
        assert float(argv[argv.index('--withdraw-start-ns') + 1]) == args.withdraw_start_ns
        assert command['exit_code'] == 0
        verify(command['log'], command['log_sha256'])
    native = read(directory / 'native_audit.json')
    assert native['withdrawal_start_ns'] == args.withdraw_start_ns
    duration_ns = 350 if args.mode_mhz == 450 else 450
    assert native['mode_mhz'] == args.mode_mhz
    assert native['simulation_time_ns'] == duration_ns
    assert native['native_complete_wave_audit_pass']
    assert native['macro_reset_released'] and native['event_storage_exercised']
    replay = read(directory / 'rtl_replay/assessment.json')
    assert replay['withdrawal_start_ns'] == args.withdraw_start_ns
    assert replay['pass'] and replay['exit_code'] == 0
    assert replay['mode_mhz'] == args.mode_mhz
    assert replay['simulation_time_ns'] == duration_ns
    assert not replay['negative_control']
    consumption = read(directory / 'consumption_audit.json')
    assert consumption['withdrawal_start_ns'] == args.withdraw_start_ns
    verify(directory / 'consumption_audit.json', terminal['consumption_audit_sha256'])
    assert consumption['mode_mhz'] == args.mode_mhz
    assert consumption['simulation_time_ns'] == duration_ns
    assert consumption['pass'] and consumption['physical_storage_loaded_before_withdrawal']
    assert not consumption['stale_events_after_reset_before_next_ref']
    assert not consumption['opposite_events']
    direction = 'UP' if consumption['phase_ps'] > 0 else 'DN'
    assert consumption['expected_direction'] == direction
    assert abs(abs(consumption['phase_ps']) - 250) < 1e-8
    for key in ('pre_withdrawal_consumed_events', 'fresh_events'):
        assert len(consumption[key]) == 1 and consumption[key][0][0] == direction
    fresh_time = consumption['fresh_events'][0][1]
    assert consumption['consumption_window_ns'][0] <= fresh_time <= consumption['consumption_window_ns'][1]
    control = read(directory / 'direction_control/assessment.json')
    assert control['withdrawal_start_ns'] == args.withdraw_start_ns
    verify(directory / 'direction_control/assessment.json', terminal['direction_control_sha256'])
    assert not control['pass'] and control['exit_code'] != 0
    assert control['negative_control_rejected']
    # Resolve the actual native deck through the first audited command.
    argv = terminal['commands'][0]['argv']
    native_directory = Path(argv[argv.index('--directory') + 1]).resolve()
    original = read(native_directory / 'assessment.json')
    assert original['simulation_completed'] and original['exit_code'] == 0
    manifest = read(native_directory / 'input_manifest.json')
    verify(native_directory / 'input_manifest.json', original['input_manifest_sha256'])
    deck_path = native_directory / 'loaded.cir'
    assert str(deck_path) in cache
    deck = deck_path.read_text()
    pulse = re.search(r'^VCOMMAND COMMAND_RUN 0 PWL\(0 \{VDD\} ([0-9.]+)n \{VDD\} ([0-9.]+)n 0 ([0-9.]+)n 0 ([0-9.]+)n \{VDD\}\)$', deck, re.M)
    assert pulse
    start = Decimal(str(args.withdraw_start_ns))
    assert tuple(map(Decimal, pulse.groups())) == (start, start+Decimal('.02'), start+Decimal('1.50'), start+Decimal('1.52'))
    assert f'.tran 5p {duration_ns}n 0 5p' in deck
    clock = re.search(r'^VPLL PLLOUT 0 PULSE\(0 \{VDD\} 0n 200p 200p ([0-9.]+)n ([0-9.]+)n\)$', deck, re.M)
    assert clock
    plateau, period = map(Decimal, clock.groups())
    assert abs(period * args.mode_mhz - 1000) < Decimal('0.0000003')
    assert abs(plateau + Decimal('.2') - period / 2) < Decimal('0.000000001')
    supply = float(re.search(r'^\.param VDD=([0-9.]+)$', deck, re.M)[1])
    phase = (float(re.search(r'^VDIV CLKDIVR 0 PULSE\(0 \{VDD\} ([0-9.]+)n ', deck, re.M)[1]) - 10) * 1000
    pvt = {'corner': re.search(r'^\.lib .+ (tt|ff|ss|sf|fs)$', deck, re.M)[1],
           'supply_v': supply,
           'temperature_c': float(re.search(r'^\.options device temp=([-0-9.]+)$', deck, re.M)[1])}
    assert native['pvt'] == pvt
    assert consumption['supply_v'] == replay['supply_v'] == supply
    assert abs(consumption['phase_ps'] - phase) < 1e-8
    assert abs(replay['phase_ps'] - phase) < 1e-8
    for record in (manifest, original):
        if 'pvt' in record:
            assert record['pvt'] == pvt
        if args.withdraw_start_ns == 207.05:
            assert record['withdrawal_start_ns'] == args.withdraw_start_ns
        if 'mode_mhz' in record:
            assert record['mode_mhz'] == args.mode_mhz
    # Derive every half-supply input-clock transition independently with Decimal.
    expected = []
    for cycle in range(math.ceil(Decimal(duration_ns) / period) + 1):
        for offset, value in ((Decimal('.1'), 1), (plateau + Decimal('.3'), 0)):
            tick = int(((cycle * period + offset) * 1000000).to_integral_value(rounding=ROUND_HALF_EVEN))
            if tick < duration_ns * 1000000:
                expected.append((tick, value))
    bench = directory / 'rtl_replay/replay.v'
    assert str(bench) in cache
    tick = 0
    observed = []
    for delay, signal, value in re.findall(r"#([0-9]+\.[0-9]+) ([a-z0-9_]+)=1'b([01]);", bench.read_text()):
        tick += int(Decimal(delay) * 1000000)
        if signal == 'pll':
            observed.append((tick, int(value)))
    assert observed == expected
    assert len(observed) == replay['pll_edges_replayed']
    assert 0 < duration_ns * 1000000 - observed[-1][0] <= float(period) * 500000 + 1
    assert control['mode_mhz'] == args.mode_mhz and control['simulation_time_ns'] == duration_ns
    assert control['negative_control']
    assert control['pll_edges_replayed'] == len(observed)
    storage = consumption['fresh_storage_edges_ns']
    assert len(storage) >= 2 and storage[0][1] == 1 and storage[1][1] == 0
    assert consumption['consumption_window_ns'][0] < storage[0][0] < storage[1][0]
    assert abs(consumption['consumption_window_ns'][1] - (storage[1][0] - 1e-6)) < 1e-8
    assert replay['consumption_window_ns'] == consumption['consumption_window_ns']
    assert replay['fresh_storage_edges_ns'] == storage
    assert consumption['event_reset_assert_ns'] < consumption['macro_reset_assert_ns'] < consumption['macro_reset_release_ns'] < consumption['next_ref_opportunity_ns']
    assert abs(replay['macro_release_after_withdrawal_ns'] - consumption['macro_reset_release_ns']) < 1e-8
    log = (directory / 'rtl_replay/run.log').read_text()
    events = [[name, float(t)] for name, t in re.findall(r'accepted_(UP|DN) time_ns=([0-9.]+)', log)]
    assert events == consumption['consumed_events']
    assert events == sorted(events, key=lambda event: event[1])
    assert all(name == direction and 0 <= t <= duration_ns for name, t in events)
    lower, upper = consumption['consumption_window_ns']
    assert [event for event in events if lower <= event[1] <= upper] == consumption['fresh_events']
    assert not [event for event in events if consumption['event_reset_assert_ns'] <= event[1] < lower]
    verify(Path(__file__).resolve(), digest(Path(__file__)))
    # Recheck after reading all receipts, rather than trusting cached digests.
    for path, expected in list(cache.items()):
        verify(path, expected)
    result = {
        'pass': True, 'observed_utc': datetime.now(timezone.utc).isoformat(),
        'terminal_directory': str(directory), 'unique_evidence_pins_verified': len(cache),
        'consumption': {k: v for k, v in consumption.items() if k != 'sha256'},
        'sha256': cache, 'release_qualified': False, 'selected': False,
        'withdrawal_start_ns':args.withdraw_start_ns,'mode_mhz': args.mode_mhz, 'pvt': pvt, 'simulation_time_ns': duration_ns,
        'pll_edges_independently_verified': len(observed),
        'last_pll_edge_ns': observed[-1][0] / 1e6,
        'scope': 'One completed deterministic mode-aware loaded-reset case; fixed RC and ideal committed controls; preserves receipt limitations; no MTBF or wholePLL proof.',
    }
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('pass', 'unique_evidence_pins_verified', 'terminal_directory')}))


if __name__ == '__main__':
    main()
