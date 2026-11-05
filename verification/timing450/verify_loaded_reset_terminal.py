#!/usr/bin/env python3
"""Independently verify a completed loaded-reset receipt and all its pinned evidence."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
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
    assert terminal['native_completed'] and terminal['terminal_checks_pass']
    assert terminal['independent_consumption_audit_pass']
    assert terminal['direction_control_rejected']
    assert len(terminal['commands']) == 4
    for command in terminal['commands']:
        assert command['exit_code'] == 0
        verify(command['log'], command['log_sha256'])
    native = read(directory / 'native_audit.json')
    assert native['native_complete_wave_audit_pass']
    assert native['macro_reset_released'] and native['event_storage_exercised']
    replay = read(directory / 'rtl_replay/assessment.json')
    assert replay['pass'] and replay['exit_code'] == 0
    consumption = read(directory / 'consumption_audit.json')
    verify(directory / 'consumption_audit.json', terminal['consumption_audit_sha256'])
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
    verify(directory / 'direction_control/assessment.json', terminal['direction_control_sha256'])
    assert not control['pass'] and control['exit_code'] != 0
    assert control['negative_control_rejected']
    verify(Path(__file__).resolve(), digest(Path(__file__)))
    # Recheck after reading all receipts, rather than trusting cached digests.
    for path, expected in list(cache.items()):
        verify(path, expected)
    result = {
        'pass': True, 'observed_utc': datetime.now(timezone.utc).isoformat(),
        'terminal_directory': str(directory), 'unique_evidence_pins_verified': len(cache),
        'consumption': {k: v for k, v in consumption.items() if k != 'sha256'},
        'sha256': cache, 'release_qualified': False, 'selected': False,
        'scope': 'One completed deterministic 450MHz loaded-reset case; preserves source receipt limitations.',
    }
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('pass', 'unique_evidence_pins_verified', 'terminal_directory')}))


if __name__ == '__main__':
    main()
