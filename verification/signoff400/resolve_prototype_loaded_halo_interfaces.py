"""Resolve a physical loaded-domain halo's cut pins and direction obligations.

Native local primitive terminals and exact zero-R aliases bind LEF pins to
the same extracted conductors. No boundary voltage or substitute load is
created by this inventory.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from common_v3 import save, sha, verify
from compare_prototype_physical_primitive_graphs import parsed, Union
from inventory_prototype_context_domains import classify
from inventory_prototype_context_interfaces import lef_directions
from prepare_prototype_context_domain_reference import partition


def library_directions(text):
    pattern = re.compile(r'(?ms)^[ \t]*MACRO[ \t]+(\S+)[ \t]*\n(.*?)^[ \t]*END[ \t]+\1[ \t]*$')
    matches = list(pattern.finditer(text))
    if len(matches) != len(re.findall(r'(?m)^[ \t]*MACRO[ \t]+', text)):
        raise ValueError('incomplete physical LEF macro blocks')
    result = {}
    for match in matches:
        if match[1] in result:
            raise ValueError('duplicate physical LEF master')
        result[match[1]] = lef_directions(match[2])
    if not result:
        raise ValueError('physical LEF masters absent')
    return result


def local_bindings(instances, terminals, cells, models):
    aliases = {}
    for master, (_, body) in models.items():
        union = aliases[master] = Union()
        for row in body:
            if row[0] == 'alias':
                union.join(row[1], row[2])
    result = {}
    for item in instances:
        name, master = item['instance'], item['leaf_master']
        if master not in aliases or name not in terminals or name not in cells:
            raise ValueError('complete same-extraction local primitive inventory required')
        cell = cells[name]
        entry = result.setdefault(cell, dict(master=master, nodes={}, primitives=[]))
        if entry['master'] != master:
            raise ValueError('physical cell master conflict')
        local = item['local_primitive_signature'][1]
        if len(local) != len(terminals[name]):
            raise ValueError('physical primitive terminal arity differs')
        for node, actual in zip(local, terminals[name]):
            representative = aliases[master].find(node)
            if representative in entry['nodes'] and entry['nodes'][representative] != actual:
                raise ValueError('one aliased local conductor has multiple assembled conductors')
            entry['nodes'][representative] = actual
        entry['primitives'].append(name)
    if {n for e in result.values() for n in e['primitives']} != terminals.keys():
        raise ValueError('local physical primitive coverage differs')
    return result, aliases


def obligations(endpoints, top_directions):
    outside = {e['direction'] for e in endpoints if e['side'] == 'outside'}
    result = []
    if 'OUTPUT' in outside:
        result.append('external_cell_driver_waveform_required')
    if 'INPUT' in outside:
        result.append('external_cell_receiver_loading_required')
    if 'INOUT' in outside:
        result.append('external_cell_inout_loading_or_behavior_required')
    if 'INPUT' in top_directions:
        result.append('primary_input_waveform_required')
    if 'OUTPUT' in top_directions:
        result.append('macro_output_integration_loading_required')
    known_driver = any(e['direction'] == 'OUTPUT' for e in endpoints) or 'INPUT' in top_directions
    if not known_driver:
        result.append('driver_origin_unresolved')
    if not endpoints:
        result.append('physical_cell_pin_binding_unresolved')
    return result


def run(reference, converted, halo, frame, top_ports, lefs, output):
    receipts = [p / 'assessment.json' for p in (reference, converted, halo, frame)]
    rr, cr, hr, fr = records = [json.loads(p.read_text()) for p in receipts]
    for record in records:
        verify(record['input_sha256']); verify(record['artifacts'])
    if rr['input_sha256'].get(str(receipts[1])) != sha(receipts[1]):
        raise ValueError('converted hierarchy differs from flat reference')
    if hr['input_sha256'].get(str(receipts[0])) != sha(receipts[0]) or hr['input_sha256'].get(str(receipts[3])) != sha(receipts[3]):
        raise ValueError('halo reference or physical frame differs')
    metadata_file = reference / 'nodes.json'
    model = reference / 'context.spice'
    source = converted / 'ng47.spice'
    halo_file = halo / 'halo.json'
    metadata = json.loads(metadata_file.read_text())
    _, cells = classify(metadata['physical_instances'], {k: v['master'] for k, v in fr['macro_sources'].items()})
    terminals = {}
    for line in model.open():
        if line.startswith('Xflat'):
            fields = line.split()
            stop = next(i for i, f in enumerate(fields) if f.startswith('sky130_fd_pr__'))
            if fields[0] in terminals:
                raise ValueError('duplicate flat primitive')
            terminals[fields[0]] = fields[1:stop]
    d = json.loads(halo_file.read_text())
    selected = set(d['expanded_primitives'])
    fixed = {metadata['original_to_emitted'][n] for n in metadata['original_fixed_supply_nodes']} | {'0'}
    _, cuts = partition(terminals, selected, fixed)
    if cuts != d['remaining_conductive_cuts'].keys():
        raise ValueError('halo conductive cuts differ from actual terminals')
    directions = {}
    for path in lefs:
        for master, ports in library_directions(path.read_text()).items():
            if master in directions and directions[master] != ports:
                raise ValueError('conflicting physical LEF master interfaces')
            directions[master] = ports
    bound, aliases = local_bindings(metadata['physical_instances'], terminals, cells, parsed(source.read_text()))
    endpoints = defaultdict(list)
    missing_masters = set()
    for cell, entry in bound.items():
        inside = set(entry['primitives']) & selected
        if inside and len(inside) != len(entry['primitives']):
            raise ValueError('halo cuts a physical cell')
        if not set(entry['nodes'].values()) & cuts:
            continue
        master = entry['master']
        if master not in directions:
            missing_masters.add(master)
            continue
        for pin, direction in directions[master].items():
            node = entry['nodes'].get(aliases[master].find(pin))
            if node in cuts:
                endpoints[node].append(dict(physical_cell=cell, master=master, pin=pin,
                                            direction=direction, side='inside' if inside else 'outside'))
    tp = json.loads(top_ports.read_text())
    odb = frame / 'floorplan.odb'
    if tp['input_sha256'].get(str(odb)) != sha(odb) or fr['artifacts'].get(str(odb)) != sha(odb):
        raise ValueError('native root-port query must bind the certified physical frame')
    top = defaultdict(set)
    for name, direction in tp['directions'].items():
        if direction not in ('INPUT', 'OUTPUT', 'INOUT'):
            raise ValueError('unsupported native primary-port direction')
        if name not in metadata['original_to_emitted']:
            raise ValueError('native primary port missing from extracted basis')
        top[metadata['original_to_emitted'][name]].add(direction)
    rows = [dict(node=node, endpoints=endpoints[node], top_directions=sorted(top[node]),
                 obligations=obligations(endpoints[node], top[node])) for node in sorted(cuts)]
    counts = Counter(item for row in rows for item in row['obligations'])
    paths = [*receipts, metadata_file, model, source, halo_file, top_ports, *lefs,
             Path(__file__).resolve(),
             *[Path(__file__).with_name(n) for n in ('compare_prototype_physical_primitive_graphs.py',
               'inventory_prototype_context_domains.py', 'inventory_prototype_context_interfaces.py',
               'prepare_prototype_context_domain_reference.py')]]
    pins = {str(p): sha(p) for p in paths}
    output.mkdir(parents=True, exist_ok=False)
    detail = output / 'interfaces.json'
    save(detail, dict(cuts=rows, missing_physical_LEF_masters=sorted(missing_masters)))
    verify(pins)
    save(output / 'assessment.json', dict(input_sha256=pins, artifacts={str(detail): sha(detail)},
         conductive_cut_nodes=len(cuts), resolved_physical_pin_endpoints=sum(len(r['endpoints']) for r in rows),
         obligations=dict(counts), missing_physical_LEF_masters=sorted(missing_masters),
         native_local_zero_R_aliases_respected=True, native_root_port_directions_used=True,
         all_cut_physical_pin_bindings_resolved=not counts['physical_cell_pin_binding_unresolved'] and not missing_masters,
         all_cut_driver_origins_resolved=not counts['driver_origin_unresolved'],
         boundary_waveforms_supplied=False, receiver_loads_replaced=False,
         loaded_native_model_qualified=False, diagnostic=True, validated_for_prototype=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'converted', 'halo', 'frame', 'top-ports', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--lef', type=Path, action='append', required=True)
    args = parser.parse_args()
    run(args.reference.resolve(), args.converted.resolve(), args.halo.resolve(), args.frame.resolve(),
        args.top_ports.resolve(), [p.resolve() for p in args.lef], args.output.resolve())
