"""Insert inventoried parent wire R through proved primitive terminal incidence.

The complete signed C operator is lifted by an injective one-hot voltage map.
Driver/farthest attachment are diagnostic variants, not a distributed physical
C reconstruction. Fixed-supply wires remain under the existing ideal-PDN
assumption. Proved shared macro accesses use one internal conductor junction.
"""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction as F
import heapq
import json
from pathlib import Path
from common_v3 import save, sha, verify
from build_prototype_DCO_rc import decimal


class Union:
    def __init__(self):
        self.parent = {}

    def find(self, node):
        self.parent.setdefault(node, node)
        root = node
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[node] != node:
            following = self.parent[node]
            self.parent[node] = root
            node = following
        return root

    def join(self, a, b):
        a, b = self.find(a), self.find(b)
        self.parent[max(a, b)] = min(a, b)


def primitive(fields):
    stop = next(i for i, word in enumerate(fields) if word.startswith('sky130_fd_pr__'))
    return fields[0], fields[1:stop], fields[stop:]


def source_inventory(lines):
    terminals, nodes, ports = {}, set(), None
    for line in lines:
        fields = line.split()
        if not fields or fields[0].startswith('*'):
            continue
        if fields[0].lower() == '.subckt':
            if ports is not None:
                raise ValueError('one flat native context required')
            ports = fields[2:]; nodes.update(ports)
        elif fields[0].startswith('Xflat'):
            name, ns, _ = primitive(fields)
            if name in terminals:
                raise ValueError('duplicate flat primitive')
            terminals[name] = ns; nodes.update(ns)
        elif fields[0].startswith(('Cflat', 'Ckron')):
            if len(fields) != 4:
                raise ValueError('explicit two-terminal C required')
            nodes.update(fields[1:3])
        elif fields[0][0].upper() == 'R':
            raise ValueError('source already contains wire or alias resistors')
    if ports is None:
        raise ValueError('missing source interface')
    return terminals, nodes, ports


def plan(networks, bindings, terminals, source_nodes, ports, fixed, attachment):
    if attachment not in ('driver', 'farthest'):
        raise ValueError('explicit attachment variant required')
    signals = [n for n in networks if n['context_conductor'] not in fixed]
    lookup = {(r['net'], r['wire_terminal']): r for r in bindings}
    if len(lookup) != len(bindings):
        raise ValueError('duplicate physical terminal binding')
    tokens, token_old, owners, primaries, drivers = set(), {}, defaultdict(list), {}, defaultdict(list)
    union = Union()
    for net in signals:
        name, old = net['net'], net['context_conductor']
        local = {t['node'] for t in net['terminals']} | {n for r in net['resistors'] for n in r['nodes']}
        for node in local:
            key = name, node
            tokens.add(key); token_old[key] = old; union.find(key)
        for t in net['terminals']:
            key = name, t['node']
            if key not in lookup:
                raise ValueError('missing physical primitive terminal binding')
            row = lookup[key]
            if row['context_conductor'] != old or row['ideal_supply_boundary']:
                raise ValueError('physical terminal conductor differs')
            if t['kind'] == 'P':
                if t['node'] not in ports or t['node'] != old or not row['top_port']:
                    raise ValueError('explicit matching primary port required')
                primaries[key] = t['node']
            else:
                if row['top_port'] or not row['primitive_terminal_positions']:
                    raise ValueError('primitive incidence required for every signal instance terminal')
                for instance, index in row['primitive_terminal_positions']:
                    if terminals[instance][index] != old:
                        raise ValueError('source primitive terminal does not match physical wire binding')
                    owners[instance, index].append(key)
            if (t['kind'] == 'I' and t['direction'] == 'O') or (t['kind'] == 'P' and t['direction'] == 'I'):
                drivers[old].append(key)
    old_nodes = {n['context_conductor'] for n in signals}
    actual = {(name, i) for name, ns in terminals.items() for i, node in enumerate(ns) if node in old_nodes}
    if actual != set(owners):
        raise ValueError('signal wire primitive incidence is incomplete or excessive')
    for keys in owners.values():
        for key in keys[1:]:
            if token_old[key] != token_old[keys[0]]:
                raise ValueError('shared macro access crosses physical conductors')
            union.join(keys[0], key)
    groups = defaultdict(list)
    for key in sorted(tokens):
        groups[union.find(key)].append(key)
    names, new_to_old, shared = {}, {}, []
    for i, keys in enumerate(groups.values()):
        primary = {primaries[k] for k in keys if k in primaries}
        if len(primary) > 1:
            raise ValueError('distinct named primary ports need an explicit alias model')
        node = next(iter(primary)) if primary else '__parent_R_node_' + str(i)
        if not primary and node in source_nodes:
            raise ValueError('reserved wire node namespace collision')
        old = {token_old[k] for k in keys}
        if len(old) != 1:
            raise ValueError('junction crosses native physical conductors')
        new_to_old[node] = old.pop()
        for key in keys:
            names[key] = node
        if len(keys) > 1:
            shared.append(dict(junction=node, accesses=[list(k) for k in keys]))
    position_nodes = {position: names[keys[0]] for position, keys in owners.items()}
    wire, graph, components = [], defaultdict(list), Union()
    for net in signals:
        for resistor in net['resistors']:
            a, b = [names[net['net'], n] for n in resistor['nodes']]
            value = F(resistor['ohms'])
            if value <= 0:
                raise ValueError('positive native wire resistance required')
            wire.append(('RparentWire' + str(len(wire)), a, b, value))
            graph[a].append((b, value)); graph[b].append((a, value)); components.join(a, b)
    by_old = defaultdict(set)
    for node, old in new_to_old.items():
        by_old[old].add(node)
    anchors = {}
    for old, vertices in by_old.items():
        if len({components.find(n) for n in vertices}) != 1:
            raise ValueError('wire graphs for a native conductor are not connected')
        candidates = sorted({names[k] for k in drivers[old]})
        if not candidates:
            raise ValueError('physical wire conductor has no inventoried driver')
        origin = candidates[0]; distances = {origin: F()}; heap = [(F(), origin)]
        while heap:
            distance, node = heapq.heappop(heap)
            if distance != distances[node]:
                continue
            for other, resistance in graph[node]:
                value = distance + resistance
                if other not in distances or value < distances[other]:
                    distances[other] = value; heapq.heappush(heap, (value, other))
        if set(distances) != vertices:
            raise ValueError('wire graph voltage domains cross or are disconnected')
        anchors[old] = origin if attachment == 'driver' else max(vertices, key=lambda n: (distances[n], n))
    if len({anchors.get(n, n) for n in source_nodes}) != len(source_nodes):
        raise ValueError('complete C voltage lift is not injective')
    return dict(positions=position_nodes, anchors=anchors, wire=wire, new_to_old=new_to_old,
                shared_junctions=shared, signal_networks=len(signals), conductor_count=len(by_old))


