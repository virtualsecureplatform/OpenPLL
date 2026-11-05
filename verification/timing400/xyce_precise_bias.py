#!/usr/bin/env python3
"""Export round-trippable voltage ICs from explicit high-precision N() output."""
import argparse
import math
from pathlib import Path
import re


def reference_nodes(path):
    nodes = []
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('*'): continue
        match = re.fullmatch(r'\s*\.IC\s+V\(([^)]+)\)\s*=\s*(\S+)\s*', line, re.I)
        assert match and math.isfinite(float(match[2])), line
        nodes.append(match[1])
    assert nodes and len({name.upper() for name in nodes}) == len(nodes)
    return nodes


def print_directive(nodes):
    # N() can access both ordinary and device-internal solution variables;
    # V(*) and explicit V(internal-name) omit or reject the latter in Xyce.
    lines = ['.PRINT DC FORMAT=STD PRECISION=17']
    for start in range(0, len(nodes), 16):
        lines.append('+ ' + ' '.join(f'N({name})' for name in nodes[start:start + 16]))
    return '\n'.join(lines) + '\n'


def convert(reference, wave, output):
    nodes = reference_nodes(reference)
    lines = [line for line in wave.read_text().splitlines() if line.strip()]
    assert len(lines) == 3 and lines[-1] == 'End of Xyce(TM) Simulation'
    header, row = lines[0].split(), lines[1].split()
    assert header[0] == 'Index' and row[0] == '0' and len(header) == len(row) == len(nodes) + 1
    values = {}
    for column, token in zip(header[1:], row[1:]):
        match = re.fullmatch(r'N\(([^)]+)\)', column, re.I)
        assert match and match[1].upper() not in values, column
        value = float(token); assert math.isfinite(value)
        values[match[1].upper()] = value
    assert set(values) == {node.upper() for node in nodes}
    assert not output.exists()
    output.write_text(''.join(f'.IC V({node}) = {values[node.upper()]:.17g}\n' for node in nodes))
    restored = reference_nodes(output)
    assert restored == nodes
    for line, node in zip(output.read_text().splitlines(), nodes):
        assert float(line.rsplit('=', 1)[1]) == values[node.upper()]
    return len(nodes)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wave', type=Path)
    args = parser.parse_args()
    if args.wave:
        print('Exported', convert(args.reference, args.wave, args.output), 'round-trippable voltages.')
    else:
        assert not args.output.exists()
        args.output.write_text(print_directive(reference_nodes(args.reference)))


if __name__ == '__main__':
    main()
