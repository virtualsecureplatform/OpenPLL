#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate fixed-geometry diode comparison evidence, separately from PLL signoff."""
import argparse
import itertools
import json
import math
from pathlib import Path

from pvt_release_gate import has_xyce_temperature
from sky130_diode_translation_probe import MODEL_SHA256, charge, data_rows, digest, tree_digest

CORNERS = ('tt', 'ff', 'ss', 'sf', 'fs')
TEMPERATURES = (-40, 27, 125)
BIASES = (0, .81, 1.62, 1.8, 1.98)
LIMITS = {'dc_relative_error': .001, 'ac_complex_current_relative_error': .0001,
          'ac_imaginary_current_relative_error': .0001, 'charge_relative_error': .001,
          'falling_charge_relative_error': .001, 'output_noise_psd_relative_error': .001}


def coverage(cases, noise=False):
    keys = [(c['corner'], c['temperature_c'], c['bias_v']) if noise else
            (c['corner'], c['temperature_c']) for c in cases]
    expected = set(itertools.product(CORNERS, TEMPERATURES, BIASES) if noise else
                   itertools.product(CORNERS, TEMPERATURES))
    if len(keys) != len(expected) or set(keys) != expected:
        raise ValueError('incomplete or duplicate diode comparison coverage')
    for case in cases:
        if case['screen_passed'] is not True:
            raise ValueError('failed comparison case')
        for key, limit in LIMITS.items():
            if key in case and (not math.isfinite(case[key]) or not 0 <= case[key] < limit):
                raise ValueError(f'invalid or failing {key}')


def aligned(a, b, count):
    if len(a) != count or len(b) != count or any(
            not all(math.isfinite(v) for v in row) for row in a + b):
        raise ValueError('incomplete or nonfinite simulation output')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--electrical', type=Path, required=True)
    parser.add_argument('--noise', type=Path, required=True)
    parser.add_argument('--pdk', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    electrical, noise = args.electrical.resolve(), args.noise.resolve()
    e = json.loads(electrical.read_text()); n = json.loads(noise.read_text())
    coverage(e['cases']); coverage(n['cases'], True)
    if (e['reference_geometry'] != 'explicit' or set(e['ac_biases_v']) != set(BIASES)
            or not e['all_screens_passed'] or not n['all_screens_passed']
            or n['reference_units'] != 'V^2/Hz (set sqrnoise)' or n['transimpedance_ohm'] != 1000):
        raise ValueError('unexpected comparison configuration')
    hashes = {str(electrical): digest(electrical), str(noise): digest(noise)}
    for report in (e, n):
        for path, value in report['input_sha256'].items():
            if path == 'pdk_tree':
                if tree_digest(args.pdk.resolve()) != value:
                    raise ValueError('PDK tree changed')
                continue
            if path in hashes and hashes[path] != value:
                raise ValueError('conflicting input provenance')
            hashes[path] = value
    if any(digest(Path(path)) != value for path, value in hashes.items()):
        raise ValueError('comparison inputs changed')
    model = args.pdk / 'libs.ref/sky130_fd_pr/spice/sky130_fd_pr__diode_pw2nd_05v5.model.spice'
    if digest(model) != MODEL_SHA256:
        raise ValueError('unexpected PDK diode model')
    for c in e['cases']:
        folder = electrical.parent / f"{c['corner']}_{c['temperature_c']:g}C"
        deck = (folder / 'xyce_dc.cir').read_text()
        if not has_xyce_temperature(deck, c['temperature_c']):
            raise ValueError('wrong Xyce temperature directive')
        a, b = data_rows(folder / 'ngspice_dc.log'), data_rows(folder / 'xyce_dc.prn')
        aligned(a, b, 110)
        if any(abs(x[-2] - y[-2]) > 1e-10 for x, y in zip(a, b)):
            raise ValueError('DC biases differ')
        if max(abs(x[-1] - y[-1]) / max(abs(x[-1]), 1e-18) for x, y in zip(a, b)) >= .001:
            raise ValueError('raw DC comparison fails')
        for bias in BIASES:
            a = data_rows(folder / f'ngspice_ac_{bias:g}V.log')
            b = data_rows(folder / f'xyce_ac_{bias:g}V.FD.prn')
            aligned(a, b, 21)
            if any(abs(x[0] / y[0] - 1) > 1e-6 for x, y in zip(a, b)):
                raise ValueError('AC frequencies differ')
            if max(abs(complex(*x[-2:]) - complex(*y[-2:])) / abs(complex(*x[-2:]))
                   for x, y in zip(a, b)) >= .0001:
                raise ValueError('raw AC comparison fails')
        a, b = data_rows(folder / 'ngspice_tran.log'), data_rows(folder / 'xyce_tran.prn')
        for start, stop in ((.9e-9, 1.5e-9), (5e-9, 5.6e-9)):
            qa, qb = charge(a, start, stop), charge(b, start, stop)
            if abs(qa - qb) / abs(qa) >= .001:
                raise ValueError('raw charge comparison fails')
    for c in n['cases']:
        folder = noise.parent / f"{c['corner']}_{c['temperature_c']:g}C_{c['bias_v']:g}V"
        a, b = data_rows(folder / 'ngspice.log'), data_rows(folder / 'xyce.NOISE.prn')
        aligned(a, b, 21)
        if any(x[-1] <= 0 or y[-1] <= 0 or abs(x[0] / y[0] - 1) > 1e-6 for x, y in zip(a, b)):
            raise ValueError('invalid raw noise spectrum')
        if max(abs(x[-1] - y[-1]) / x[-1] for x, y in zip(a, b)) >= .001:
            raise ValueError('raw noise comparison fails')
    for folder in (electrical.parent, noise.parent):
        hashes.update({str(p): digest(p) for p in folder.rglob('*') if p.is_file()})
    result = {'model_equivalence_screen_passed': True, 'pll_release_qualified': False,
              'scope': 'fixed effective area .4347 and perimeter 2.64; DC bias -.2..1.98 V; AC/noise 1MHz..10GHz',
              'corners': CORNERS, 'temperatures_c': TEMPERATURES, 'ac_noise_biases_v': BIASES,
              'limits': LIMITS, 'evidence_sha256': hashes}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: fixed-geometry diode model evidence; PLL release remains unqualified')


if __name__ == '__main__':
    main()
