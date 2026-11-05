"""Inventory external signed capacitances and transistor terminals at an analog interface.

The selected analog block is replaced by an empty interface while retaining the
rest of the assembled extracted hierarchy. This is an inventory, not a lumped
load approximation or a claim that other terminals are AC ground.
"""
import argparse
from pathlib import Path
import json

from prototype_capacitance_aliases import flatten
from bind_prototype_spef_pins_v2 import hierarchy
from common import save, sha, verify
from compare_prototype_analog_devices_v2 import devices
from prepare_prototype_analog_reference import subcircuits


def inventory(text, top, target, pin):
    blocks = subcircuits(text)
    ports, instances, find = hierarchy(text, top)
    selected = [v for v in instances.values() if v['model'] == target]
    if len(selected) != 1:
        raise ValueError('one direct target instance required')
    signal = find(selected[0]['pins'][pin])
    # Keep the complete port header, including continuation records.
    header = []
    for line in blocks[target].splitlines():
        if not header or line.startswith('+'):
            header.append(line)
        else:
            break
    blocks[target] = '\n'.join(header) + '\n.ends ' + target + '\n'
    caps, counts, canonical = flatten(blocks, top)
    # The hierarchy helper uses top-local names; flattened internals carry the top path.
    signal = canonical(signal if signal in ports or signal == "0" else top + "/" + signal)
    signal_device = "/".join(part[1:] if part.startswith("Xsky130_fd_sc_hd__") else part for part in signal.split("/"))
    incident = [dict(nodes=list(nodes), farads=str(value))
                for nodes, value in sorted(caps.items()) if signal in nodes]
    terminals = []
    for (model, nodes, params), count in sorted(devices(blocks, top).items()):
        if signal_device not in nodes:
            continue
        roles = ['drain', 'gate', 'source', 'bulk'] if ('nfet' in model or 'pfet' in model) else None
        if roles is not None and len(nodes) != 4:
            raise ValueError('unreviewed MOS terminal order')
        terminals.append(dict(model=model, nodes=list(nodes), parameters=dict(params), count=count,
            incident_terminals=[roles[i] if roles else 'terminal_' + str(i)
                                for i, node in enumerate(nodes) if node == signal_device]))
    return dict(target_model=target, target_pin=pin, assembled_signal=signal,
                exterior_counts=counts, incident_signed_capacitances=incident,
                external_primitive_terminals=terminals,
                external_primitive_instances=sum(t['count'] for t in terminals),
                intrinsic_device_capacitance_evaluated=False,
                coupling_other_terminal_grounded=False,
                parent_loading_complete=False, validated_for_prototype=False)


def run(source, top, target, pin, output):
    output.mkdir(parents=True, exist_ok=False)
    receipt = source / 'native_assessment.json'
    r = json.loads(receipt.read_text())
    netlist = source / top / 'capacitance.spice'
    if sha(netlist) != r['artifacts'][str(netlist)]:
        raise ValueError('assembled extraction changed')
    paths = [receipt, netlist, Path(__file__).resolve(), Path(__file__).with_name('prototype_capacitance_aliases.py'), Path(__file__).with_name('bind_prototype_spef_pins_v2.py'), Path(__file__).with_name('compare_prototype_analog_devices_v2.py')]
    pins = {str(p): sha(p) for p in paths}
    detail = output / 'interface.json'
    save(detail, inventory(netlist.read_text(), top, target, pin))
    verify(pins)
    save(output / 'assessment.json', dict(input_sha256=pins, artifacts={str(detail): sha(detail)},
         diagnostic=True, parent_loading_complete=False, validated_for_prototype=False,
         release_ready=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    for name in ('top', 'target', 'pin'):
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    run(a.source.resolve(), a.top, a.target, a.pin, a.output.resolve())
