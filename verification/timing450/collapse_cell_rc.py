#!/usr/bin/env python3
"""Short extracted cell resistors and omit capacitance for transistor-only LVS.

Only the verification copy is changed; the physical RC simulation model is intact.
"""
import argparse
import json
import math
import re
from pathlib import Path


def collapse(source, output):
    text = source.read_text()
    headers = re.findall(r'^\.subckt (\S+) (.+)$', text, re.M)
    assert len(headers) == 1
    name, port_text = headers[0]
    ports = port_text.split()
    assert len(ports) == len(set(ports))
    parent = {}

    def root(node):
        parent.setdefault(node, node)
        if parent[node] != node:
            parent[node] = root(parent[node])
        return parent[node]

    counts = dict(resistors=0, capacitors=0, transistors=0)
    for line in text.splitlines():
        fields = line.split()
        if not fields:
            continue
        kind = fields[0][0]
        if kind == 'R':
            assert len(fields) == 4
            value = float(fields[3])
            assert math.isfinite(value) and value > 0
            a, b = root(fields[1]), root(fields[2])
            if a != b:
                parent[a] = b
            counts['resistors'] += 1
        elif kind == 'C':
            assert len(fields) == 4
            counts['capacitors'] += 1
        elif kind == 'X':
            assert len(fields) >= 8
            assert fields[5].startswith('sky130_fd_pr__')
            for node in fields[1:5]:
                root(node)
            counts['transistors'] += 1
        else:
            assert kind in ('*', '.'), ('Unexpected model statement', line)
    assert all(counts.values())
    components = {}
    for node in list(parent):
        components.setdefault(root(node), []).append(node)
    aliases = {}
    for nodes in components.values():
        external = set(nodes) & set(ports)
        assert len(external) <= 1, ('Resistors short distinct cell ports', external)
        preferred = next(iter(external)) if external else min(nodes, key=lambda n: (len(n), n))
        aliases.update({node: preferred for node in nodes})
    lines = []
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0].startswith(('R', 'C')):
            continue
        if fields and fields[0].startswith('X'):
            fields[1:5] = [aliases[node] for node in fields[1:5]]
            line = ' '.join(fields)
        lines.append(line)
    assert not output.exists()
    output.write_text('\n'.join(lines) + '\n')
    return {'cell': name, **counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(collapse(args.model, args.output), indent=2))


if __name__ == '__main__':
    main()
