#!/usr/bin/env python3
"""Verify full-clock UP/DN pilot regressions, including independent edge scheduling."""
import json
import math
import re
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from characterize_bbpd import sha, verify


def main():
    root = Path('build/timing450/interface_characterization').resolve()
    output = root / 'receiver_loaded_reset_full_clock_regression_001.json'
    assert not output.exists()
    pins = {}

    def read(path):
        value = json.loads(path.read_text())
        for key in ('sha256', 'artifacts', 'source_pins'):
            for source, digest in value.get(key, {}).items():
                assert source not in pins or pins[source] == digest
                pins[source] = digest
        pins[str(path)] = sha(path)
        return value

    records = {}
    for suffix, direction in (('ss125', 'UP'), ('ss125_dn', 'DN')):
        name = 'receiver_loaded_macro_reset_' + suffix
        native = root / name
        replay_dir = root / (name + '_full_clock_replay_v2_001')
        control_dir = root / (name + '_full_clock_direction_control_v2_001')
        replay = read(replay_dir / 'assessment.json')
        consumption = read(root / (name + '_full_clock_consumption_v2_001.json'))
        control = read(control_dir / 'assessment.json')
        assert replay['pass'] and replay['exit_code'] == 0
        assert consumption['pass'] and consumption['expected_direction'] == direction
        assert consumption['physical_storage_loaded_before_withdrawal']
        assert consumption['consumed_events'] == [[direction, t] for t in (180.1, 300.1, 340.1)]
        assert consumption['fresh_events'] == [[direction, 300.1]]
        assert not consumption['stale_events_after_reset_before_next_ref'] and not consumption['opposite_events']
        assert control['negative_control_rejected'] and not control['pass'] and control['exit_code'] != 0
        deck_path = native / 'loaded.cir'
        deck = deck_path.read_text()
        plateau, period = map(Decimal, re.search(
            r'^VPLL PLLOUT 0 PULSE\(0 \{VDD\} 0n 200p 200p ([\d.]+)n ([\d.]+)n\)$', deck, re.M).groups())
        expected = []
        for cycle in range(math.ceil(Decimal(350) / period) + 1):
            for offset, value in ((Decimal('.1'), 1), (plateau + Decimal('.3'), 0)):
                time_fs = int(((cycle * period + offset) * 1000000).to_integral_value(rounding=ROUND_HALF_EVEN))
                if time_fs < 350000000:
                    expected.append((time_fs, value))
        time_fs = 0
        observed = []
        bench = replay_dir / 'replay.v'
        for delay, signal, value in re.findall(r"#([0-9]+\.[0-9]+) ([a-z0-9_]+)=1'b([01]);", bench.read_text()):
            time_fs += int(Decimal(delay) * 1000000)
            if signal == 'pll':
                observed.append((time_fs, int(value)))
        assert observed == expected and len(observed) == replay['pll_edges_replayed']
        assert 0 < 350000000 - observed[-1][0] <= float(period) * 500000 + 1
        pins[str(deck_path)] = sha(deck_path)
        pins[str(bench)] = sha(bench)
        records[direction] = {'pass': True, 'pll_edges_independently_verified': len(observed),
                              'last_pll_edge_ns': observed[-1][0] / 1e6,
                              'consumed_events': consumption['consumed_events'],
                              'fresh_events': consumption['fresh_events'], 'direction_control_rejected': True}
    pins[str(Path(__file__).resolve())] = sha(Path(__file__))
    verify(pins)
    result = {'pass': True, 'records': records, 'unique_evidence_pins_verified': len(pins),
              'sha256': pins, 'release_qualified': False, 'selected': False,
              'scope': 'Two completed SS125/450MHz pilots with full350ns clock schedule. '
                       'Lower modes and all physical/MTBF/wholePLL qualification remain pending.'}
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'sha256'}))


if __name__ == '__main__':
    main()
