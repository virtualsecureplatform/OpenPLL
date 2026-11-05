#!/usr/bin/env python3
"""Remove algebraic resistor-only leaves and series nodes with replay proof.

No capacitor, device, port or dynamic state is removed. Resistor arithmetic
uses exact fractions; surviving replacements are serialized to 17 digits.
This is a model transformation candidate, not native/release qualification.
"""
import argparse
from collections import defaultdict, deque
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

from run_dco_qualification import sha, save


def parse(text):
    resistors, lines, protected = {}, {}, {'0'}
    nonresistor = []
    subckts = ends = 0
    for index, line in enumerate(text.splitlines()):
        fields = line.split()
        if not fields or fields[0].startswith('*'):
            continue
        lead = fields[0].upper()
        if lead.startswith('R'):
            assert len(fields) == 4, 'only literal, constant, two-terminal resistors supported'
            name, a, b, value = fields
            name, a, b = name.casefold(), a.casefold(), b.casefold()
            value = Fraction(value)
            assert value > 0 and name not in resistors
            resistors[name] = (a, b, value)
            lines[name] = index
        else:
            if lead.startswith('.'):
                assert lead in ('.SUBCKT', '.ENDS'), 'unsupported directive in reduction input'
                subckts += lead == '.SUBCKT'
                ends += lead == '.ENDS'
            else:
                assert lead[0] in 'XMDCQ+', 'dependent/current-probe elements require separate handling'
            protected.update(field.casefold() for field in fields[1:])
            nonresistor.append(line)
    assert subckts == ends == 1 and resistors
    # Current-dependent resistor references are not supported by this pass.
    assert not any(name in protected for name in resistors)
    return resistors, lines, protected, '\n'.join(nonresistor)


def adjacency(resistors):
    result = defaultdict(set)
    for name, (a, b, _) in resistors.items():
        result[a].add(name)
        result[b].add(name)
    return result


def reduce(source):
    original, source_lines, protected, _ = parse(source)
    resistors = dict(original)
    graph = adjacency(resistors)
    trace, generated = [], 0

    def remove(name):
        a, b, _ = resistors.pop(name)
        graph[a].discard(name)
        graph[b].discard(name)
        return a, b

    for name, (a, b, _) in list(resistors.items()):
        if a == b:
            remove(name)
            trace.append(dict(kind='self_loop', node=a, edges=[name]))
    queue = deque(sorted(node for node in graph if node not in protected and 0 < len(graph[node]) <= 2))
    while queue:
        node = queue.popleft()
        names = sorted(graph[node])
        if node in protected or not 0 < len(names) <= 2:
            continue
        neighbors = [b if a == node else a for name in names for a, b, _ in [resistors[name]]]
        assert node not in neighbors
        if len(set(neighbors)) == 1:
            for name in names:
                remove(name)
            trace.append(dict(kind='open_leaf', node=node, edges=names))
        else:
            assert len(names) == 2
            value = sum((resistors[name][2] for name in names), Fraction())
            for name in names:
                remove(name)
            while True:
                label = f'rr_exact_{generated:08d}'
                generated += 1
                if label not in original:
                    break
            a, b = sorted(neighbors)
            resistors[label] = (a, b, value)
            graph[a].add(label)
            graph[b].add(label)
            trace.append(dict(kind='series', node=node, edges=names, replacement=label))
        assert not graph[node]
        for neighbor in neighbors:
            if neighbor not in protected and 0 < len(graph[neighbor]) <= 2:
                queue.append(neighbor)
    deleted = {source_lines[name] for name in original if name not in resistors}
    replacements = []
    for name in sorted(set(resistors)-set(original)):
        a, b, value = resistors[name]
        numeric = float(value)
        assert math.isfinite(numeric) and numeric > 0
        replacements.append(f'{name} {a} {b} {numeric:.17g}')
    output = []
    for index, line in enumerate(source.splitlines()):
        if index in deleted:
            continue
        if line.lstrip().upper().startswith('.ENDS'):
            output.extend(replacements)
        output.append(line)
    return '\n'.join(output)+'\n', trace


