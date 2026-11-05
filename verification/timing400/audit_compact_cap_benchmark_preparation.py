#!/usr/bin/env python3
"""Independent signed-operator and protocol audit of the benchmark deck."""
import json
from pathlib import Path
import re
import numpy as np
from compile_local_C_operators_v2 import digest, save

root = Path(__file__).resolve().parents[2]
base = root/'build/timing400/release_001'
campaign = base/'compact_constant_cap_benchmark_001'
deck = campaign/'benchmark.cir'
owner_path = campaign/'owner.json'
owner = json.loads(owner_path.read_text())
out = base/'compact_cap_benchmark_preparation_audit_001'; out.mkdir(exist_ok=False)
pins = {str(p): digest(p) for p in (Path(__file__).resolve(), deck, owner_path)}
for p, sha in owner['input_sha256'].items(): assert digest(Path(p)) == sha, p
operator = np.zeros((64, 64))
counts = dict(capacitors=0, negative=0, multiplied=0, grounded=0)
names = set(); resistors = set()
lines = deck.read_text().splitlines()
for line in lines[1:]:
    fields = line.split()
    if not fields: continue
    if fields[0].startswith('R'):
        assert fields[1] == 'input' and 1000 <= float(fields[3]) <= 1630
        resistors.add(fields[2]); continue
    if not fields[0].startswith('C'): continue
    assert fields[0] not in names; names.add(fields[0])
    assert len(fields) in (4, 5)
    first = int(re.fullmatch(r'n(\d+)', fields[1]).group(1))
    second = -1 if fields[2] == '0' else int(re.fullmatch(r'n(\d+)', fields[2]).group(1))
    assert 0 <= first < 64 and -1 <= second < 64 and first != second
    coefficient = float(fields[3]); assert np.isfinite(coefficient) and coefficient != 0
    multiple = 1 if len(fields) == 4 else float(fields[4].split('M=')[1])
    assert multiple in (1, 2)
    counts['capacitors'] += 1
    counts['negative'] += coefficient < 0
    counts['multiplied'] += multiple == 2
    counts['grounded'] += second == -1
    effective = coefficient*multiple
    operator[first, first] += effective
    if second >= 0:
        operator[second, second] += effective
        operator[first, second] -= effective
        operator[second, first] -= effective
assert counts['capacitors'] == 150000 and counts['negative'] > 0 and counts['multiplied'] > 0
assert resistors == {f'n{i}' for i in range(64)}
assert np.array_equal(operator, operator.T)
eigenvalues = np.linalg.eigvalsh(operator)
roundoff_bound = 1000*np.finfo(float).eps*np.linalg.norm(operator, ord=np.inf)
assert eigenvalues[0] > roundoff_bound
assert lines.count('.tran 1p 500p 0 1p') == 1
assert lines.count('.options TIMEINT METHOD=GEAR RELTOL=1e-7 ABSTOL=1e-12') == 1
assert owner['declared_variants'] == ['reference', 'packed', 'disabled']
assert owner['budget_restarted'] is False and owner['per_case_wall_limit_s'] == 120
for path, sha in pins.items(): assert digest(Path(path)) == sha
save(out/'assessment.json', dict(input_sha256=pins, counts=counts,
     signed_capacitance_operator_symmetric=True, minimum_eigenvalue_F=float(eigenvalues[0]),
     maximum_eigenvalue_F=float(eigenvalues[-1]), numerical_roundoff_allowance_F=float(roundoff_bound),
     benchmark_operator_positive_definite=True, deck_and_protocol_preparation_passed=True,
     native_execution_proven=False, DCO_equivalence_inferred=False, release_qualified=False))
print(json.dumps(dict(counts=counts, minimum_eigenvalue_F=float(eigenvalues[0]), preparation_passed=True)))
