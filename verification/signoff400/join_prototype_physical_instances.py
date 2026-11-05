"""Regenerate the routed-to-extracted instance join using an independently measured grid."""
import argparse
from collections import Counter
from fractions import Fraction as F
from pathlib import Path
import shlex

from common import save, sha, verify
from prepare_prototype_analog_reference import subcircuits

ORIENTATIONS = {'R0': (1, 0, 0, 1), 'MX': (1, 0, 0, -1),
                'MY': (-1, 0, 0, 1), 'R180': (-1, 0, 0, -1)}


def dimensions(ext, spice, cell):
    extracted = []
    for line in ext.splitlines():
        f = shlex.split(line)
        if f[:2] != ['device', 'msubckt']:
            continue
        params = dict(t.split('=', 1) for t in f if '=' in t)
        extracted.append((f[2], F(params['l']), F(params['w'])))
    native = []
    for line in subcircuits(spice)[cell].splitlines():
        if not line.startswith('X'):
            continue
        f = line.split()
        params = dict(t.split('=', 1) for t in f if '=' in t)
        native.append((f[5], F(params['l']), F(params['w'])))
    if not extracted or len(extracted) != len(native):
        raise ValueError('independent primitive dimension controls missing')
    scales = {n[1] / e[1] for n in native for e in extracted if n[0] == e[0]}
    valid = [scale for scale in scales if
             Counter((m, l * scale, w * scale) for m, l, w in extracted) == Counter(native)]
    if len(valid) != 1:
        raise ValueError('ambiguous or inconsistent extraction grid')
    return valid[0], len(native)


def join(placements, top_ext, grid_um):
    lines = placements.splitlines()
    if not lines or not lines[0].startswith('UNITS\t'):
        raise ValueError('database units missing')
    scale = F(lines[0].split('\t')[1]) * grid_um
    extracted = {}
    for line in top_ext.splitlines():
        f = line.split()
        if not f or f[0] != 'use':
            continue
        a, b, x, c, d, y = map(int, f[3:9])
        key = (f[1], (a, b, c, d), F(x) * scale, F(y) * scale)
        extracted.setdefault(key, []).append(f[2])
    result = []
    used = set()
    for line in lines[1:]:
        f = line.split('\t')
        if len(f) != 8 or f[0] != 'INST' or f[3] not in ORIENTATIONS:
            raise ValueError('unreviewed placement record or orientation')
        _, name, master, orientation, x, y, _, _ = f
        candidates = extracted.get((master, ORIENTATIONS[orientation], F(x), F(y)), [])
        if len(candidates) != 1 or candidates[0] in used:
            raise ValueError('placement does not have a unique extracted instance')
        used.add(candidates[0])
        result.append(dict(routed_instance=name, extracted_instance=candidates[0],
                           master=master, x_dbu=int(x), y_dbu=int(y), orientation=orientation))
    if not result or len({r['routed_instance'] for r in result}) != len(result):
        raise ValueError('missing or duplicate routed instances')
    # Via geometry is deliberately excluded; every extracted standard cell must join.
    cell_instances = {name for key, names in extracted.items()
                      if key[0].startswith('sky130_fd_sc_') for name in names}
    if used != cell_instances:
        raise ValueError('extracted standard-cell coverage incomplete')
    return result, scale


def run(placements, top_ext, cell_ext, spice, cell, output):
    output.mkdir(parents=True, exist_ok=False)
    paths = [placements, top_ext, cell_ext, spice, Path(__file__).resolve()]
    pins = {str(p): sha(p) for p in paths}
    grid, controls = dimensions(cell_ext.read_text(), spice.read_text(), cell)
    mapping, scale = join(placements.read_text(), top_ext.read_text(), grid)
    target = output / 'join.json'
    save(target, dict(mapping=mapping))
    verify(pins)
    save(output / 'assessment.json', dict(input_sha256=pins, artifacts={str(target): sha(target)},
         exact_primitive_length_width_grid_match=True, primitive_controls=controls,
         magic_grid_um=str(grid), database_units_per_magic_unit=str(scale),
         all_instance_placements_match=True, matched_instances=len(mapping),
         validated_for_prototype=False, release_ready=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('placements', 'top-ext', 'cell-ext', 'spice', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--cell', required=True)
    a = p.parse_args()
    run(a.placements.resolve(), a.top_ext.resolve(), a.cell_ext.resolve(),
        a.spice.resolve(), a.cell, a.output.resolve())
