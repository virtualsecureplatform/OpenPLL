"""Bind isolated child wire R to assembled primitives by exact local placement.

Extra exported capacitance ports are not treated as physical macro ports.
Matching uses native placement paths, local primitive cards and parallel
multiplicity. The result inventories parent/child port junctions; it does not
insert R, add SPEF C, or qualify capacitor placement or native behavior.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
from common_v3 import save, sha, verify
from compare_prototype_physical_primitive_graphs import parsed, expand, use_table
from bind_prototype_spef_pins_v2 import hierarchy, bind
from convert_prototype_ng47_diode_geometry import convert, check, MODEL
from build_prototype_context_parent_wire_R import source_inventory


def key(value):
    return json.dumps(value, separators=(',', ':'))


def unescape(name):
    result = []; index = 0
    while index < len(name):
        if name[index] == chr(92):
            index += 1
            if index == len(name):
                raise ValueError('unterminated escaped instance name')
        result.append(name[index]); index += 1
    return ''.join(result)


def match(primitives, alias, metadata, global_terminals, master, port_targets):
    selected = {}
    for item in metadata['physical_instances']:
        identity = item['physical_hierarchy_identity']
        if not identity or identity[0][2][0] != master:
            continue
        physical = key((identity[1:], item['leaf_master'], item['local_primitive_signature'], item['parallel_ordinal']))
        if physical in selected:
            raise ValueError('ambiguous assembled child primitive placement')
        selected[physical] = item['instance']
    if set(selected) != {key(k) for k in primitives}:
        raise ValueError('isolated and assembled child primitive coverage or local cards differ')
    forward, reverse = {}, {}
    def pair(a, b):
        a = alias.find(a)
        if (a in forward and forward[a] != b) or (b in reverse and reverse[b] != a):
            raise ValueError('child conductor mapping is not bijective')
        forward[a] = b; reverse[b] = a
    for physical, (_, nodes, _) in primitives.items():
        instance = selected[key(physical)]
        other = global_terminals[instance]
        if len(nodes) != len(other):
            raise ValueError('primitive terminal arity differs')
        for a, b in zip(nodes, other):
            pair(a, b)
    for pin, target in port_targets.items():
        pair(pin, target)
    return forward, selected


def run(rc, reference, binding, frame, role, output):
    receipts = [p / 'assessment.json' for p in (rc, reference, binding, frame)]
    cr, rr, br, fr = records = [json.loads(p.read_text()) for p in receipts]
    for record in records:
        verify(record['input_sha256']); verify(record['artifacts'])
    if not cr['all_RC_terminals_bound_and_connected'] or not cr['all_instance_placements_match']:
        raise ValueError('complete isolated placed wire binding required')
    if br['input_sha256'].get(str(receipts[1])) != sha(receipts[1]):
        raise ValueError('parent wire binding refers to another assembled basis')
    macro = fr['macro_sources'][role]; top = macro['master']; gds = Path(macro['gds']); lef = Path(macro['lef'])
    if cr['input_sha256'].get(str(gds)) != sha(gds) or fr['input_sha256'].get(str(gds)) != sha(gds):
        raise ValueError('isolated wire extraction and assembled child GDS differ')
    candidates = [Path(p) for p in cr['input_sha256'] if p.endswith('/' + top + '/capacitance.spice')]
    if len(candidates) != 1:
        raise ValueError('one isolated native hierarchy required')
    source = candidates[0]; folder = source.parent; joinfile = rc / 'join.json'
    metadata_file = reference / 'nodes.json'; model = reference / 'context.spice'
    parent_files = [binding / (c + '.wire_interfaces.json') for c in ('min', 'nom', 'max')]
    spef_files = [rc / (c + '.json') for c in ('min', 'nom', 'max')]
    dependencies = ('compare_prototype_physical_primitive_graphs.py', 'bind_prototype_spef_pins_v2.py',
                    'convert_prototype_ng47_diode_geometry.py', 'prepare_prototype_analog_reference.py',
                    'build_prototype_context_parent_wire_R.py')
    paths = [*receipts, source, gds, lef, joinfile, metadata_file, model, *parent_files, *spef_files,
             *folder.glob('*.ext'), Path(__file__).resolve(), *[Path(__file__).with_name(n) for n in dependencies]]
    pins = {str(p): sha(p) for p in paths}
    physical_ports = set(re.findall(r'^\s*PIN\s+(\S+)\s*$', lef.read_text(), re.M))
    original = source.read_text(); text = original
    diode_translation = None
    if MODEL in text:
        text, _ = convert(text); diode_translation = check(original, text, top)
    ports, primitives, alias, _, _ = expand(parsed(text), top, folder)
    if not physical_ports or not physical_ports <= set(ports):
        raise ValueError('isolated hierarchy lacks named physical macro ports')
    metadata = json.loads(metadata_file.read_text())
    global_terms, _, _ = source_inventory(model.read_text().splitlines())
    parent_nominal = json.loads(parent_files[1].read_text())['networks']
    targets, accesses, macro_instances = {}, {}, set()
    for net in parent_nominal:
        for terminal in net['terminals']:
            if terminal['kind'] != 'I' or terminal['cell_model'] != top:
                continue
            instance, pin = terminal['node'].rsplit(':', 1)
            macro_instances.add(instance)
            if pin in targets and targets[pin] != net['context_conductor']:
                raise ValueError('physical child macro port has conflicting parent conductors')
            targets[pin] = net['context_conductor']
            accesses[pin] = dict(parent_net=net['net'], parent_wire_terminal=terminal['node'])
    if len(macro_instances) != 1:
        raise ValueError('one placed child macro interface required')
    fixed = {metadata['original_to_emitted'][n] for n in metadata['original_fixed_supply_nodes']} | {'0'}
    for pin in ('VGND', 'VNB', 'VPB', 'VPWR'):
        if pin in physical_ports:
            targets.setdefault(pin, metadata['original_to_emitted'][pin])
    if not physical_ports <= targets.keys():
        raise ValueError('physical child port lacks its assembled parent interface')
    forward, paired = match(primitives, alias, metadata, global_terms, top,
                            {p: targets[p] for p in physical_ports})
    scale, uses = use_table(folder, top)
    positions = defaultdict(list)
    for item in metadata['physical_instances']:
        identity = item['physical_hierarchy_identity']
        if not identity or identity[0][2][0] != top:
            continue
        if len(identity) < 2 or identity[1][0] != top or identity[1][1] != scale:
            raise ValueError('child native placement scale differs')
        group = tuple(identity[1][2])
        for i, node in enumerate(global_terms[item['instance']]):
            positions[group, node].append([item['instance'], i])
    placed = {unescape(row['routed_instance']): row['extracted_instance']
              for row in json.loads(joinfile.read_text())['mapping']}
    root_ports, _, root_alias = hierarchy(text, top)
    artifacts, results = {}, []
    verify(pins)
    output.mkdir(parents=True, exist_ok=False)
    for corner, spef_file, parent_file in zip(('min', 'nom', 'max'), spef_files, parent_files):
        # Ensure the physical macro port conductor is invariant across wire corners.
        actual_accesses = {(n['net'], t['node']): n['context_conductor']
                           for n in json.loads(parent_file.read_text())['networks'] for t in n['terminals']}
        if any(actual_accesses[a['parent_net'], a['parent_wire_terminal']] != targets[p] for p, a in accesses.items()):
            raise ValueError('parent macro port conductor differs across wire corners')
        spef = json.loads(spef_file.read_text()); checked = bind(spef, text, top, placed)
        if not checked['all_RC_terminals_bound_and_connected']:
            raise ValueError('isolated wire topology no longer binds')
        networks = []; primitive_positions = set(); instances = 0; junctions = 0
        for wire, logical in zip(spef['nets'], checked['networks']):
            if wire['name'] != logical['net'] or len(logical['logical_nodes']) != 1:
                raise ValueError('one child conductor per wire network required')
            node = root_alias(logical['logical_nodes'][0])
            native = alias.find(node if node in root_ports or node == '0' else top + '/' + node)
            compact = forward[native]; terms = []
            for terminal in logical['terminals']:
                row = dict(terminal, context_conductor=compact, ideal_supply_boundary=compact in fixed)
                if terminal['kind'] == 'P':
                    pin = terminal['node']
                    if pin not in physical_ports or targets[pin] != compact:
                        raise ValueError('child wire port is not the same physical macro port')
                    row['parent_access'] = accesses.get(pin)
                    row['primitive_terminal_positions'] = []
                    if compact not in fixed:
                        if row['parent_access'] is None:
                            raise ValueError('signal child port lacks a parent junction')
                        junctions += 1
                else:
                    instance, pin = terminal['node'].rsplit(':', 1)
                    placement = uses[placed[unescape(instance)]]
                    if placement[0] != terminal['cell_model']:
                        raise ValueError('child physical terminal master differs')
                    found = positions.get((placement, compact), [])
                    if not found and compact not in fixed:
                        raise ValueError('child signal terminal lacks physical primitive incidence')
                    row['primitive_terminal_positions'] = found
                    if compact not in fixed:
                        instances += 1; primitive_positions.update(map(tuple, found))
                terms.append(row)
            networks.append(dict(net=wire['name'], context_conductor=compact,
                                 terminals=terms, resistors=wire['resistors']))
        target = output / (corner + '.child_wire_interfaces.json')
        save(target, dict(networks=networks)); artifacts[str(target)] = sha(target)
        results.append(dict(corner=corner, networks=len(networks),
                            resistors=sum(len(n['resistors']) for n in networks),
                            signal_instance_terminals=instances, primitive_terminal_positions=len(primitive_positions),
                            parent_child_signal_port_junctions=junctions))
    verify(pins)
    mapping = output / 'child_to_context_conductors.json'; save(mapping, forward); artifacts[str(mapping)] = sha(mapping)
    save(output / 'assessment.json', dict(input_sha256=pins, artifacts=artifacts,
        role=role, master=top, matched_physical_primitives=len(paired),
        physical_macro_ports=len(physical_ports), physical_conductor_bijection=len(forward),
        exact_local_primitive_cards_and_placement_paths_matched=True,
        all_physical_macro_ports_anchored=True, instance_counter_identity_assumed=False,
        diode_geometry_translation=diode_translation, results=results,
        child_wire_R_inserted=False, SPEF_C_added=False, capacitor_spatial_attachment_qualified=False,
        loaded_native_model_qualified=False, diagnostic=True, validated_for_prototype=False, release_ready=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('rc', 'reference', 'binding', 'frame', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--role', choices=('oscillator', 'detector'), required=True)
    a = p.parse_args()
    run(a.rc.resolve(), a.reference.resolve(), a.binding.resolve(), a.frame.resolve(), a.role, a.output.resolve())
