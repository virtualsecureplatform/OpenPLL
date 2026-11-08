"""Check R-network identity under a primitive-terminal-bound node permutation."""
import argparse
from collections import Counter
import json
import os
import time
from pathlib import Path
from common_v3 import save, sha, verify
from resources import lease
from audit_keeper_native_R_contraction import number


def scan(text):
    devices, resistors, nodes = {}, [], set()
    for line in text.splitlines():
        f = line.lower().split()
        if not f or f[0].startswith('*'):
            continue
        if f[0].startswith('x'):
            end = next((i for i, word in enumerate(f) if '=' in word), len(f)) - 1
            if f[0] in devices:
                raise ValueError('duplicate primitive name')
            devices[f[0]] = (tuple(f[1:end]), tuple(f[end:]))
        elif f[0].startswith('r'):
            if len(f) != 4:
                raise ValueError('literal wire resistor required')
            resistors.append((f[1], f[2], number(f[3])))
            nodes.update(f[1:3])
    return devices, resistors, nodes


def compare(before, after):
    a, ar, an = scan(before)
    b, br, bn = scan(after)
    if a.keys() != b.keys():
        raise ValueError('same primitive identities required')
    mapping, inverse = {}, {}
    for key in a:
        left, lp = a[key]
        right, rp = b[key]
        if lp != rp or len(left) != len(right):
            raise ValueError('primitive model/parameter records differ')
        if len(set(left) & an) > 1 or len(set(right) & bn) > 1:
            raise ValueError('multiple R-network nodes on one primitive are outside this proof')
        for old, new in zip(left, right):
            if (old in an) != (new in bn):
                raise ValueError('R-network terminal attachment differs')
            if old in an:
                if mapping.get(old, new) != new or inverse.get(new, old) != old:
                    raise ValueError('non-bijective primitive-terminal mapping')
                mapping[old], inverse[new] = new, old
            elif old != new:
                raise ValueError('non-R primitive terminal changed')
    translated = Counter((tuple(sorted((mapping.get(x, x), mapping.get(y, y)))), value) for x, y, value in ar)
    actual = Counter((tuple(sorted((x, y))), value) for x, y, value in br)
    same = translated == actual
    return dict(primitive_records=len(a), primitive_models_parameters_and_non_R_terminals_match=True,
                primitive_bound_node_mapping=mapping, renamed_terminal_nodes={k:v for k,v in mapping.items() if k != v},
                wire_R_cards=[len(ar), len(br)], exact_R_multigraph_match_under_terminal_mapping=same,
                cap_placement_compared=False, coupling_placement_qualified=False,
                dynamic_accuracy_qualified=False, native_simulation_allowed=False, release_ready=False)


def run(previous, candidate, contraction, output):
    if output.exists():
        raise FileExistsError(output)
    audit = json.loads(contraction.read_text())
    files = [previous / 'pilot.spice', candidate / 'pilot.spice']
    if audit['candidate_contraction']['exact_device_and_C_contraction_verified'] is not True:
        raise ValueError('completed exact C/primitive contraction required')
    for p in files:
        if audit['input_sha256'].get(str(p)) != sha(p):
            raise ValueError('same completed exports required')
    pins = {str(p): sha(p) for p in [*files, contraction, Path(__file__).resolve(), Path(__file__).with_name('audit_keeper_native_R_contraction.py')]}
    os.sched_setaffinity(0, {29})
    with lease(1, 2, time.clock_gettime(time.CLOCK_BOOTTIME) + 7200):
        verify(audit['input_sha256'])
        result = compare(*(p.read_text() for p in files))
        verify(pins)
        save(output, dict(input_sha256=pins, **result))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ['previous', 'candidate', 'contraction', 'output']:
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    run(*(getattr(a, name).resolve() for name in ['previous', 'candidate', 'contraction', 'output']))
