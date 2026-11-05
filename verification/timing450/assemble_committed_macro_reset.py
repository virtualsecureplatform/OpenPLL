#!/usr/bin/env python3
"""Reuse pinned physical RC cell definitions for the explicit committed-bundle fixture."""
import argparse
import json
import re
from pathlib import Path
from characterize_bbpd import sha, verify
from add_macro_reset_cell_rc import subcircuits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--physical-model-fixture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    fixture, physical = args.fixture.resolve(), args.physical_model_fixture.resolve()
    graph_path, model_path = fixture/'extraction.json', physical/'extraction.json'
    graph, models = json.loads(graph_path.read_text()), json.loads(model_path.read_text())
    verify(graph['sha256']); verify(models['sha256'])
    assert sha(physical/'receiver.spice') == models['receiver_sha256']
    assert models['fixed_model_corner'] == 'ss' and models['fixed_model_temperature_c'] == 125
    assert models['cell_topology_width_length_lvs_pass'] and models['diode_model_equivalence_screen_passed']
    raw = (fixture/'receiver.spice').read_text()
    old = (physical/'receiver.spice').read_text()
    source_definitions, physical_definitions = subcircuits(raw), subcircuits(old)
    used = {v['type'] for v in graph['selected_cells'].values()}
    assert used <= physical_definitions.keys()
    for typ in used:
        assert source_definitions[typ][0] == physical_definitions[typ][0]
    end = re.search(r'^\.ends bbpd_receiver_cdc[^\n]*\n', raw, re.M).end()
    old_end = re.search(r'^\.ends bbpd_receiver_cdc[^\n]*\n', old, re.M).end()
    result = raw[:end] + old[old_end:]
    definitions = subcircuits(result)
    assert definitions['bbpd_receiver_cdc'] == source_definitions['bbpd_receiver_cdc']
    assert all(definitions[t] == v for t,v in physical_definitions.items() if t != 'bbpd_receiver_cdc')
    base = Path(__file__).resolve().parents[2]/'build/timing450/interface_characterization'
    prior_path = base/'receiver_macro_reset_fixture_v7/extraction.json'
    prior = json.loads(prior_path.read_text()); verify(prior['sha256'])
    assert all(prior['selected_cells'][n] == v for n,v in graph['selected_cells'].items())
    receiver_path = base/'receiver_reset_fixture_rc/extraction.json'
    # The smaller RC receipt pins its extraction rather than duplicating mapped cells.
    assert receiver_path.exists()
    pins = {**graph['sha256'], **models['sha256'], **prior['sha256']}
    for p in (graph_path, model_path, physical/'receiver.spice', prior_path,
              receiver_path, Path(__file__).resolve(), Path(__file__).with_name('add_macro_reset_cell_rc.py'),
              Path(__file__).with_name('characterize_bbpd.py')):
        pins[str(p.resolve())] = sha(p)
    verify(pins)
    args.output.mkdir(parents=True, exist_ok=False)
    target = args.output/'receiver.spice'; target.write_text(result)
    report = {'sha256': pins, 'receiver_sha256': sha(target),
              'mapped_cells': len(graph['selected_cells']), 'used_cell_types': len(used),
              'mapped_connections_match_expanded_source': True,
              'physical_definitions_unchanged': True, 'external_routed_rc_unchanged': True,
              'fixed_model_corner': 'ss', 'fixed_model_temperature_c':125,
              'release_qualified':False, 'selected':False,
              'limitations': graph['limitations'] + models['limitations']}
    (args.output/'extraction.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('sha256','limitations')}))


if __name__ == '__main__':
    main()
