#!/usr/bin/env python3
"""Compare elaborated old/new DCO connectivity before layout experiments."""
from datetime import datetime, timezone
import copy
import json
from pathlib import Path
import subprocess
from prepare_return_fine_range_candidate import BASE_TOP, TOP
from run_dco_qualification import ROOT, sha, save

YOSYS = '/nix/store/4bmfi4470w0i3ixcaidfki18d3fyqvva-yosys-with-plugins-0.62/bin/yosys'


def audit(old, new, indices):
    # Match all existing signal identities through named net aliases, rather
    # than assuming Yosys allocated identical numeric bit IDs in both designs.
    mapping = {}
    for name, net in old['netnames'].items():
        other = new['netnames'][name]
        assert len(net['bits']) == len(other['bits'])
        for a, b in zip(net['bits'], other['bits']):
            assert mapping.setdefault(a, b) == b
    for name, port in old['ports'].items():
        other = new['ports'][name]
        assert port['direction'] == other['direction']
        assert [mapping[b] for b in port['bits']] == other['bits']
    assert old['ports'].keys() == new['ports'].keys()
    for name, cell in old['cells'].items():
        other = new['cells'][name]
        assert cell['type'] == other['type']
        assert cell['parameters'] == other['parameters']
        assert cell['port_directions'] == other['port_directions']
        assert {p: [mapping[b] for b in bits] for p, bits in cell['connections'].items()} == other['connections']
    added = set(new['cells']) - set(old['cells'])
    assert added == {f'gen_return_fine_load[{i}].load' for i in range(80)}
    node = new['netnames']['mirror_pass_n']['bits'][0]
    fine = new['netnames']['DCO_THERM']['bits']
    dummy = new['netnames']['return_fine_dummy']['bits']
    c1_controls = set()
    for name, cell in old['cells'].items():
        if name.startswith('gen_coarse1_fine_load['):
            c1_controls.add(mapping[cell['connections']['TE'][0]])
    # Use the elaborated C1 bank's actual controls, independent of generator math.
    assert len(c1_controls) == 160
    for i, index in enumerate(indices):
        cell = new['cells'][f'gen_return_fine_load[{i}].load']
        assert cell['type'] == 'sky130_fd_sc_hd__einvp_1'
        assert cell['connections'] == {'A': [node], 'TE': [fine[index]], 'Z': [dummy[i]]}
        assert fine[index] not in c1_controls
        for attr in ['keep', 'dont_touch']:
            assert cell['attributes'][attr] == 'true'
    # Each dummy is isolated from every other instance and public port.
    for i, bit in enumerate(dummy):
        uses = [(name, p) for name, cell in new['cells'].items()
                for p, bits in cell['connections'].items() if bit in bits]
        assert uses == [(f'gen_return_fine_load[{i}].load', 'Z')]
        assert all(bit not in p['bits'] for p in new['ports'].values())
    return len(old['cells']), len(new['cells'])


def main():
    base = ROOT / 'build/timing400/release_001'
    plan_path = base / 'return_fine_range_candidate_001/plan.json'
    plan = json.loads(plan_path.read_text())
    out = base / 'return_fine_range_connectivity_001'
    assert not out.exists()
    out.mkdir()
    bb = ROOT / 'sky130/sky130_fd_sc_hd_pll_blackbox.v'
    old_source = ROOT / 'sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_boost8_osc8_load36_c1fine160_sky130.v'
    new_source = Path(plan['candidate_source'])
    assert sha(new_source) == plan['candidate_source_sha256']
    designs = []
    for label, top, source in [('original', BASE_TOP, old_source), ('candidate', TOP, new_source)]:
        script = out / f'{label}.ys'
        script.write_text(f'read_verilog -lib {bb}\nread_verilog -D USE_POWER_PINS {source}\nhierarchy -check -top {top}\nproc\nflatten\nwrite_json {out / (label + ".json")}\n')
        with (out / f'{label}.log').open('w') as log:
            subprocess.run([YOSYS, '-s', str(script)], stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
        designs.append(json.loads((out / f'{label}.json').read_text())['modules'][top])
    old, new = designs
    counts = audit(old, new, plan['control_indices'])
    corrupted = copy.deepcopy(new)
    corrupted['cells']['gen_return_fine_load[0].load']['connections']['TE'] = new['netnames']['DCO_THERM']['bits'][:1]
    rejected = False
    try:
        audit(old, corrupted, plan['control_indices'])
    except AssertionError:
        rejected = True
    assert rejected
    inputs = [Path(__file__).resolve(), plan_path, old_source, new_source, bb]
    save(out / 'assessment.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        input_sha256={str(p): sha(p) for p in inputs}, original_cells=counts[0], candidate_cells=counts[1],
        original_cells_and_connections_preserved=True, public_ports_preserved=True, added_return_loads=80,
        elaborated_control_indices=plan['control_indices'], controls_disjoint_from_existing_c1_bank=True,
        added_output_nodes_isolated=True, keep_attributes_preserved=True, wrong_control_negative_control_rejected=True,
        elaboration_and_connectivity_passed=True, power_pin_insertion_not_validated=True,
        physical_layout_started=False, native_analog_started=False, range_qualified=False,
        release_qualified=False, adopted=False))
    print(f'Elaborated connectivity passed: {counts[0]} original cells preserved, exactly80 isolated return loads added; negative control rejected.')


if __name__ == '__main__':
    main()
