"""Prepare a physical AOI/buffer/DCO-input load cut, with explicit boundary scope."""
import argparse
import json
from pathlib import Path

from common_v3 import save, sha, verify
from compare_prototype_physical_primitive_graphs import Union
from plan_selected_detector_passive_cut import passive_cut, RAILS
from extend_selected_detector_loads import full_load_cells


def run(upstream, inventory, model, role, output):
    if output.exists(): raise FileExistsError(output)
    u, i = [json.loads(p.read_text()) for p in (upstream, inventory)]
    for x in (u, i): verify(x['input_sha256'])
    if u['input_sha256'].get(str(inventory)) != sha(inventory): raise ValueError('same programming inventory required')
    paths = [Path(p) for p in i['input_sha256'] if p.endswith('/nodes.json')]
    if len(paths) != 1: raise ValueError('unique physical primitive metadata required')
    metadata = paths[0]
    items = {r['instance']: r for r in json.loads(metadata.read_text())['physical_instances']}
    r = u['controls'][role]
    if set(r['upstream_input_drivers']) != {'A'}: raise ValueError('single input output buffer required')
    logic = r['upstream_input_drivers']['A']['driver']
    if logic['master'] != 'sky130_fd_sc_hs__a21oi_4': raise ValueError('selected AOI4 path required')
    selected = set(logic['primitives']) | set(r['upstream_driver']['primitives']) | set(r['programming_inverter']['primitives'])
    receivers = i['controls'][role]['physical_receivers']
    if len(receivers) != 1 or receivers[0]['master'] != 'sky130_fd_sc_hd__einvp_1':
        raise ValueError('one physical enable-inverter load required')
    key = receivers[0]['cell_key']
    load = {n for n,x in items.items() if json.dumps([x['physical_hierarchy_identity'],x['leaf_master']], separators=(',', ':')) == key}
    if len(load) != 6: raise ValueError('complete six-device enable inverter required')
    selected |= load
    terms = {}; passives = []; union = Union(); inside = False
    for line in model.open():
        f = line.split()
        if not f: continue
        if f[0].lower() == '.subckt': inside = f[1] == 'IntegerPLL_400MHz_PrototypeTop'; continue
        if f[0].lower() == '.ends': inside = False; continue
        if not inside: continue
        if f[0].startswith('Xflat'):
            count = len(items[f[0]]['local_primitive_signature'][1]); terms[f[0]] = f[1:count+1]
        elif f[0][0].upper() in ('R', 'C'):
            passives.append((f[0], f[1], f[2]))
            if f[0][0].upper() == 'R': union.join(f[1], f[2])
    if terms.keys() != items.keys(): raise ValueError('complete native primitive graph required')
    load_pins = {}
    for name in load:
        for pin, node in zip(items[name]['local_primitive_signature'][1], terms[name]):
            if pin not in ('A', 'Z', 'TE'): continue
            if pin in load_pins and load_pins[pin] != node: raise ValueError('ambiguous physical load pin')
            load_pins[pin] = node
    if set(load_pins) != {'A', 'Z', 'TE'}: raise ValueError('complete load interface required')
    inputs = {p:logic['pins'][p] for p in ('A1','A2','B1')}
    observed = dict(logic_output=logic['pins']['Y'], buffer_output=r['upstream_driver']['pins']['Y'],
                    DCO_input=r['programming_inverter']['pins']['A'], enable_output=r['programming_inverter']['pins']['Y'])
    prescribed = set(inputs.values()) | {load_pins['A'],load_pins['Z']}
    driven_components = {union.find(n) for n in observed.values()}
    attached = {n:[] for n,nodes in terms.items() if n not in selected and any(union.find(v) in driven_components for v in nodes)}
    original_selected = set(selected)
    selected, additional_masters = full_load_cells(selected, attached, items)
    if len(selected) > 200: raise ValueError('unexpectedly large loaded-path closure')
    private, boundary, cards, omitted = passive_cut(terms, passives, selected, prescribed)
    if omitted: raise ValueError('unretained active devices share a private node')
    if not set(observed.values()) <= private: raise ValueError('observed output clamped')
    driven_components = {union.find(n) for n in observed.values()}
    if any(union.find(n) in driven_components for n in boundary):
        raise ValueError('ideal boundary clamps a driven output through finite resistance')
    paths = [upstream, inventory, metadata, model, Path(__file__).resolve(),
             Path(__file__).with_name('plan_selected_detector_passive_cut.py'),
             Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py'),Path(__file__).with_name('extend_selected_detector_loads.py')]
    pins = {str(p):sha(p) for p in paths}; verify(pins)
    save(output, dict(input_sha256=pins, role=role, logic_inputs=inputs, observed_roles=observed,
         conditional_receiver_phase_pins={p:load_pins[p] for p in ('A','Z')},
         selected_primitives=sorted(selected), added_load_cell_masters=additional_masters, added_load_primitives=sorted(selected-original_selected), private_unknown_nodes=sorted(private),
         required_non_supply_boundary_voltage_nodes=sorted(boundary),
         retained_passive_cards=[passives[x][0] for x in sorted(cards)],
         omitted_primitives_touching_private_nodes=omitted,
         all_incident_passives_retained=True, floating_capacitor_nodes_preserved=True,
         outputs_not_clamped_directly_or_through_finite_resistance=True,
         receiver_input_and_output_phase_conditioned=True, exterior_coupling_boundary_qualified=False,
         native_behavior_qualified=False, release_ready=False))
    print(json.dumps(dict(primitives=len(selected), private_nodes=len(private), boundary_nodes=len(boundary), passives=len(cards))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('upstream','inventory','model','output'): p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--role',default='DCO_THERM[226]'); a=p.parse_args()
    run(a.upstream.resolve(),a.inventory.resolve(),a.model.resolve(),a.role,a.output.resolve())
