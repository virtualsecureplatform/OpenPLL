"""Trace every extracted MOS bulk to a declared parent rail; do not infer EM/IR qualification."""
import argparse
from collections import Counter
import json
from pathlib import Path
from common_v3 import save, sha, verify
from prepare_prototype_analog_reference import subcircuits
from audit_hierarchical_capacitance import number


def trace(text, top):
    parsed = {}
    for name, block in subcircuits(text).items():
        rows = []
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith('*'):
                continue
            if line.startswith('+'):
                rows[-1] += ' '+line[1:]
            else:
                rows.append(line)
        parsed[name] = (rows[0].split()[2:], rows[1:-1])
    rails = {'VPWR', 'VGND', 'VPB', 'VNB'}
    if not rails <= set(parsed[top][0]):
        raise ValueError('all four parent supply/body-bias ports required')
    parent = {}

    def find(node):
        parent.setdefault(node, node)
        root = node
        while parent[root] != root:
            root = parent[root]
        while parent[node] != node:
            next_node = parent[node]
            parent[node] = root
            node = next_node
        return root

    primitives = []

    def expand(name, path, bindings, stack):
        if name in stack:
            raise ValueError('recursive extracted hierarchy')
        ports, rows = parsed[name]
        if len(ports) != len(bindings) or len(set(ports)) != len(ports):
            raise ValueError('ambiguous extracted port binding')
        mapping = dict(zip(ports, bindings))

        def node(value):
            return '0' if value == '0' else mapping.get(value, path+'/'+value)

        seen = set()
        for row in rows:
            fields = row.split()
            kind = fields[0][0].upper()
            if kind in {'X', 'R'}:
                if fields[0] in seen:
                    raise ValueError('duplicate extracted instance')
                seen.add(fields[0])
            if kind == 'R':
                if number(fields[-1]) == 0:
                    parent[find(node(fields[1]))] = find(node(fields[2]))
                continue
            if kind != 'X':
                if kind != 'C':
                    raise ValueError('unreviewed extracted element: '+fields[0])
                continue
            positional = []
            for value in fields[1:]:
                if '=' in value:
                    break
                positional.append(value)
            model = positional[-1]
            nodes = [node(value) for value in positional[:-1]]
            instance = path+'/'+fields[0]
            if model in parsed:
                expand(model, instance, nodes, stack+[name])
            elif model.startswith('sky130_fd_pr__'):
                if 'nfet' in model or 'pfet' in model:
                    if len(nodes) != 4:
                        raise ValueError('four-terminal MOS required')
                    primitives.append((instance, model, nodes[3]))
                elif len(nodes) == 2 and ('diode' in model or model == 'sky130_fd_pr__res_generic_po'):
                    primitives.append((instance, model, None))
                else:
                    raise ValueError('unreviewed primitive: '+model)
            else:
                raise ValueError('unresolved extracted subcircuit: '+model)

    expand(top, top, parsed[top][0], [])
    high = {find('VPWR'), find('VPB')}
    low = {find('VGND'), find('VNB')}
    if high & low:
        raise ValueError('positive and negative parent rails shorted')
    failures = []
    counts = Counter()
    for instance, model, bulk in primitives:
        counts[model] += 1
        if bulk is None:
            continue
        allowed = high if 'pfet' in model else low
        if find(bulk) not in allowed:
            failures.append(dict(instance=instance, model=model, bulk_node=bulk,
                                 canonical_bulk_node=find(bulk)))
    mos = sum(count for model, count in counts.items() if 'nfet' in model or 'pfet' in model)
    if not mos:
        raise ValueError('expanded MOS inventory required')
    return dict(expanded_MOS_instances=mos, primitive_models=dict(counts),
                all_MOS_bulk_terminals_connected_to_correct_parent_rail=not failures,
                unexpected_bulk_connections=failures,
                parent_rail_classes={rail: find(rail) for rail in sorted(rails)},
                explicit_diodes_excluded_from_four_terminal_MOS_bulk_check=True,
                two_terminal_poly_resistors_counted_without_inventing_a_bulk_terminal=True,
                finite_resistances_not_collapsed=True)


def run(layout, output):
    receipt = layout/'assessment.json'
    record = json.loads(receipt.read_text())
    if not record.get('assembled_lvs_pass') or not record.get('assembled_drc_pass') or not record.get('all_three_macros_expanded'):
        raise ValueError('assembled DRC/LVS with all three macros expanded required')
    verify(record['input_sha256']); verify(record['artifacts'])
    models = [Path(p) for p in record['artifacts'] if p.endswith('assembly_alias_normalized.spice')]
    if len(models) != 1:
        raise ValueError('unique audited assembled netlist required')
    model = models[0]
    result = trace(model.read_text(), 'IntegerPLL_400MHz_PrototypeTop')
    output.mkdir(parents=True, exist_ok=False)
    detail = output/'bulk_connections.json'; save(detail, result)
    pins = {str(p): sha(p) for p in (receipt, model, Path(__file__).resolve(),
            Path(__file__).with_name('prepare_prototype_analog_reference.py'),
            Path(__file__).with_name('audit_hierarchical_capacitance.py'))}
    verify(pins)
    save(output/'assessment.json', dict(input_sha256=pins, artifacts={str(detail): sha(detail)},
         expanded_MOS_instances=result['expanded_MOS_instances'],
         extracted_bulk_connectivity_pass=result['all_MOS_bulk_terminals_connected_to_correct_parent_rail'],
         extraction_geometry_and_supply_aliases_preserved=True,
         parent_supply_voltage_and_body_bias_contract_verified=False,
         well_tap_spacing_and_latchup_rules_qualified=False, power_integrity_qualified=False,
         release_ready=False))
    if result['unexpected_bulk_connections']:
        raise ValueError('unexpected MOS bulk connectivity')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('layout', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args(); run(a.layout.resolve(), a.output.resolve())
