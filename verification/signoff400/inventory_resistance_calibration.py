#!/usr/bin/env python3
"""Quantify candidate sheet-model mismatches without modifying extracted R."""
import argparse
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import re

from nominal_sheet_resistance_v3 import parse

CANDIDATES = {
    'poly': 'po', 'locali': 'l1', 'nwell': 'nw', 'ndiff': 'nd', 'pdiff': 'pd',
    'nsubdiff': 'nd', 'psubdiff': 'pd',
    **{'metal'+str(i): 'm'+str(i) for i in range(1, 6)},
    **{m: 'po' for m in ('scnmos', 'scpmos', 'scnmoslvt', 'scpmoshvt')},
}


def run(args):
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    registry = json.loads((args.laws/'registry.json').read_text())
    native = json.loads(args.native.read_text())
    tech = args.tech.read_bytes()
    digest = hashlib.sha256(tech).hexdigest()
    if native['input_sha256'].get(str(args.tech.resolve())) != digest:
        raise ValueError('Magic technology differs from native arithmetic receipt')
    sheets = parse(tech.decode())
    path = args.laws/'sources/r+c/res_typical__cap_typical.spice'
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != registry['sources']['r+c/res_typical__cap_typical.spice']['sha256']:
        raise ValueError('PDK nominal model parameters changed')
    constants = {}
    for line in data.decode().splitlines():
        match = re.fullmatch(r'\+\s*(\w+)\s*=\s*([+\-\d.eE]+)\s*', line)
        if match:
            if match[1] in constants:
                raise ValueError('duplicate nominal parameter')
            constants[match[1]] = F(match[2])
    models = {m['name']:m for m in registry['models']}
    counts = native['material_counts']
    rows = []
    for material, count in sorted(counts.items()):
        row = dict(material=material, segments=count['native_segments'],
                   magic_sheet_ohm=str(sheets[material]/1000) if material in sheets else None,
                   proposed_model=None, nominal_match=None, physical_mapping_qualified=False,
                   magic_reference_temperature_known=False)
        if material in CANDIDATES:
            name = 'sky130_fd_pr__res_generic_'+CANDIDATES[material]
            model = models[name]
            matches = re.findall(r'\brsh\s*=\s*\{?(\w+)\}?',model['source_declaration'])
            if len(matches) != 1 or matches[0] not in constants:
                raise ValueError('ambiguous sheet parameter')
            nominal = constants[matches[0]]
            magic = sheets[material]/1000
            row.update(proposed_model=name, model_sheet_ohm=str(nominal),
                       nominal_match=magic==nominal, model_tnom_c=model['tnom_c'],
                       model_minus_magic_fraction=str((nominal-magic)/magic),
                       tc1=model['tc1'], tc2=model['tc2'])
        rows.append(row)
    if set(counts)-set(CANDIDATES) != {'pwell','ndiode'}:
        raise ValueError('unreviewed missing material model')
    total = sum(r['segments'] for r in rows)
    if total != native['counts']['native_segments']:
        raise ValueError('incomplete segment inventory')
    pins = {str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (args.native, args.tech, args.laws/'registry.json', path, Path(__file__),
             Path(__file__).with_name('nominal_sheet_resistance.py'),
             Path(__file__).with_name('nominal_sheet_resistance_v2.py'),
             Path(__file__).with_name('nominal_sheet_resistance_v3.py'))}
    result = dict(status='inventory_complete', native_segments=total, materials=rows,
                  segments_without_candidate_model=sum(r['segments'] for r in rows if r['proposed_model'] is None),
                  segments_with_nominal_mismatch=sum(r['segments'] for r in rows if r['nominal_match'] is False),
                  all_segments_lack_established_magic_reference_temperature=True,
                  input_sha256=pins, contacts_in_scope=False, extracted_resistors_modified=False,
                  resistance_PVT_qualified=False, release_qualified=False)
    (out/'assessment.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('materials','input_sha256')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--laws', required=True, type=Path)
    p.add_argument('--native', required=True, type=Path)
    p.add_argument('--tech', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    run(p.parse_args())
