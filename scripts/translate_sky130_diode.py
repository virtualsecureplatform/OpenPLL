#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Translate only the diode geometry covered by checked comparison evidence."""
import argparse
import json
from pathlib import Path
import re

from sky130_diode_translation_probe import MODEL_SHA256, digest, translated_model

DEVICE = 'sky130_fd_pr__diode_pw2nd_05v5'
REPLACEMENT = 'openpll_pw2nd_qualified_geometry'


def translate(text):
    lines, count = [], 0
    for line in text.splitlines():
        if line.lstrip().startswith('*') or DEVICE not in line.lower():
            lines.append(line)
            continue
        fields = line.split()
        if (len(fields) != 6 or not fields[0].lower().startswith('x')
                or fields[3].lower() != DEVICE):
            raise ValueError('unsupported diode statement or continued instance')
        parameters = {}
        for token in fields[4:]:
            key, value = token.lower().split('=', 1)
            if key in parameters:
                raise ValueError('duplicate diode parameter')
            parameters[key] = float(value)
        if parameters != {'area': 4.347e11, 'perim': 2.64e6}:
            raise ValueError('diode geometry outside checked scope')
        lines.append(' '.join(fields[:3] + [REPLACEMENT]))
        count += 1
    if not count or re.search(r'(?im)^\s*\.end\s*$', text) or REPLACEMENT in text:
        raise ValueError('expected a fresh extracted include containing qualified diode instances')
    return '\n'.join(lines) + '\n', count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qualification', type=Path, required=True)
    parser.add_argument('--electrical', type=Path, required=True)
    parser.add_argument('--pdk', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--corner', choices=('tt', 'ss', 'ff', 'sf', 'fs'), required=True)
    parser.add_argument('--temperature-c', type=float, choices=(-40, 27, 125), required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix('.translation.json').exists():
        parser.error('use a fresh output path')
    qualified = json.loads(args.qualification.read_text())
    if qualified.get('model_equivalence_screen_passed') is not True:
        raise ValueError('missing checked model evidence')
    hashes = qualified['evidence_sha256']
    if str(args.electrical.resolve()) not in hashes:
        raise ValueError('electrical report is not covered by qualification evidence')
    if any(digest(Path(path)) != value for path, value in hashes.items()):
        raise ValueError('qualification evidence changed')
    model = args.pdk / 'libs.ref/sky130_fd_pr/spice/sky130_fd_pr__diode_pw2nd_05v5.model.spice'
    if digest(model) != MODEL_SHA256:
        raise ValueError('PDK model differs from checked model')
    electrical = json.loads(args.electrical.read_text())
    aj, pj = electrical['corner_parameters'][args.corner]
    text, count = translate(args.input.read_text())
    text += ('\n* Fixed geometry model-equivalence screen; assembled PLL remains unqualified.\n'
             + translated_model(args.temperature_c, aj, pj)
             + f'.subckt {REPLACEMENT} N P\n'
             + 'D0 N P openpll_pw2nd_candidate area=.4347 pj=2.64\n'
             + f'.ends {REPLACEMENT}\n')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text)
    report = {'pll_release_qualified': False, 'translated_instances': count,
              'corner': args.corner, 'temperature_c': args.temperature_c,
              'required_global_temperature_c': args.temperature_c,
              'effective_geometry': {'area': .4347, 'perimeter': 2.64},
              'input_sha256': digest(args.input), 'output_sha256': digest(args.output),
              'qualification_sha256': digest(args.qualification), 'pdk_model_sha256': digest(model)}
    args.output.with_suffix('.translation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Translated {count} checked-geometry diode instances; PLL qualification remains open')


if __name__ == '__main__':
    main()
