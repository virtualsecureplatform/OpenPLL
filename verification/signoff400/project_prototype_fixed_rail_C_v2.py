"""Project a complete signed capacitor operator onto explicitly ideal supply rails."""
import argparse
from collections import defaultdict
from fractions import Fraction as F
import json
from pathlib import Path
from common_v3 import save, sha, verify
from prepare_prototype_analog_reference import subcircuits
from prototype_capacitance_aliases_v2 import flatten
from bind_prototype_spef_pins_v2 import hierarchy

FIXED = '__fixed_rail_AC_reference'
RAILS = ('0', 'VGND', 'VNB', 'VPB', 'VPWR')


def project(pairs, fixed):
    result = defaultdict(F)
    for nodes, value in pairs.items():
        a, b = (FIXED if n in fixed else n for n in nodes)
        if a != b:
            result[tuple(sorted((a, b)))] += value
    return {k: v for k, v in result.items() if v}


def run(source, top, output):
    receipt = source / 'assessment.json'
    record = json.loads(receipt.read_text())
    verify(record['input_sha256']); verify(record['artifacts'])
    originals = [Path(p) for p in record['input_sha256']
                 if p.endswith('/' + top + '/capacitance.spice')]
    if len(originals) != 1:
        raise ValueError('unique original capacitor hierarchy required')
    original = originals[0]
    pairs_file = source / (top + '.pairs.jsonl')
    if record['artifacts'].get(str(pairs_file)) != sha(pairs_file):
        raise ValueError('complete signed aggregation required')
    pairs = {tuple(r['nodes']): F(r['farads'])
             for line in pairs_file.read_text().splitlines() for r in [json.loads(line)]}
    blocks = subcircuits(original.read_text())
    independent, _, canonical = flatten(blocks, top)
    if independent != pairs:
        raise ValueError('complete operator does not match original hierarchy')
    # The hierarchical flattener binds top-level ports by their literal names.
    header = blocks[top].split('.subckt', 1)[1].splitlines()
    ports = header[0].split()[1:]
    for line in header[1:]:
        if not line.startswith('+'): break
        ports.extend(line.split()[1:])
    _, instances, root_alias = hierarchy(original.read_text(), top)
    bindings = {}
    for pin in RAILS[1:]:
        conductors = {root_alias(i['pins'][pin]) for i in instances.values()
                      if pin in i['pins']}
        if len(conductors) != 1:
            raise ValueError('supply pins must identify one connected conductor: ' + pin)
        n = conductors.pop()
        bindings[pin] = canonical(n if n in ports or n == '0' else top + '/' + n)
    if {bindings['VPWR'], bindings['VPB']} & {bindings['VGND'], bindings['VNB']}:
        raise ValueError('positive and ground supply conductors shorted')
    fixed = set(bindings.values()) | {'0'}
    dynamic = project(pairs, fixed)
    output.mkdir(parents=True, exist_ok=False)
    target = output / 'dynamic.pairs.jsonl'
    target.write_text(''.join(json.dumps(dict(nodes=list(k), farads=str(v))) + '\n'
                              for k, v in sorted(dynamic.items())))
    paths = [receipt, pairs_file, original, Path(__file__).resolve(),
             Path(__file__).with_name('prototype_capacitance_aliases_v2.py'),
             Path(__file__).with_name('native_spice_comments.py'),
             Path(__file__).with_name('bind_prototype_spef_pins_v2.py'),
             Path(__file__).with_name('prepare_prototype_analog_reference.py')]
    pins = {str(p): sha(p) for p in paths}; verify(pins)
    save(output / 'assessment.json', dict(input_sha256=pins,
         artifacts={str(target): sha(target)}, fixed_voltage_nodes=sorted(fixed),
         supply_pin_conductor_bindings=bindings,
         supplies_exposed_as_top_ports=set(RAILS[1:]) <= set(ports),
         complete_original_operator_independently_reparsed=True,
         exact_fixed_voltage_congruence=True, signed_values_preserved=True,
         dynamic_pairs=len(dynamic), ideal_constant_supply_assumption=True,
         nonideal_supply_behavior_qualified=False, release_ready=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('source', 'output'): p.add_argument('--' + n, type=Path, required=True)
    p.add_argument('--top', required=True)
    a = p.parse_args(); run(a.source.resolve(), a.top, a.output.resolve())
