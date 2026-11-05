#!/usr/bin/env python3
"""Repeat candidate-owned KLayout checks inside the pinned release container."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

from run import DEFAULT_PDK, REPO

KLAYOUT = '/nix/store/c8mymw0gckkiw7lqwnm2l6mqnd99xmzy-klayout-0.30.7/bin/klayout'
PYTHON = '/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3'
TOP = 'IntegerPLL_AcquiringCore'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_hash(path, evidence):
    if evidence.get(str(path)) != sha(path):
        raise RuntimeError(f'Missing or stale signoff evidence: {path}')


def report_count(path, require_categories=True):
    root = ET.parse(path).getroot()
    if (root.tag != 'report-database' or root.findtext('top-cell') != TOP
            or root.find('items') is None or root.find('categories') is None):
        raise RuntimeError(f'Incomplete KLayout report: {path}')
    if require_categories and not len(root.find('categories')):
        raise RuntimeError(f'No rule categories in KLayout report: {path}')
    return len(root.find('items'))


def density_ratios(text):
    values = {k: float(v) for k, v in re.findall(
        r'(li1|m[1-5])_ca_density is (\S+)', text)}
    if (set(values) != {'li1', 'm1', 'm2', 'm3', 'm4', 'm5'}
            or not all(math.isfinite(v) and 0 <= v <= 1 for v in values.values())):
        raise RuntimeError('Missing or invalid global clear-area density ratios')
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', choices=['hd', 'hs'], default='hd')
    parser.add_argument('--pdk-root', default=DEFAULT_PDK)
    parser.add_argument('--stage', choices=['full', 'global-density', 'all'], default='all')
    args = parser.parse_args()
    candidate = REPO / 'build/timing450' / args.library
    output = candidate / 'signoff/klayout_checks'
    output.mkdir(exist_ok=True)
    stages = ['full', 'global-density'] if args.stage == 'all' else [args.stage]
    for stage in stages:
        (output / f'{stage}_assessment.json').unlink(missing_ok=True)
    evidence = json.loads((candidate / 'signoff/assessment.json').read_text())['sha256']
    gds = candidate / 'signoff/route.gds'
    for path in (gds, candidate / 'route.odb'):
        require_hash(path, evidence)
    inputs = {str(path): sha(path) for path in (gds, candidate / 'route.odb')}
    probe = output / 'geometry.py'
    probe.write_text('''import json, pya, sys
l = pya.Layout()
l.read(sys.argv[1])
c = l.cell(sys.argv[2])
if c is None: raise RuntimeError("Missing candidate top cell")
print(json.dumps({"top": c.name, "bbox_area_dbu2": c.bbox().area(),
                  "instances": sum(1 for _ in c.each_inst()),
                  "cells": l.cells(), "layers": l.layers()}))
''')
    geometry_file = output / 'geometry.json'
    with geometry_file.open('w') as stream:
        subprocess.run([PYTHON, str(probe), str(gds), TOP], stdout=stream, check=True)
    geometry = json.loads(geometry_file.read_text())
    if any(geometry[k] <= 0 for k in ('bbox_area_dbu2', 'instances', 'cells', 'layers')):
        raise RuntimeError('Empty candidate geometry')
    failed = False
    for stage in stages:
        deck_dir = Path(args.pdk_root) / 'sky130A/libs.tech/klayout/drc'
        deck = deck_dir / ('sky130A_mr.drc' if stage == 'full' else 'met_min_ca_density.lydrc')
        report = output / f'{stage}.lyrdb'
        report.unlink(missing_ok=True)
        command = [KLAYOUT, '-b', '-r', str(deck), '-rd', f'input={gds}',
                   '-rd', f'top_cell={TOP}', '-rd', f'report={report}']
        if stage == 'full':
            for key in ('feol', 'beol', 'offgrid', 'floating_met', 'seal'):
                command += ['-rd', f'{key}=true']
            command += ['-rd', 'sram_exclude=false', '-rd', 'thr=4']
        recipe = output / f'{stage}_command.json'
        recipe.write_text(json.dumps(command, indent=2) + '\n')
        log = output / f'{stage}.log'
        with log.open('w') as stream:
            subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                           env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'}, check=True)
        count = report_count(report, require_categories=stage == 'full')
        values = density_ratios(log.read_text()) if stage == 'global-density' else None
        passed = count == 0 and (values is None or all(
            v >= (.24 if k == 'm5' else .4) for k, v in values.items()))
        # Reject a route/GDS change during the check as well as before it.
        for path, digest in inputs.items():
            if sha(path) != digest:
                raise RuntimeError(f'Candidate changed during KLayout checks: {path}')
        result = {'pass': passed, 'release_qualified': False, 'selected': False,
                  'stage': stage, 'violations': count, 'geometry': geometry,
                  'clear_area_ratios': values,
                  'limitations': ['Global clear-area ratios do not establish full windowed density qualification',
                                  'Antenna, EM/IR, PVT, interface and whole-PLL qualification remain separate gates'],
                  'sha256': {str(p): sha(p) for p in [gds, candidate / 'route.odb', deck,
                              recipe, log, report, probe, geometry_file, Path(__file__)]}}
        (output / f'{stage}_assessment.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'stage': stage, 'pass': passed, 'violations': count}), flush=True)
        failed |= not passed
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
