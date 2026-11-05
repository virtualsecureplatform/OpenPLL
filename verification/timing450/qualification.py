#!/usr/bin/env python3
"""Inventory exact release PVT coverage; diagnostic corners do not imply it."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re

from run import DEFAULT_PDK, REPO


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', choices=['hd', 'hs'], default='hd')
    parser.add_argument('--pdk-root', default=DEFAULT_PDK)
    args = parser.parse_args()
    specification = REPO / 'verification/engineering.json'
    requirements = json.loads(specification.read_text())
    scl = 'sky130_fd_sc_' + args.library
    libroot = Path(args.pdk_root) / 'sky130A/libs.ref' / scl / 'lib'
    if not libroot.is_dir():
        raise RuntimeError(f'Library directory missing: {libroot}; run inside the pinned container')
    models = []
    for source in sorted(libroot.glob('*.lib')):
        content = source.read_text()
        process = re.search(r'__(tt|ff|ss|sf|fs)_', source.name)
        voltage = re.search(r'\bnom_voltage\s*:\s*([\d.]+)', content)
        temperature = re.search(r'\bnom_temperature\s*:\s*(-?[\d.]+)', content)
        if process and voltage and temperature:
            models.append({'corner': process[1], 'voltage': float(voltage[1]),
                           'temperature_c': float(temperature[1]), 'path': str(source),
                           'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
    if not models:
        raise RuntimeError(f'No characterized cell models found in {libroot}')
    points = []
    for corner, voltage, temperature in itertools.product(requirements['corners'], requirements['voltages'], requirements['temperatures_c']):
        matching = [m['path'] for m in models if m['corner'] == corner and m['voltage'] == voltage and m['temperature_c'] == temperature]
        points.append({'corner': corner, 'voltage': voltage, 'temperature_c': temperature,
                       'exact_models': matching})
    root = REPO / 'build/timing450' / args.library
    result = {'release_qualified': False, 'selected': False,
              'shared_supply_maximum_v': max(requirements['voltages']),
              'required_pvt_points': len(points), 'required_mode_pvt_points': len(points) * len(requirements['modes_mhz']),
              'exact_cell_model_points': sum(bool(p['exact_models']) for p in points),
              'requirements_sha256': hashlib.sha256(specification.read_bytes()).hexdigest(),
              'cell_models': models, 'pvt_grid': points,
              'open_gates': ['Complete extracted timing across five modes and the required PVT grid',
                             'Measured interface loads, pulse widths, CDC resolution and bundled-data skew',
                             'Candidate-owned independent DRC/LVS and antenna/EM/IR evidence',
                             'Whole-PLL analog and closed-loop PVT qualification with the 1.95 V ceiling']}
    (root / 'qualification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['shared_supply_maximum_v', 'required_pvt_points', 'required_mode_pvt_points', 'exact_cell_model_points', 'release_qualified']}))


if __name__ == '__main__':
    main()
