"""Locate actual upstream cells driving all 302 DCO programming inverter inputs.

Use extracted physical hierarchy and finite-resistor connectivity, rather than
assuming the digital output load or identifying cells by synthesis counters.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from common_v3 import save, sha, verify
from compare_prototype_physical_primitive_graphs import parsed, Union
from resolve_prototype_loaded_halo_interfaces import local_bindings, library_directions


def run(inventory, output):
    if output.exists(): raise FileExistsError(output)
    original = json.loads(inventory.read_text()); verify(original['input_sha256'])
    def one(suffix):
        paths = [Path(p) for p in original['input_sha256'] if p.endswith(suffix)]
        if len(paths) != 1: raise ValueError('unique physical input required: '+suffix)
        return paths[0]
    metadata, wire, hierarchy = one('/nodes.json'), one('/context.spice'), one('/ng47.spice')
    instances = json.loads(metadata.read_text())['physical_instances']
    cells = {i['instance']: json.dumps([i['physical_hierarchy_identity'], i['leaf_master']], separators=(',', ':')) for i in instances}
    directions = {}; lef_paths = []
    for path in map(Path, original['input_sha256']):
        if path.suffix != '.lef': continue
        lef_paths.append(path)
        for master, ports in library_directions(path.read_text()).items():
            if master in directions and directions[master] != ports: raise ValueError('conflicting cell pin directions')
            directions[master] = ports
    if not lef_paths: raise ValueError('pinned physical library directions required')
    terms = {}; union = Union()
    for line in wire.open():
        f = line.split()
        if not f: continue
        if f[0].startswith('Xflat'):
            stop = next(i for i,t in enumerate(f) if t.startswith('sky130_fd_pr__'))
            terms[f[0]] = f[1:stop]
        elif f[0].startswith('R'):
            union.join(f[1], f[2])
    bound, aliases = local_bindings(instances, terms, cells, parsed(hierarchy.read_text()))
    pins = {}; drivers = defaultdict(list); receivers = defaultdict(list)
    for key, entry in bound.items():
        pins[key] = {}
        for pin, direction in directions.get(entry['master'], {}).items():
            node = entry['nodes'].get(aliases[entry['master']].find(pin))
            if node is None: continue
            pins[key][pin] = node
            if direction == 'OUTPUT': drivers[union.find(node)].append((key, pin))
            elif direction == 'INPUT': receivers[union.find(node)].append((key, pin))
    results = {}
    def describe(key):
        return dict(cell_key=key, master=bound[key]['master'], primitives=bound[key]['primitives'], pins=pins[key])
    for role, control in original['controls'].items():
        node = control['driver_input_node']; component = union.find(node)
        upstream = drivers[component]
        if len(upstream) != 1: raise ValueError('unique upstream physical driver required: '+role)
        key, pin = upstream[0]
        receiver = control['driver']['cell_key']
        if (receiver, 'A') not in receivers[component] or pins[receiver]['A'] != node:
            raise ValueError('actual programming inverter input binding differs')
        results[role] = dict(upstream_driver=describe(key), upstream_output_pin=pin,
            programming_inverter_input_node=node, programming_inverter=control['driver'],
            load_input_pins=[dict(cell=describe(k), pin=p) for k,p in receivers[component]],
            upstream_input_nodes={p:n for p,n in pins[key].items() if directions[bound[key]['master']][p] == 'INPUT'})
    for role, result in results.items():
        result['upstream_input_drivers'] = {}
        for pin, node in result['upstream_input_nodes'].items():
            source = drivers[union.find(node)]
            if len(source) != 1: raise ValueError('unique second upstream driver required: '+role+'/'+pin)
            key, output_pin = source[0]
            result['upstream_input_drivers'][pin] = dict(driver=describe(key), output_pin=output_pin)
    if len(results) != 302: raise ValueError('complete physical programming interface required')
    files = [inventory, metadata, wire, hierarchy, *lef_paths, Path(__file__).resolve(),
             Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py'),
             Path(__file__).with_name('resolve_prototype_loaded_halo_interfaces.py'),
             Path(__file__).with_name('common_v3.py')]
    inputs = {str(p): sha(p) for p in files}; verify(inputs)
    save(output, dict(input_sha256=inputs, controls=results,
        upstream_driver_master_counts=dict(Counter(x['upstream_driver']['master'] for x in results.values())),
        programming_inputs=302, unique_upstream_output_per_input_verified=True,
        actual_inverter_load_connectivity_verified=True,
        physical_hierarchy_identity_used=True, synthesis_counter_identity_assumed=False,
        finite_resistors_used_for_connectivity_only=True,
        physical_load_capacitance_qualified=False, upstream_slew_qualified=False,
        native_behavior_qualified=False, release_ready=False))
    print(json.dumps(dict(programming_inputs=302, upstream_driver_master_counts=dict(Counter(x['upstream_driver']['master'] for x in results.values())))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inventory', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); run(a.inventory.resolve(), a.output.resolve())