def render(lines, p):
    emitted = []
    for line in lines:
        fields = line.split()
        if fields and fields[0].startswith('Xflat'):
            name, nodes, tail = primitive(fields)
            nodes = [p['positions'].get((name, i), n) for i, n in enumerate(nodes)]
            line = ' '.join([name, *nodes, *tail])
        elif fields and fields[0].startswith(('Cflat', 'Ckron')):
            fields[1:3] = [p['anchors'].get(n, n) for n in fields[1:3]]
            line = ' '.join(fields)
        elif fields and fields[0].lower() == '.ends':
            emitted.extend(' '.join([name, a, b, decimal(value)]) for name, a, b, value in p['wire'])
        emitted.append(line)
    return emitted


def contraction_review(source, emitted, p):
    union = Union(); actual_R = []
    for line in emitted:
        fields = line.split()
        if fields and fields[0].startswith('RparentWire'):
            name, a, b, value = fields
            actual_R.append((name, a, b, F(value))); union.join(a, b)
    if Counter(actual_R) != Counter(p['wire']):
        raise ValueError('actual resistor cards differ from the native wire inventory')
    roots, by_old = defaultdict(set), defaultdict(set)
    for node, old in p['new_to_old'].items():
        roots[union.find(node)].add(old); by_old[old].add(union.find(node))
    if any(len(v) != 1 for v in roots.values()) or any(len(v) != 1 for v in by_old.values()):
        raise ValueError('wire contraction does not define one component per source conductor')
    def node(n):
        return next(iter(roots[union.find(n)])) if n in p['new_to_old'] else n
    def signatures(lines, transform):
        devices, caps = Counter(), Counter()
        for line in lines:
            f = line.split()
            if f and f[0].startswith('Xflat'):
                name, ns, tail = primitive(f)
                devices[name, tuple(map(transform, ns)), tuple(tail)] += 1
            elif f and f[0].startswith(('Cflat', 'Ckron')):
                caps[f[0], transform(f[1]), transform(f[2]), F(f[3])] += 1
        return devices, caps
    if signatures(source, lambda n: n) != signatures(emitted, node):
        raise ValueError('wire contraction changes original primitive or signed capacitor cards')
    if [l for l in source if l.lower().startswith('.subckt')] != [l for l in emitted if l.lower().startswith('.subckt')]:
        raise ValueError('named top interface changed')
    return dict(all_native_wire_R_cards_reparsed=True, all_primitive_and_signed_C_cards_recovered_by_R_contraction=True,
                parent_wire_contraction_components=len(by_old), injective_C_voltage_lift=True)