def verify(source, output, trace):
    active, _, protected, invariant = parse(source)
    final, _, _, output_invariant = parse(output)
    assert invariant == output_invariant, 'ports/capacitors/devices/directives changed'
    graph = adjacency(active)
    for event in trace:
        kind, node, names = event['kind'], event['node'], event['edges']
        assert all(name in active for name in names)
        if kind == 'self_loop':
            assert len(names) == 1 and active[names[0]][:2] == (node, node)
            affected = [node]
        else:
            assert node not in protected and set(names) == graph[node]
            assert 0 < len(names) <= 2
            affected = []
            for name in names:
                a, b, _ = active[name]
                assert (a == node) != (b == node)
                affected.append(b if a == node else a)
            if kind == 'open_leaf':
                assert len(set(affected)) == 1
            else:
                assert kind == 'series' and len(names) == 2 and len(set(affected)) == 2
                replacement = event['replacement']
                assert replacement not in active
                value = active[names[0]][2]+active[names[1]][2]
        for name in names:
            a, b, _ = active.pop(name)
            graph[a].discard(name)
            graph[b].discard(name)
        if kind == 'series':
            a, b = sorted(affected)
            active[replacement] = (a, b, value)
            graph[a].add(replacement)
            graph[b].add(replacement)
    assert set(active) == set(final)
    worst = Fraction()
    for name, (a, b, value) in active.items():
        x, y, written = final[name]
        assert (a, b) == (x, y)
        error = abs(written-value)/value
        assert error <= Fraction(1, 10**14), 'resistance serialization exceeds fixed roundoff bound'
        worst = max(worst, error)
    return dict(source_resistors=len(parse(source)[0]), reduced_resistors=len(final),
        eliminated_nodes=len({event['node'] for event in trace if event['kind'] != 'self_loop'}),
        eliminated_self_loops=sum(event['kind']=='self_loop' for event in trace),
        nonresistor_statement_sha256=hashlib.sha256(invariant.encode()).hexdigest(),
        maximum_relative_resistance_serialization_error=float(worst),
        every_elimination_identity_replayed=True, all_ports_devices_capacitors_unchanged=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    source, out = args.source.resolve(), args.output.resolve()
    text = source.read_text()
    pins = {str(path): sha(path) for path in (source, Path(__file__).resolve())}
    output, trace = reduce(text)
    result = verify(text, output, trace)
    result['effective_reduction'] = result['reduced_resistors'] < result['source_resistors']
    result['spice_node_names_compared_case_insensitively'] = True
    candidates = [(i, line) for i, line in enumerate(output.splitlines()) if line.lstrip().upper().startswith('R')]
    assert candidates
    index, line = candidates[0]
    bad = output.splitlines()
    fields = line.split()
    fields[3] = format(float(fields[3])*1.01, '.17g')
    bad[index] = ' '.join(fields)
    try:
        verify(text, '\n'.join(bad)+'\n', trace)
        raise RuntimeError('wrong-resistance negative control was accepted')
    except AssertionError:
        result['wrong_resistance_rejected'] = True
    bad = output.splitlines()
    index = next(i for i, line in enumerate(bad) if line.lstrip().upper().startswith('C'))
    del bad[index]
    try:
        verify(text, '\n'.join(bad)+'\n', trace)
        raise RuntimeError('missing-capacitor negative control was accepted')
    except AssertionError:
        result['missing_capacitor_rejected'] = True
    for path, digest in pins.items():
        assert sha(Path(path)) == digest
    out.mkdir(parents=True, exist_ok=False)
    (out/'reduced_exact.spice').write_text(output)
    save(out/'elimination_trace.json', trace)
    save(out/'assessment.json', dict(input_sha256=pins,
        artifacts={str(p): sha(p) for p in out.iterdir() if p.is_file()}, **result,
        mathematical_scope='Algebraic KCL equivalence for constant resistors, before explicitly bounded serialization roundoff',
        native_waveform_validation_complete=False, adopted=False, release_qualified=False, scope=__doc__))
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
