"""Independent end-to-end R control for repeated logical layout labels."""
import json
import os
import shlex
import time
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path
from runtime_common import ROOT, save, sha
from resources import identity, lease
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import TECH
from audit_keeper_native_R_contraction import parse


def effective_R(resistors, first, last):
    parent = {}
    def root(n):
        parent.setdefault(n, n)
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n
    for a, b, value in resistors:
        if value < 0:
            raise ValueError('negative resistance')
        if value == 0:
            parent[root(a)] = root(b)
    first, last = root(first), root(last)
    if first == last:
        return F(0)
    graph = defaultdict(dict)
    for a, b, value in resistors:
        a, b = root(a), root(b)
        if value and a != b:
            graph[a][b] = graph[a].get(b, F(0)) + 1 / value
            graph[b][a] = graph[b].get(a, F(0)) + 1 / value
    reached, pending = {first}, [first]
    while pending:
        a = pending.pop()
        for b in graph[a]:
            if b not in reached:
                reached.add(b); pending.append(b)
    if last not in reached:
        raise ValueError('control wire disconnected')
    names = sorted(reached - {last})
    if len(names) > 64:
        raise ValueError('small native control required')
    matrix = [[F(0) for _ in range(len(names) + 1)] for _ in names]
    index = {n: i for i, n in enumerate(names)}
    for a, i in index.items():
        matrix[i][i] = sum(graph[a].values())
        matrix[i][-1] = F(a == first)
        for b, g in graph[a].items():
            if b != last:
                matrix[i][index[b]] -= g
    for k in range(len(names)):
        pivot = next(i for i in range(k, len(names)) if matrix[i][k])
        matrix[k], matrix[pivot] = matrix[pivot], matrix[k]
        divisor = matrix[k][k]
        matrix[k] = [v / divisor for v in matrix[k]]
        for i in range(len(names)):
            if i != k:
                factor = matrix[i][k]
                matrix[i] = [a - factor * b for a, b in zip(matrix[i], matrix[k])]
    return matrix[index[first]][-1]


def run():
    out = ROOT / 'build/signoff400/selected_repeated_RC_labels_1705'
    out.mkdir(exist_ok=False)
    template = ROOT / 'tools/magic_rcx/coupling_grounding_R_threshold1_probe.tcl'
    baseline = template.read_text().replace('extresist include A\n', '').replace(
        'extract do resistance', 'extract no resistance').replace('extresist threshold 1', 'extresist threshold 0')
    addition = '''box values 1200 0 1220 100
label MID center m1
box values 2700 0 2720 100
label MID center m1
'''
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 1800
    rows, pins = [], {str(template): sha(template), str(TECH): sha(TECH), str(Path(__file__).resolve()): sha(Path(__file__).resolve())}
    os.sched_setaffinity(0, {29})
    for engine_name in ['magic_precise_ground_ports_1700', 'magic_single_RC_points_1704']:
        engine = ROOT / 'build/tools' / engine_name
        owner = json.loads((engine / 'owner.json').read_text())
        while not (engine / 'assessment.json').exists():
            if identity(owner['pid']) != owner['birth']:
                raise ValueError('build ended without a completion receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME) > deadline:
                raise TimeoutError('native control admission deadline')
            time.sleep(5)
        receipt = engine / 'assessment.json'; record = json.loads(receipt.read_text())
        binary = engine / 'install/bin/magic'; library = engine / 'install/lib/magic/tcl/tclmagic.so'
        for p in [binary, library]:
            if record['artifacts'][str(p)] != sha(p):
                raise ValueError('native build artifact changed')
        pins.update({str(p): sha(p) for p in [receipt, binary, library]})
        for repeated in [False, True]:
            case = out / (engine_name + '_repeat' + str(int(repeated)))
            case.mkdir()
            rc = case / 'minimal.magicrc'; rc.write_text(f'tech load {{{TECH}}}\n')
            script = case / 'run.tcl'
            recipe = baseline.replace('extract style ngspice()', (addition if repeated else '') + 'extract style ngspice()')
            script.write_text(f'cd {{{case}}}\n' + recipe)
            pins.update({str(p): sha(p) for p in [rc, script]})
            with lease(1, 2, deadline):
                execute(['env', 'OPENPLL_RC_NATIVE_CAPS=1', 'OPENPLL_RC_EXPLICIT_COUPLING=1',
                         'OPENPLL_RC_ZERO_JUNCTION=1', str(binary), '-nowrapper', '-dnull',
                         '-noconsole', '-rcfile', str(rc), str(script)], case / 'native.log',
                        min(deadline, time.clock_gettime(time.CLOCK_BOOTTIME) + 120), 2)
            before, after = [(case / n).read_text() for n in ['before.spice', 'after.spice']]
            parsed = parse(after); locations = defaultdict(set)
            for line in (case / 'OpenPLL_Coupling_R_Probe.res.ext').read_text().splitlines():
                if line.startswith('rnode '):
                    f = shlex.split(line); locations[f[1]].add(tuple(f[4:6]))
            value = effective_R(parsed['resistors'], 'a', 'afar')
            rows.append(dict(engine=engine_name, repeated_labels=repeated,
                 effective_A_AFAR_ohms_exact=str(value), effective_A_AFAR_ohms=float(value),
                 formal_ports_preserved=parse(before)['ports'] == parsed['ports'],
                 duplicate_names_at_distinct_points={n: sorted(v) for n, v in locations.items() if len(v) > 1},
                 resistor_selfloops=sum(a == b for a, b, v in parsed['resistors'])))
    for p, h in pins.items():
        if sha(p) != h:
            raise ValueError('control input changed')
    save(out / 'assessment.json', dict(input_sha256=pins, results=rows,
         artifacts={str(p): sha(p) for p in out.glob('*/*') if p.is_file()},
         RC_export_fixed=False, release_ready=False))
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    run()
