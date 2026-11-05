"""Trace the extracted PLLOUT clock-buffer cone, retaining every terminal frontier."""
import argparse
import json
from pathlib import Path
import re

from bind_prototype_spef_pins_v2 import hierarchy
from common import save, sha, verify


def trace(text, top, signal):
    _, cells, find = hierarchy(text, top)
    terminals = {}
    for name, cell in cells.items():
        for pin, node in cell['pins'].items():
            terminals.setdefault(find(node), []).append((name, pin))
    pending = [find(signal)]
    seen = set()
    buffers = {}
    frontiers = []
    while pending:
        net = pending.pop(0)
        if net in seen:
            continue
        seen.add(net)
        for name, pin in terminals.get(net, []):
            cell = cells[name]
            match = re.fullmatch(r'sky130_fd_sc_hs__(clkbuf|buf|clkinv|inv)_(1|2|4|8|16)', cell['model'])
            if match and pin == 'A':
                output = 'Y' if match[1] in ('clkinv', 'inv') else 'X'
                destination = find(cell['pins'][output])
                if destination == net:
                    raise ValueError('shorted clock buffer input/output')
                buffers[name] = dict(instance=name, master=cell['model'], input_node=net,
                                     output_node=destination, output_pin=output,
                                     inverts=match[1] in ('clkinv', 'inv'))
                pending.append(destination)
            elif match and pin in ('X', 'Y'):
                # This is a driver of the visited conductor, not another load.
                continue
            else:
                frontiers.append(dict(instance=name, master=cell['model'], pin=pin, node=net))
    if not buffers or not frontiers:
        raise ValueError('clock buffer cone or terminal frontier absent')
    return dict(root_signal=signal, traversed_conductors=sorted(seen),
                buffers=sorted(buffers.values(), key=lambda x:x['instance']),
                frontiers=sorted(frontiers, key=lambda x:(x['node'],x['instance'],x['pin'])),
                boundary_capacitances_measured=False, clock_timing_qualified=False)


def run(layout, output):
    output.mkdir(parents=True, exist_ok=False)
    receipt = layout / 'assessment.json'
    a = json.loads(receipt.read_text())
    source = layout / 'assembly.spice'
    if not a.get('assembled_lvs_pass') or a['artifacts'].get(str(source)) != sha(source):
        raise ValueError('matching assembled LVS extraction required')
    paths = [receipt, source, Path(__file__).resolve()]
    pins = {str(p): sha(p) for p in paths}
    result = trace(source.read_text(), 'IntegerPLL_ProgrammedCore', 'PLLOUT')
    target = output / 'clock_loading.json'
    save(target, result)
    verify(pins)
    save(output / 'assessment.json', dict(input_sha256=pins, artifacts={str(target): sha(target)},
         extracted_clock_buffers=len(result['buffers']), frontier_terminals=len(result['frontiers']),
         diagnostic=True, validated_for_prototype=False, release_ready=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--layout', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    run(a.layout.resolve(), a.output.resolve())
