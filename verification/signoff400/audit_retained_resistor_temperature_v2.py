#!/usr/bin/env python3
"""Audit retained isolated native probes without repeating native simulations."""
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import sys

source, output = map(Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=False)
registry = json.loads((source/'registry.json').read_text())
models = registry['models']
assert len(models) == 22 and len({m['name'] for m in models}) == 22
records, pins = [], {}
for p in sorted(source.rglob('*')):
    if p.is_file():
        pins[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
for temperature in (-40, 27, 125):
    directory = source/('temperature_'+str(temperature))
    deck = (directory/'law.cir').read_text()
    assert '.options device temp='+str(temperature)+'\n' in deck
    assert '***** End of Xyce(TM) Simulation' in (directory/'solver.log').read_text()
    lines = (directory/'law.cir.prn').read_text().splitlines()
    assert lines[0].split() == ['Index']+[f'I(V{i})' for i in range(22)]
    assert lines[-1] == 'End of Xyce(TM) Simulation'
    rows = [s.split() for s in lines if s.strip() and s.split()[0].isdigit()]
    assert len(rows) == 1 and len(rows[0]) == 23 and rows[0][0] == '0'
    for i, (model, token) in enumerate(zip(models, rows[0][1:])):
        declaration = f'.model law{i} R TC1={model["tc1"]} TC2={model["tc2"]} TNOM={model["tnom_c"]}'
        assert declaration+'\n' in deck
        assert f'R{i} n{i} 0 law{i} 1000\n' in deck
        delta = D(temperature)-D(model['tnom_c'])
        factor = 1+D(model['tc1'])*delta+D(model['tc2'])*delta*delta
        expected = -1/(1000*factor)
        error = abs((D(token)-expected)/expected)
        assert factor > 0 and error <= D('1e-12'), (model, error)
        records.append(dict(model=model['name'], temperature_c=temperature,
                            factor=str(factor), relative_error=str(error)))
for name, pin in registry['sources'].items():
    assert hashlib.sha256((source/'sources'/name).read_bytes()).hexdigest() == pin['sha256']
result = dict(status='pass', isolated_model_checks=len(records), records=records,
              retained_source=str(source), artifact_sha256=pins,
              magic_mapping_qualified=False, full_extracted_resistance_pvt_qualified=False,
              release_qualified=False)
(output/'assessment.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(status='pass', checks=len(records),
                     max_relative_error=str(max(D(r['relative_error']) for r in records)))))