def run(source, source_review, reference, binding, terminals, corner, attachment, output):
    receipts = [p / 'assessment.json' for p in (source, source_review, reference, binding, terminals)]
    sr, vr, rr, br, tr = records = [json.loads(p.read_text()) for p in receipts]
    for r in records:
        verify(r['input_sha256']); verify(r['artifacts'])
    if not sr['complete_reduced_fixed_supply_C_passivity_certified'] or not vr['complete_reduced_fixed_supply_C_passivity_certified']:
        raise ValueError('complete source C passivity and independent export replay required')
    if vr['input_sha256'].get(str(receipts[0])) != sha(receipts[0]):
        raise ValueError('source pruning review refers to a different model')
    if not F(sr['maximum_normalized_final_row_error']) <= F(str(sr['relative_row_error_budget'])) <= F('1e-6'):
        raise ValueError('source C numerical error budget exceeded')
    for record in (br, tr):
        if record['input_sha256'].get(str(receipts[2])) != sha(receipts[2]):
            raise ValueError('physical wire and reference basis differ')
    if tr['input_sha256'].get(str(receipts[3])) != sha(receipts[3]) or not tr['all_signal_instance_terminals_have_native_physical_primitive_incidence']:
        raise ValueError('complete matching primitive incidence proof required')
    if sr['assembled_candidate_gds_sha256'] != rr['assembled_candidate_gds_sha256']:
        raise ValueError('source and physical reference manufacturing candidates differ')
    model = source / 'context.spice'; original = reference / 'context.spice'
    metadata_file = reference / 'nodes.json'; wire_file = binding / (corner + '.wire_interfaces.json')
    terminal_file = terminals / 'terminal_bindings.json'
    paths = [*receipts, model, original, metadata_file, wire_file, terminal_file, Path(__file__).resolve(),
             Path(__file__).with_name('build_prototype_DCO_rc.py')]
    pins = {str(p): sha(p) for p in paths}
    lines = model.read_text().splitlines()
    if [l for l in lines if l.startswith('Xflat')] != [l for l in original.read_text().splitlines() if l.startswith('Xflat')]:
        raise ValueError('source physical primitive identities differ from the flat reference')
    metadata = json.loads(metadata_file.read_text())
    fixed = {metadata['original_to_emitted'][n] for n in metadata['original_fixed_supply_nodes']} | {'0'}
    active, nodes, ports = source_inventory(lines)
    p = plan(json.loads(wire_file.read_text())['networks'], json.loads(terminal_file.read_text())['terminals'],
             active, nodes, ports, fixed, attachment)
    emitted = render(lines, p)
    proof = contraction_review(lines, emitted, p)
    verify(pins); output.mkdir(parents=True, exist_ok=False)
    target = output / 'context.spice'; target.write_text('\n'.join(emitted) + '\n')
    # Re-read the actual file, not only the renderer's in-memory output.
    contraction_review(lines, target.read_text().splitlines(), p)
    detail = output / 'wire_map.json'
    save(detail, dict(capacitor_anchors=p['anchors'], generated_node_to_source_conductor=p['new_to_old'],
                      shared_macro_access_junctions=p['shared_junctions']))
    verify(pins)
    save(output / 'assessment.json', dict(input_sha256=pins, artifacts={str(p): sha(p) for p in (target, detail)},
        **proof, assembled_candidate_gds_sha256=sr['assembled_candidate_gds_sha256'], top=sr['top'],
        wire_corner=corner, attachment=attachment, inserted_parent_wire_resistors=len(p['wire']),
        signal_wire_networks=p['signal_networks'], mapped_signal_conductors=p['conductor_count'],
        primitive_terminal_positions_rebound=len(p['positions']), shared_macro_access_junctions=len(p['shared_junctions']),
        complete_reduced_fixed_supply_C_passivity_certified=True,
        source_C_numerical_error_budget_preserved_under_injective_lift=True,
        maximum_normalized_final_row_error=sr['maximum_normalized_final_row_error'],
        relative_row_error_budget=sr['relative_row_error_budget'],
        fixed_supply_wire_R_adopted=False, SPEF_C_added=False, capacitor_spatial_attachment_qualified=False,
        child_internal_wire_R_complete=False, loaded_native_model_qualified=False,
        diagnostic=True, validated_for_prototype=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'source-review', 'reference', 'binding', 'terminals', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--corner', choices=('min', 'nom', 'max'), required=True)
    parser.add_argument('--attachment', choices=('driver', 'farthest'), required=True)
    a = parser.parse_args()
    run(a.source.resolve(), a.source_review.resolve(), a.reference.resolve(), a.binding.resolve(),
        a.terminals.resolve(), a.corner, a.attachment, a.output.resolve())
