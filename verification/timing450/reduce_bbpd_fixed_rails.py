#!/usr/bin/env python3
"""Remove isolated MOS loads on ideal constant rails for signal-only transients."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

RAILS = {'VPWR', 'VPB', 'VGND', 'VNB'}
MODELS = {'sky130_fd_pr__nfet_01v8', 'sky130_fd_pr__pfet_01v8_hvt'}


def reduce(text):
    result, removed = [], []
    active, tops = False, 0
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0].lower() == '.subckt':
            if active:
                raise RuntimeError('Nested BBPD subcircuit')
            active = fields[1] == 'IntegerPLL_BBPD'
            tops += int(active)
        if (active and len(fields) >= 6 and re.fullmatch(r'X\d+', fields[0])
                and fields[5] in MODELS and set(fields[1:5]) <= RAILS):
            removed.append({'instance': fields[0], 'terminals': fields[1:5],
                            'model': fields[5], 'statement': line})
        else:
            result.append(line)
        if fields and fields[0].lower() == '.ends':
            active = False
    if active or tops != 1 or not removed:
        raise RuntimeError('Missing/unterminated BBPD or no isolated fixed-rail MOS loads')
    return '\n'.join(result) + '\n', removed


def verify_ideal_rails(deck):
    number = r'[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?'
    supply = re.findall(r'^\.param VDD=(' + number + r')\s*$', deck, re.M | re.I)
    temperature = re.findall(r'^\.options device temp=(' + number + r')\s*$', deck, re.M | re.I)
    if (len(supply) != 1 or len(temperature) != 1
            or not math.isfinite(float(supply[0])) or not 0 < float(supply[0]) <= 1.95
            or not math.isfinite(float(temperature[0])) or float(temperature[0]) <= -273.15):
        raise RuntimeError('Reduction requires fixed numeric supply and global temperature')
    for name, node, value in [('VVPWR', 'VPWR', '{VDD}'), ('VVPB', 'VPB', '{VDD}'),
                              ('VVGND', 'VGND', '0'), ('VVNB', 'VNB', '0')]:
        pattern = '^' + name + r'\s+' + node + r'\s+0\s+' + re.escape(value) + r'\s*$'
        if len(re.findall(pattern, deck, re.M | re.I)) != 1:
            raise RuntimeError('Reduction requires explicit ideal constant rail sources')
    if re.search(r'(?im)^\s*\.(?:noise|ac|dc)\b', deck):
        raise RuntimeError('This reduction is for deterministic signal transients only')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--deck', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output file')
    verify_ideal_rails(args.deck.read_text())
    text, removed = reduce(args.input.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text)
    receipt = {'release_qualified': False, 'selected': False, 'removed_instances': removed,
               'removed_count': len(removed),
               'scope': 'Signal voltages with ideal constant rails and fixed global temperature',
               'limitations': ['Supply current/power/noise and nonideal supply behavior are not preserved',
                               'Full versus reduced signal waveform comparison remains required'],
               'sha256': {str(p.resolve()): sha(p) for p in
                          [args.input, args.deck, args.output, Path(__file__)]}}
    args.output.with_suffix('.reduction.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(f'Removed {len(removed)} fixed-rail-only MOS instances; signal waveform comparison required')


if __name__ == '__main__':
    main()
