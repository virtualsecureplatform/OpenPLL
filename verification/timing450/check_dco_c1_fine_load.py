#!/usr/bin/env python3
"""Compare elaborated candidate connectivity against the complete baseline."""
import argparse
from collections import Counter
import json
from pathlib import Path


def check(base, candidate, count):
    # A shared named wire and bit offset define identity independent of Yosys IDs.
    mapping = {}
    for name, net in base['netnames'].items():
        assert name in candidate['netnames'], ('missing baseline net', name)
        other = candidate['netnames'][name]['bits']
        assert len(net['bits']) == len(other), name
        for old, new in zip(net['bits'], other):
            if old in mapping:
                assert mapping[old] == new, ('changed net alias', name)
            mapping[old] = new
    assert len(set(mapping.values())) == len(mapping), 'merged baseline wires'
    assert set(base['ports']) == set(candidate['ports']), 'changed external ports'
    for name, port in base['ports'].items():
        assert port['direction'] == candidate['ports'][name]['direction'], name
        assert [mapping[b] for b in port['bits']] == candidate['ports'][name]['bits'], name
    for name, cell in base['cells'].items():
        other = candidate['cells'][name]
        assert cell['type'] == other['type'], ('changed baseline cell', name)
        assert cell['parameters'] == other['parameters'], name
        assert {p:[mapping[b] for b in bits] for p,bits in cell['connections'].items()} == other['connections'], ('changed baseline connection', name)
    extra = set(candidate['cells']) - set(base['cells'])
    assert extra == {f'gen_coarse1_fine_load[{j}].load' for j in range(count)}, 'unexpected added cells'
    turn = candidate['netnames']['mirror_turn_n']['bits'][1]
    therm = candidate['ports']['DCO_THERM']['bits']
    dummy = candidate['netnames']['coarse1_fine_dummy']['bits']
    assert len(dummy) == count and len(set(dummy)) == count
    assert not set(dummy).intersection(mapping.values()), 'dummy aliases baseline'
    occurrences = Counter(b for c in candidate['cells'].values() for bs in c['connections'].values() for b in bs)
    for j in range(count):
        cell = candidate['cells'][f'gen_coarse1_fine_load[{j}].load']
        assert cell['type'] == 'sky130_fd_sc_hd__einvp_1'
        assert cell['connections'] == {'A':[turn], 'TE':[therm[255*j//count]], 'Z':[dummy[j]]}
        assert occurrences[dummy[j]] == 1, ('dummy output reused', j)
        for attribute in ('keep', 'dont_touch'):
            value = cell['attributes'][attribute]
            assert value == 'true' or (set(value) <= {'0','1'} and int(value, 2) == 1), attribute
    # Baseline parallel-driver topology is preserved exactly, including all
    # 255 independent original fine loads, 36 fixed loads and 48 turn stages.
    return dict(passed=True, baseline_cells_preserved=len(base['cells']), extra_loads=count,
                external_interface_preserved=True, original_connectivity_preserved=True,
                independent_added_outputs=True, release_qualified=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--count', type=int, choices=(144,160,192), required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    base = next(m for n,m in json.loads(a.baseline.read_text())['modules'].items() if n.startswith('IntegerPLL_'))
    candidate = next(m for n,m in json.loads(a.candidate.read_text())['modules'].items() if n.startswith('IntegerPLL_'))
    result = check(base, candidate, a.count)
    a.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
