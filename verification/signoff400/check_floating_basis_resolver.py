"""Audit all lookup offsets and project resolved meshes with the compiled engine."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import struct
import time
from common import save, sha
from floating_basis_resolver import FloatingBasisResolver, rational, encoded
from native_axis_basis import named_sheet
from floating_sheet_charge import area, constant, cross
from compiled_sheet_charge_rational import build, invoke, decode
from resources import lease


def inscribed_box(points):
    center = tuple(sum(p[d] for p in points)/3 for d in (0, 1))
    margins = [cross(a, b, center)/(abs(b[0]-a[0])+abs(b[1]-a[1]))
               for a, b in zip(points, points[1:]+points[:1])]
    epsilon = min(margins)/2
    if epsilon <= 0:
        raise ValueError('positive oriented triangle required')
    return [center[0]-epsilon, center[1]-epsilon, center[0]+epsilon, center[1]+epsilon]


def run(index, output):
    index, out = index.resolve(), output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    with lease(8, 12, deadline), FloatingBasisResolver(index) as resolver:
        def check_partition(part):
            count, offset, samples = 0, 0, {}
            digest = hashlib.sha256()
            with resolver.parts[part].open('rb') as stream:
                for raw in stream:
                    if count % 1000 == 0 and time.clock_gettime(time.CLOCK_BOOTTIME) > deadline:
                        raise TimeoutError('resolver audit deadline')
                    digest.update(raw)
                    row = json.loads(raw)
                    field = row['physical_field_id']
                    entry = struct.unpack_from('<QII', resolver.mapping, 16+16*field)
                    if entry != (offset, len(raw)-1, part):
                        raise ValueError('independent instance/index offset mismatch')
                    samples.setdefault(row['local_template_id'], field)
                    offset += len(raw)
                    count += 1
            if digest.hexdigest() != resolver.report['input_sha256'][str(resolver.parts[part])]:
                raise ValueError('instance stream changed')
            return count, samples

        save(out/'status.json', dict(state='auditing_all_field_offsets', release_qualified=False))
        with ThreadPoolExecutor(max_workers=7) as pool:
            checked = list(pool.map(check_partition, range(7)))
        count = sum(n for n, _ in checked)
        samples = {key: field for _, rows in checked for key, field in rows.items()}
        if count != resolver.report['indexed_instances']:
            raise ValueError('index audit count')
        cases, expected = [], {}
        for local, field in sorted(samples.items()):
            for ref in (1, 2, 4):
                payload = resolver.resolve(field, ref)
                template = dict(points=[tuple(rational(x) for x in p) for p in payload['points']],
                                triangles=payload['triangles'], point_nodes=payload['point_nodes'])
                triangle = [template['points'][i] for i in template['triangles'][0]]
                box = inscribed_box(triangle)
                name = f'{local}/r{ref}'
                operator = ['A', field, 0, 1, list(map(encoded, box)), 1.0]
                cases.append(dict(id=name, operator=operator, source_basis=payload,
                                  target_basis=dict(constant='@SUBSTRATE_REFERENCE')))
                expected[name] = area(named_sheet(template), constant('@SUBSTRATE_REFERENCE'), box)
                stiffness = resolver.nominal_stiffness(field, ref)
                names = set(payload['point_nodes'])
                for node in names:
                    if sum(value for (a, b), value in stiffness.items() if a == node) != 0:
                        raise ValueError('nominal stiffness loses floating constant nullspace')
                if any(a not in names or b not in names for a, b in stiffness):
                    raise ValueError('stiffness/payload identity mismatch')
        binary = build(out/'build', deadline)
        save(out/'status.json', dict(state='projecting_resolved_exact_coordinate_controls', release_qualified=False))
        rows, summary = invoke(binary, cases, out/'projection', threads=8, deadline=deadline)
        if len(rows) != len(cases):
            raise ValueError('projection row count')
        for row in rows:
            if decode(row, exact=True) != expected[row['id']]:
                raise ValueError('resolved compiled projection differs from rational oracle')
        rejected = 0
        for field, ref in ((0, 1), (1, 1), (2394895, 1), (-1, 1), (True, 1), (next(iter(samples.values())), 3)):
            try:
                resolver.resolve(field, ref)
            except ValueError:
                rejected += 1
            else:
                raise ValueError('unsupported field/refinement accepted')
        receipt = index/'assessment.json'
        paths = [receipt, Path(__file__).resolve(),
                 *[Path(__file__).with_name(p) for p in ('floating_basis_resolver.py', 'compiled_sheet_charge_rational.py',
                    'native_axis_basis.py', 'floating_sheet_charge.py')]]
        pins = {str(p): sha(p) for p in paths}
        save(out/'assessment.json', dict(input_sha256=pins,
             artifacts={str(p): sha(p) for p in (out/'build/build.json', out/'projection/matrices.jsonl',
                 out/'projection/cases.json', out/'projection/native.log')},
             all_indexed_offsets_independently_checked=True, indexed_instances=count,
             material_local_shapes=len(samples), exact_resolved_projection_controls=len(cases),
             rejected_unsupported_requests=rejected, compiled_summary=summary,
             named_payloads_and_nominal_stiffness_resolved=True,
             actual_native_C_operators_projected=False, full_C_energy_matrix_assembled=False,
             physical_RC_qualified=False, release_qualified=False))
        save(out/'status.json', dict(state='floating_basis_resolver_controls_pass', release_qualified=False))
        print(json.dumps(dict(instances=count, shapes=len(samples), projections=len(cases))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('index', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    run(args.index, args.output)
