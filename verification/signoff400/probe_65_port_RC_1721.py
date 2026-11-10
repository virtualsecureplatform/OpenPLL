"""Analytical wire stress control: 65 physical ports, an analytical wire and 1,000 repeated labels."""
import json
import os
import shlex
import time
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path
from runtime_common import ROOT, save, sha
from resources import lease
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import TECH
from audit_keeper_native_R_contraction import parse
from native_C_roundoff import assess
from native_wire_values import assess as wire_values


def tree_path_resistance(resistors, first, last):
    parent = {}
    def root(n):
        parent.setdefault(n, n)
        while parent[n] != n:
            parent[n] = parent[parent[n]]; n = parent[n]
        return n
    for a, b, value in resistors:
        if value < 0:
            raise ValueError('negative native resistance')
        if value == 0:
            parent[root(a)] = root(b)
    first, last = root(first), root(last)
    if first == last:
        raise ValueError('wire bypassed by an ideal alias')
    conductance = defaultdict(F)
    for a, b, value in resistors:
        a, b = root(a), root(b)
        if value and a != b:
            conductance[tuple(sorted((a, b)))] += 1 / value
    graph = defaultdict(dict)
    for (a, b), value in conductance.items():
        graph[a][b] = graph[b][a] = 1 / value
    reached, pending = {first: (None, F(0))}, [first]
    while pending:
        a = pending.pop()
        for b, value in graph[a].items():
            if b not in reached:
                reached[b] = (a, value); pending.append(b)
    if last not in reached:
        raise ValueError('wire control disconnected')
    if sum(len(graph[n]) for n in reached) != 2 * (len(reached) - 1):
        raise ValueError('analytical series-wire control must remain a tree')
    total = F(0); current = last
    while current != first:
        current, value = reached[current]; total += value
    return total


def run():
    out = ROOT / 'build/signoff400/selected_65_port_RC_1721'
    out.mkdir(exist_ok=False)
    os.sched_setaffinity(0, {28})
    recipe = ['drc off', 'crashbackups disable', 'locking disable',
              'load PortStress', 'box values 0 0 4000 100', 'paint m1',
              'box values 0 0 20 100', 'label P0 center m1', 'port make 1',
              'box values 3980 0 4000 100', 'label P1 center m1', 'port make 2']
    for i in range(63):
        y = 400 + 200 * i
        recipe += [f'box values 0 {y} 20 {y+100}', 'paint m1',
                   f'label ISOLATED_{i} center m1', f'port make {i+3}']
    for i in range(500):
        for x in [1200, 2700]:
            recipe += [f'box values {x} 0 {x+20} 100', f'label LOAD_{i} center m1']
    recipe += ['extract style ngspice()', 'extract do local', 'extract do capacitance',
               'extract do coupling', 'extract no resistance', 'extract all',
               'extresist simplify off', 'extresist threshold 0', 'ext2spice lvs',
               'ext2spice hierarchy off', 'ext2spice subcircuit top on',
               'ext2spice short resistor', 'ext2spice cthresh -1e100',
               'ext2spice extresist off', 'ext2spice -o before.spice PortStress.ext',
               'extresist all', 'ext2spice extresist on', 'ext2spice -o after.spice PortStress.ext']
    rows, pins = [], {str(TECH): sha(TECH), str(Path(__file__).resolve()): sha(Path(__file__).resolve())}
    for name in ['magic_single_RC_points_1704', 'magic_indexed_RC_points_1708']:
        engine = ROOT / 'build/tools' / name
        receipt = engine / 'assessment.json'; record = json.loads(receipt.read_text())
        binary = engine / 'install/bin/magic'; library = engine / 'install/lib/magic/tcl/tclmagic.so'
        for p in [binary, library]:
            if record['artifacts'][str(p)] != sha(p):
                raise ValueError('native artifact changed')
        case = out / name; case.mkdir()
        rc = case / 'minimal.magicrc'; rc.write_text(f'tech load {{{TECH}}}\n')
        script = case / 'run.tcl'
        script.write_text(f'cd {{{case}}}\nif {{[catch {{\n' + '\n'.join(recipe)
                          + '\n} error]} {puts stderr $error;exit 1}\nquit -noprompt\n')
        pins.update({str(p): sha(p) for p in [receipt, binary, library, rc, script]})
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 300
        with lease(1, 4, deadline):
            start = time.monotonic()
            execute(['env', 'OPENPLL_RC_NATIVE_CAPS=1', 'OPENPLL_RC_EXPLICIT_COUPLING=1',
                     'OPENPLL_RC_ZERO_JUNCTION=1', str(binary), '-nowrapper', '-dnull',
                     '-noconsole', '-rcfile', str(rc), str(script)], case / 'native.log', deadline, 4)
            elapsed = time.monotonic() - start
        before, after = [(case / n).read_text() for n in ['before.spice', 'after.spice']]
        native = (case / 'PortStress.res.ext').read_text(); data = parse(after)
        locations = defaultdict(set)
        for line in native.splitlines():
            if line.startswith('rnode '):
                f = shlex.split(line); locations[f[1]].add(tuple(f[4:6]))
        value = tree_path_resistance(data['resistors'], 'p0', 'p1')
        rows.append(dict(engine=name, elapsed_s=elapsed, physical_ports=len(data['ports']),
             ordered_ports_preserved=parse(before)['ports'] == data['ports'],
             end_to_end_R_ohms_exact=str(value), end_to_end_R_ohms=float(value),
             analytical_wire_R_preserved=abs(value-F(199,40)) <= F(199,40*2**23),
             duplicate_names_at_distinct_points={n: sorted(v) for n,v in locations.items() if len(v)>1},
             charge=assess(before, after), wires=wire_values(native, after)))
    for name, digest in pins.items():
        if sha(name) != digest:
            raise ValueError('native control input changed')
    passed = all(r['physical_ports'] == 65 and r['ordered_ports_preserved']
        and r['analytical_wire_R_preserved'] and not r['duplicate_names_at_distinct_points']
        and r['charge']['native_devices_and_C_conserved']
        and r['wires']['per_native_wire_resistance_values_verified'] for r in rows)
    save(out / 'assessment.json', dict(input_sha256=pins, results=rows,
         artifacts={str(p): sha(p) for p in out.glob('*/*') if p.is_file()},
         all_65_port_controls_pass=passed, RC_export_fixed=False, release_ready=False))
    print(json.dumps(dict(all_65_port_controls_pass=passed, results=[{k:v for k,v in r.items()
        if k not in ['charge','wires']} for r in rows]), indent=2))


if __name__ == '__main__':
    run()
