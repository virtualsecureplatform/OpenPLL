#!/usr/bin/env python3
"""Current single-native-voltage tile inventory and bounded parallel controls.

Synthetic unit-density local controls only; actual signed C and physical RC
assembly, interfaces, native snapshot selection and PVT remain unqualified.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import time
from common import ROOT, save, sha
from resources import lease
from native_anchored_sheet import prepare, reference_mass
from native_axis_stubs import schur_eliminate
from nominal_sheet_resistance_v3 import parse
from compiled_sheet_charge_registered import build, invoke, payload, decode


def control(task):
    number, row, deadline = task
    anchors = [(p['point_internal'], p['private_id']) for p in row['breakpoints']]
    cases, expected = [], {}
    details = []
    for refinement in (1, 2, 4):
        if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
            raise TimeoutError('anchored sheet preparation deadline')
        model = prepare(row['box_internal'], anchors,
                        f"_rmesh_sheet_{row['native_group_id']}_{row['tile_serial']}", refinement, row['split'])
        if schur_eliminate(model['conductance'], model['latent_nodes']) != {}:
            raise ValueError('latent sheet changes sole native DC voltage equation')
        name = f'{number}:{refinement}'
        cases.append(dict(id=name, operator=['A', 1, 0, 1, row['box_internal'], 1.],
                          source_basis=payload(model['template'], '', model['template']['point_nodes']),
                          target_basis=dict(constant='REF')))
        expected[name] = reference_mass(model)
        details.append(dict(refinement=refinement, latent_nodes=len(model['latent_nodes']),
                            triangles=len(model['template']['triangles']),
                            exact_native_DC_unchanged=True,
                            geometric_certificate=model['geometric_certificate']))
    return cases, expected, dict(source_tile=row, refinements=details)


def run(index, domain, output):
    index, domain, out = (Path(p).resolve() for p in (index, domain, output))
    out.mkdir(parents=True, exist_ok=False)
    start = time.clock_gettime(time.CLOCK_BOOTTIME)
    deadline = start+43200
    def status(state, **extra):
        save(out/'status.json', dict(state=state, release_qualified=False,
                                    elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start, **extra))
    save(out/'owner.json', dict(wall_limit_s=43200, cpu_slots=8, memory_limit_GiB=8,
                               automatic_identical_retry=False))
    pool = None
    try:
        with lease(8, 8, deadline):
            status('inventorying_all_current_single_voltage_tiles')
            ir, dr = index/'assessment.json', domain/'assessment.json'
            i, d = json.loads(ir.read_text()), json.loads(dr.read_text())
            tech = ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech'
            if i['input_sha256'].get(str(dr)) != sha(dr) or d['input_sha256'].get(str(tech)) != sha(tech):
                raise ValueError('current tile/domain/technology lineage mismatch')
            source = index/'tile_domains.jsonl'
            pins = {str(p): sha(p) for p in (ir, dr, tech, Path(__file__).resolve(),
                *[Path(__file__).with_name(n) for n in ('native_anchored_sheet.py', 'native_axis_stubs.py',
                'native_axis_basis.py', 'floating_sheet_basis.py', 'compiled_sheet_charge_registered.py',
                'nominal_sheet_resistance.py', 'nominal_sheet_resistance_v2.py', 'nominal_sheet_resistance_v3.py',
                'common.py', 'resources.py')])}
            sheets = parse(tech.read_text())
            counts, materials, selected_materials = Counter(), Counter(), Counter()
            selected, fingerprints = [], set()
            digest = hashlib.sha256()
            with source.open('rb') as stream:
                for number, raw in enumerate(stream, 1):
                    if number % 1000 == 0 and time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                        raise TimeoutError('tile inventory deadline')
                    digest.update(raw)
                    row = json.loads(raw)
                    counts['all_tile_records'] += 1
                    if len(row['private_voltage_nodes']) != 1:
                        counts['other_native_voltage_domains'] += 1
                        continue
                    counts['single_native_voltage_tiles'] += 1
                    materials[row['raw_material']] += 1
                    box = row['box_internal']
                    points = {tuple(p['point_internal']) for p in row['breakpoints']}
                    if not points or any(p['private_id'] != row['private_voltage_nodes'][0] for p in row['breakpoints']):
                        raise ValueError('single-voltage tile identity inconsistency')
                    if row['split'] != 0 or box[0] >= box[2] or box[1] >= box[3]:
                        counts['deferred_shape'] += 1
                        continue
                    if any(not (box[0] <= x <= box[2] and box[1] <= y <= box[3]) for x, y in points):
                        counts['deferred_outside_anchor'] += 1
                        continue
                    if row['raw_material'] not in sheets:
                        counts['deferred_nominal_material'] += 1
                        continue
                    counts['geometrically_supported_nominal_single_voltage_tiles'] += 1
                    if any(not p['private_id'].startswith('_rmesh_'+row['native_group_id']+'_') for p in row['breakpoints']):
                        raise ValueError('native anchor crosses snapshot namespace')
                    fingerprint = (row['raw_material'], box[2]-box[0], box[3]-box[1],
                                   tuple(sorted((x-box[0], y-box[1]) for x, y in points)))
                    if (len(selected) < 24 and len(points) <= 2 and
                            selected_materials[row['raw_material']] < 2 and fingerprint not in fingerprints):
                        selected.append(row)
                        fingerprints.add(fingerprint)
                        selected_materials[row['raw_material']] += 1
            if digest.hexdigest() != i['artifacts'][str(source)] or counts['all_tile_records'] != i['domain_counts']['domains']:
                raise ValueError('complete tile stream hash/count mismatch')
            if counts['single_native_voltage_tiles'] != i['domain_counts']['constant_voltage_domain'] or not selected:
                raise ValueError('single-voltage coverage mismatch or empty controls')
            pins[str(source)] = digest.hexdigest()
            save(out/'inventory.json', dict(counts=counts, material_counts=materials,
                                           selected_material_counts=selected_materials))
            status('parallel_exact_anchor_mesh_and_native_DC_controls', selected_tiles=len(selected))
            pool = ProcessPoolExecutor(max_workers=8)
            futures = [pool.submit(control, (n, row, deadline)) for n, row in enumerate(selected)]
            results = {}
            for future in as_completed(futures, timeout=max(0, deadline-time.clock_gettime(time.CLOCK_BOOTTIME))):
                result = future.result()
                results[int(result[0][0]['id'].split(':')[0])] = result
            pool.shutdown()
            pool = None
            cases, expected, details = [], {}, []
            for number in range(len(selected)):
                c, e, info = results[number]
                cases.extend(c)
                expected.update(e)
                details.append(info)
            save(out/'selected_tiles.json', details)
            status('building_and_checking_compiled_exact_unit_mass', cases=len(cases))
            binary = build(out/'build', deadline)
            b = json.loads((out/'build/build.json').read_text())
            pins.update(b['input_sha256'])
            pins.update(b['artifacts'])
            matrices, _ = invoke(binary, cases, out/'matrices', threads=8, deadline=deadline)
            if len(matrices) != len(expected) or {m['id'] for m in matrices} != set(expected):
                raise ValueError('compiled matrix case coverage mismatch')
            for matrix in matrices:
                if decode(matrix, exact=True) != expected[matrix['id']]:
                    raise ValueError('compiled anchored sheet mass differs from exact P1 integral')
            for p, h in pins.items():
                if sha(p) != h:
                    raise ValueError('anchored sheet input changed: '+p)
            result = dict(input_sha256=pins, inventory=dict(counts),
                          artifacts={str(p): sha(p) for p in (out/'inventory.json', out/'selected_tiles.json',
                          out/'build/build.json', out/'matrices/matrices.jsonl')},
                          observed_single_voltage_tiles_checked=len(selected),
                          exact_native_DC_checks=len(cases), exact_compiled_unit_mass_checks=len(matrices),
                          workers=8, synthetic_unit_density_only=True,
                          full_layout_basis_constructed=False, snapshot_selection_qualified=False,
                          actual_signed_C_attachment_qualified=False, resistance_PVT_qualified=False,
                          material_device_interface_qualified=False, physical_RC_qualified=False,
                          runtime_model_eligible=False, release_qualified=False,
                          elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
            save(out/'assessment.json', result)
            status('anchored_sheet_controls_complete_physical_qualification_pending')
            return result
    except BaseException as exc:
        if pool is not None:
            for process in pool._processes.values():
                process.terminate()
            pool.shutdown(wait=True, cancel_futures=True)
        status('failed', reason=repr(exc))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('index', 'domain', 'output'):
        p.add_argument('--'+name, required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(run(a.index, a.domain, a.output)))
