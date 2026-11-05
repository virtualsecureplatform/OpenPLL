"""Project real signed native operators using the current named floating bases."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction as F
import json
import math
import multiprocessing
from pathlib import Path
import resource
import time
from common import save, sha
from floating_basis_resolver import FloatingBasisResolver, rational
from native_axis_basis import named_sheet
from floating_sheet_charge import area, line, constant
from floating_sheet_fringe import fringe
from compiled_sheet_charge_rational import invoke, decode
from resources import lease


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))


def reference_basis(payload):
    if 'constant' in payload:
        return constant(payload['constant'])
    return named_sheet(dict(points=[tuple(rational(x) for x in p) for p in payload['points']],
                            triangles=payload['triangles'], point_nodes=payload['point_nodes']))


def oracle(case):
    op = case['operator']
    source, target = (reference_basis(case[p]) for p in ('source_basis', 'target_basis'))
    if op[0] == 'A':
        matrix = area(source, target, op[4], F(op[5]))
    elif op[0] == 'L':
        matrix = line(source, target, op[4], op[5], F(op[6]))
    else:
        matrix = fringe(source, target, *op[4:9], precision=90)
    return case['id'], matrix


def run(samples, index, binary, output):
    samples, index, binary, out = (p.resolve() for p in (samples, index, binary, output))
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    proof = samples/'assessment.json'
    report = json.loads(proof.read_text())
    source = samples/'native/cases.jsonl'
    if not report['selected_operator_file_fully_rehashed'] or sha(source) != report['artifacts'][str(source)]:
        raise ValueError('fully pinned actual operator sample required')
    build = binary.parent/'build.json'
    if json.loads(build.read_text())['artifacts'][str(binary)] != sha(binary):
        raise ValueError('compiled projector build changed')
    paths = [proof, source, index/'assessment.json', binary, build, Path(__file__).resolve(),
             *[Path(__file__).with_name(p) for p in ('floating_basis_resolver.py', 'native_axis_basis.py',
                'floating_sheet_charge.py', 'floating_sheet_fringe.py', 'compiled_sheet_charge_rational.py')]]
    pins = {str(p): sha(p) for p in paths}
    observed = [json.loads(raw) for raw in source.read_text().splitlines()]
    if len(observed) != report['selected_cases'] or not observed:
        raise ValueError('complete nonempty actual operator samples required')
    with lease(8, 12, deadline), FloatingBasisResolver(index) as resolver:
        cases = []
        for sample in observed:
            for ref in (1, 2, 4):
                bases = []
                for context in (sample['source'], sample['target']):
                    field = context['global_field_id']
                    if field == 0:
                        if not context.get('explicit_reference'):
                            raise ValueError('explicit substrate reference required')
                        bases.append(dict(constant='@SUBSTRATE_REFERENCE'))
                    else:
                        instance = resolver.instance(field)
                        if (instance['original_conductor'], instance['native_type']) != (
                                context['original_conductor'], context['native_type']):
                            raise ValueError('actual operator/resolved conductor identity mismatch')
                        bases.append(resolver.resolve(field, ref))
                op = sample['operator'][:]
                op[1:3] = [sample['source']['global_field_id'], sample['target']['global_field_id']]
                cases.append(dict(id=f'{sample["operator_byte_offset"]}/r{ref}', operator=op,
                                  source_basis=bases[0], target_basis=bases[1]))
        save(out/'status.json', dict(state='compiled_actual_operator_projection', cases=len(cases), release_qualified=False))
        rows, summary = invoke(binary, cases, out/'projection', threads=8, deadline=deadline)
        if len(rows) != len(cases) or len({r['id'] for r in rows}) != len(cases):
            raise ValueError('projected actual operator count/identity')
        save(out/'status.json', dict(state='independent_exact_and_decimal_oracles', cases=len(cases), release_qualified=False))
        with ProcessPoolExecutor(max_workers=8, initializer=limits,
                 mp_context=multiprocessing.get_context('spawn')) as pool:
            references = dict(pool.map(oracle, cases))
        results, maximum = [], 0.0
        for case, row in zip(cases, rows):
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('actual operator projection deadline')
            if row['id'] != case['id']:
                raise ValueError('projection order/identity')
            kind = case['operator'][0]
            wanted = references[row['id']]
            actual = decode(row, exact=kind != 'F')
            if kind != 'F':
                if actual != wanted:
                    raise ValueError('actual A/L projection differs from exact rational oracle')
                error = 0.0
            else:
                norm = max([abs(v) for v in wanted.values()]+[0.0])
                delta = max([abs(actual.get(k, 0)-wanted.get(k, 0)) for k in set(actual)|set(wanted)]+[0.0])
                error = delta/norm if norm else delta
                if error > 1e-14:
                    raise ValueError(f'actual fringe projection error {error}')
            maximum = max(maximum, error)
            nodes = set(n for pair in actual for n in pair)
            values = {name: F(i % 7-3, 3) for i, name in enumerate(sorted(nodes))}
            energy = sum(v*values[a]*values[b] for (a, b), v in actual.items())
            magnitude = sum(abs(v*values[a]*values[b]) for (a, b), v in actual.items())
            density = case['operator'][5 if kind == 'A' else 6 if kind == 'L' else 7]
            if float(energy)*density < -1e-13*abs(density)*float(magnitude):
                raise ValueError('signed local operator energy changes sign')
            results.append(dict(id=row['id'], kind=kind, matrix_entries=len(actual), normalized_error=error,
                                test_energy=float(energy), native_signed_density=density))
        for p, h in pins.items():
            if sha(p) != h:
                raise ValueError('actual projection input changed')
        save(out/'results.json', results)
        artifacts = [out/'results.json', out/'projection/cases.json', out/'projection/matrices.jsonl',
                     out/'projection/native.log']
        save(out/'assessment.json', dict(input_sha256=pins, artifacts={str(p): sha(p) for p in artifacts},
             native_operator_samples=len(observed), resolved_projections=len(cases),
             kinds=sorted({c['operator'][0] for c in cases}), maximum_normalized_fringe_error=maximum,
             compiled_summary=summary, real_native_signed_operator_controls_passed=True,
             full_operator_coverage=False, full_C_energy_matrix_assembled=False,
             global_passivity_qualified=False, physical_RC_qualified=False,
             resistance_PVT_qualified=False, release_qualified=False))
        save(out/'status.json', dict(state='actual_floating_operator_projection_controls_pass', release_qualified=False))
        print(json.dumps(dict(native_samples=len(observed), projected=len(cases), maximum_error=maximum)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('samples', 'index', 'binary', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.samples, args.index, args.binary, args.output)
