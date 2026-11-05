#!/usr/bin/env python3
"""Audit complete cell-RC extraction and its exact transistor-LVS projections."""
import argparse
import json
import re
from pathlib import Path
from characterize_bbpd import sha, verify
from collapse_cell_rc import collapse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cells', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cells, fixture = args.cells.resolve(), args.fixture.resolve()
    receipt = fixture / 'extraction.json'
    assessment = json.loads(receipt.read_text())
    verify(assessment['sha256'])
    assert sha(fixture / 'receiver.spice') == assessment['receiver_sha256']
    types = json.loads((cells / 'selected_types.json').read_text())
    assert set(types) == set(assessment['cell_capacitors']) == set(assessment['cell_resistors'])
    log = (cells / 'magic.log').read_text()
    assert not any(error in log for error in ('Usage:', 'Error parsing', 'Cannot open file'))
    sections = re.findall(r'Processing cell (\S+) for resistance extraction\.\n'
                          r'([\s\S]*?)(?=Processing cell \S+ for resistance extraction\.|\Z)', log)
    assert [name for name, _ in sections] == types
    counts = json.loads((cells / 'model_counts.json').read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    reports = {}
    for typ, section in sections:
        statistics = re.findall(r'Total Nets: (\d+)\s+Nets extracted: (\d+) [^\n]*\n'
                                r'Nets output: (\d+) [^\n]*', section)
        assert statistics, ('Missing extraction statistics', typ)
        total, extracted, emitted = map(int, statistics[-1])
        assert total > 0 and total == extracted == emitted, ('Partial resistance extraction', typ)
        regenerated = args.output / (typ + '.mos.spice')
        actual = collapse(cells / (typ + '.spice'), regenerated)
        assert actual == counts[typ]
        assert regenerated.read_bytes() == (cells / (typ + '.mos.spice')).read_bytes()
        assert actual['resistors'] == assessment['cell_resistors'][typ]
        assert actual['capacitors'] == assessment['cell_capacitors'][typ]
        native = (cells / (typ + '.native.log')).read_text()
        lvs = (cells / (typ + '.lvs.log')).read_text()
        assert 'Circuits match uniquely.' in native and 'LVS Done.' in native
        assert 'Final result: Circuits match uniquely.' in lvs and 'Property errors were found.' not in lvs
        comparison = [c for c in json.loads((cells / (typ + '.lvs.json')).read_text())
                      if c.get('name') == [typ, typ]]
        assert len(comparison) == 1
        comparison = comparison[0]
        assert not comparison.get('badnets') and not comparison.get('badelements')
        assert comparison['devices'][0] == comparison['devices'][1]
        assert comparison['pins'][0] == comparison['pins'][1]
        reports[typ] = {**actual, 'extracted_nets': total,
                        'regenerated_mos_sha256': sha(regenerated)}
    assert 'Property errors were found.' in (cells / 'negative_width.lvs.log').read_text()
    verify(assessment['sha256'])
    report = {'all_cells_complete_net_extraction_pass': True,
              'all_regenerated_mos_views_match_native_lvs_inputs': True,
              'all_cell_topology_width_length_lvs_pass': True,
              'wrong_width_control_rejected': True, 'models': reports,
              'source_assessment_sha256': sha(receipt),
              'auditor_sha256': sha(Path(__file__)), 'release_qualified': False,
              'limitations': assessment['limitations']}
    (args.output / 'assessment.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'cell_types': len(types), 'complete_net_extraction_pass': True,
                      'native_lvs_projection_pass': True}, indent=2))


if __name__ == '__main__':
    main()
