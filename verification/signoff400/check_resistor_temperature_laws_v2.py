#!/usr/bin/env python3
"""Pin PDK resistor laws and test their explicit TC1/TC2 translation in Xyce.

This characterizes isolated model temperature factors, not Magic resistance
calibration, geometry, width corrections, or extracted circuit qualification.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import re
import subprocess

NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'


def laws(text):
    constants = {}
    for name, value in re.findall(r'^\s*\.param\s+(\w+)\s*=\s*('+NUMBER+r')\s*$', text, re.M | re.I):
        if name in constants:
            raise ValueError('duplicate constant: '+name)
        constants[name] = value
    result = []
    for name, body in re.findall(r'^\s*\.model\s+(\S+)\s+r\s+(.+)$', text, re.M | re.I):
        if name == 'short' and body.strip() == 'r=0.01':
            continue  # Explicit fixed-R utility model; no temperature law.
        def field(key):
            matches = re.findall(r'\b'+key+r'\s*=\s*(\{[^}]+\}|\S+)', body, re.I)
            if len(matches) != 1:
                raise ValueError('missing/ambiguous '+key+' in '+name)
            return matches[0].strip('{}')
        first, second, nominal = field('tc1r'), field('tc2r'), field('tnom')
        if first not in constants or second not in constants or not re.fullmatch(NUMBER, nominal):
            raise ValueError('unsupported coefficient expression: '+name)
        result.append(dict(name=name, tc1=constants[first], tc2=constants[second],
                           tnom_c=nominal, tc1_parameter=first, tc2_parameter=second,
                           source_declaration=body))
    if not result:
        raise ValueError('no resistor laws')
    return result


def run(args):
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    names = ['sky130.lib.spice', 'sky130_fd_pr__model__r+c.model.spice',
             'r+c/res_typical__cap_typical.spice', 'r+c/res_typical__cap_typical__lin.spice']
    pins, texts = {}, {}
    for name in names:
        source = args.pdk / name
        data = source.read_bytes()
        target = out / 'sources' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        pins[name] = dict(path=str(source.resolve()), sha256=hashlib.sha256(data).hexdigest())
        texts[name] = data.decode()
    models = laws(texts[names[1]])
    selections = {}
    for corner in ('tt', 'ff', 'ss', 'sf', 'fs'):
        blocks = re.findall(r'^\.lib\s+'+corner+r'\s*\n(.*?)^\.endl\s+'+corner+r'\s*$',
                            texts[names[0]], re.M | re.S | re.I)
        if len(blocks) != 1:
            raise ValueError('ambiguous corner library')
        includes = re.findall(r'^\s*\.include\s+"?([^"\s]+)', blocks[0], re.M | re.I)
        selections[corner] = [s for s in includes if s.startswith('r+c/')]
        if selections[corner] != names[2:]:
            raise ValueError('unexpected RC library selection')
    (out/'registry.json').write_text(json.dumps(dict(models=models, sources=pins,
        rc_library_selection=selections, magic_mapping_qualified=False), indent=2)+'\n')

    def probe(temperature):
        directory = out / ('temperature_'+str(temperature))
        directory.mkdir()
        lines = ['Isolated resistor model temperature-law control',
                 '.options device temp='+str(temperature), 'Vdummy dummy 0 0']
        for i, model in enumerate(models):
            lines += [f'V{i} n{i} 0 1', f'R{i} n{i} 0 law{i} 1000',
                      f'.model law{i} R TC1={model["tc1"]} TC2={model["tc2"]} TNOM={model["tnom_c"]}']
        lines += ['.dc Vdummy 0 0 1', '.print dc precision=16 '+ ' '.join(f'I(V{i})' for i in range(len(models))), '.end']
        deck = directory/'law.cir'
        deck.write_text('\n'.join(lines)+'\n')
        with (directory/'solver.log').open('w') as log:
            process = subprocess.run([args.xyce, '-linsolv', 'KLU', str(deck)],
                                     cwd=directory, stdout=log, stderr=subprocess.STDOUT, timeout=120)
        if process.returncode:
            raise ValueError('native solver failed: '+str(directory))
        rows = [s.split() for s in (directory/'law.cir.prn').read_text().splitlines()
                if s.strip() and s.split()[0].isdigit()]
        if len(rows) != 1 or len(rows[0]) != len(models)+2:
            raise ValueError('unexpected DC table shape')
        records = []
        for model, token in zip(models, rows[0][2:]):
            delta = D(temperature)-D(model['tnom_c'])
            factor = 1+D(model['tc1'])*delta+D(model['tc2'])*delta*delta
            expected = -1/(1000*factor)
            observed = D(token)
            error = abs((observed-expected)/expected)
            # Printed at sixteen significant figures; allow solver roundoff.
            if factor <= 0 or error > D('1e-12'):
                raise ValueError('temperature law mismatch: '+model['name'])
            records.append(dict(model=model['name'], temperature_c=temperature,
                                factor=str(factor), expected_current_a=str(expected),
                                observed_current_a=token, relative_error=str(error)))
        return records

    with ThreadPoolExecutor(max_workers=3) as pool:
        records = sum(pool.map(probe, (-40, 27, 125)), [])
    receipt = dict(status='pass', isolated_model_checks=len(records), workers=3,
                   records=records, sources=pins, magic_mapping_qualified=False,
                   full_extracted_resistance_pvt_qualified=False, release_qualified=False)
    (out/'assessment.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('records','sources')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdk', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--xyce', default='/opt/xyce/bin/Xyce')
    run(parser.parse_args())
