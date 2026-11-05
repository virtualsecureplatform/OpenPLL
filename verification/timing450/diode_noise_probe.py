#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Diagnostic noise comparison using previously generated diode AC decks."""
import argparse
import concurrent.futures
import json
from pathlib import Path
import re
import subprocess

from diode_translation_probe_v2 import data_rows, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--grid', type=Path, required=True)
    parser.add_argument('--ngspice', type=Path, required=True)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    grid = args.grid.resolve(strict=True)
    ngspice = args.ngspice.resolve(strict=True)
    image = args.image.resolve(strict=True)
    out = args.output.resolve()
    report = json.loads((grid / 'summary.json').read_text())
    if not report['all_screens_passed'] or args.jobs < 1 or out.exists():
        parser.error('use a passing diagnostic grid, positive jobs, and a fresh output directory')
    tasks = [(c['corner'], c['temperature_c'], bias)
             for c in report['cases'] for bias in report['ac_biases_v']]
    out.mkdir(parents=True)
    hashes = {str(p): digest(p) for p in [grid / 'summary.json', ngspice, image, Path(__file__)]}
    source_decks = [grid / f'{c}_{t:g}C' / f'{s}_ac_{v:g}V.cir'
                    for c, t, v in tasks for s in ('ngspice', 'xyce')]
    hashes.update({str(p): digest(p) for p in source_decks})
    for deck in source_decks:
        for name in re.findall(r'(?im)^\.include\s+"([^"]+)"', deck.read_text()):
            included = Path(name)
            if not included.is_absolute():
                included = deck.parent / included
            hashes[str(included.resolve(strict=True))] = digest(included)
    prefix = ['apptainer', 'exec', '--userns', '--writable-tmpfs', '--cleanenv',
              '--bind', f'{root}:{root}', '--pwd', str(root), str(image),
              '/opt/xyce/bin/Xyce', '-linsolv', 'KLU']

    def case(task):
        corner, temperature, bias = task
        folder = out / f'{corner}_{temperature:g}C_{bias:g}V'
        folder.mkdir()
        outputs = {}
        for simulator in ('ngspice', 'xyce'):
            source = grid / f'{corner}_{temperature:g}C' / f'{simulator}_ac_{bias:g}V.cir'
            lines = source.read_text().splitlines()
            lines = [line for line in lines if not re.match(r'^\.(ac|print|end)\s*$', line, re.I)
                     and not re.match(r'^\.(ac|print)\s', line, re.I)]
            # Keep .ends intact. Use a moderate transimpedance to avoid ill conditioning.
            lines += ['Bsense witness 0 V={1e3*I(Vbias)}']
            if simulator == 'ngspice':
                lines += ['.control', 'set sqrnoise', 'set numdgt=15',
                          'noise V(witness) Vbias dec 5 1meg 10g',
                          'setplot noise1', 'print onoise_spectrum', '.endc', '.end']
            else:
                lines += ['.noise V(witness) Vbias dec 5 1meg 10g', '.print noise onoise', '.end']
            deck = folder / f'{simulator}.cir'
            deck.write_text('\n'.join(lines) + '\n')
            log = folder / f'{simulator}.log'
            command = ([str(ngspice), '-b'] if simulator == 'ngspice' else
                       prefix + ['-o', str(folder / simulator)])
            with log.open('w') as output:
                result = subprocess.run(command + [str(deck)], cwd=folder,
                                        stdout=output, stderr=subprocess.STDOUT, timeout=120)
            if result.returncode:
                raise RuntimeError(f'noise simulation failed: {log}')
            rows = data_rows(log if simulator == 'ngspice' else folder / 'xyce.NOISE.prn')
            if len(rows) != 21 or any(len(r) != 2 or r[-1] <= 0 for r in rows):
                raise ValueError(f'incomplete or invalid noise spectrum: {log}')
            outputs[simulator] = rows
        ref, got = outputs['ngspice'], outputs['xyce']
        if any(abs(a[0] / b[0] - 1) > 1e-6 for a, b in zip(ref, got)):
            raise ValueError('noise frequencies differ')
        error = max(abs(a[-1] - b[-1]) / a[-1] for a, b in zip(ref, got))
        return {'corner': corner, 'temperature_c': temperature, 'bias_v': bias,
                'output_noise_psd_relative_error': error, 'screen_passed': error < .001}

    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(case, tasks))
    if any(digest(Path(p)) != value for p, value in hashes.items()):
        raise ValueError('noise diagnostic inputs changed during execution')
    result = {'qualified': False, 'scope': 'diagnostic small signal noise spectra only',
              'transimpedance_ohm': 1000, 'reference_units': 'V^2/Hz (set sqrnoise)',
              'input_sha256': hashes, 'cases': results,
              'all_screens_passed': all(c['screen_passed'] for c in results)}
    (out / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'cases': len(results), 'all_screens_passed': result['all_screens_passed'],
                      'max_relative_error': max(c['output_noise_psd_relative_error'] for c in results)}, indent=2))
    return 0 if result['all_screens_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
