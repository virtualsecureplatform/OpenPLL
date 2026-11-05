"""Necessary seven-material passivity screen; never a full PSD certificate."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction as F
import json
import os
from pathlib import Path
import shutil
import struct
import time
from common import ROOT, save, sha
from audit_substrate_reference_binding import x87
from compiled_charge import execute
from resources import lease


def run(reference, mapping, floating_index, controls, merger_upgrade, output):
    reference, mapping, floating_index, controls, merger_upgrade, out = (p.resolve() for p in
        (reference, mapping, floating_index, controls, merger_upgrade, output))
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    receipts = [p/'assessment.json' for p in (reference, mapping, floating_index, controls, merger_upgrade)]
    r, m, f, c, upgrade = [json.loads(p.read_text()) for p in receipts]
    if r['input_sha256'].get(str(receipts[1])) != sha(receipts[1]) or not r['native_capacitor_scalar_matrix_references_prepared']:
        raise ValueError('matching completed native references and conductor maps required')
    if not c['spatial_conductor_collapse_controls_pass'] or not upgrade['actual_operator_merge_bytes_identical']:
        raise ValueError('controlled collapse and sparse merger required')
    producer = Path(f['source_instances'])/'assessment.json'
    instances = json.loads(producer.read_text())
    roles = Path(instances['source_roles'])/'assessment.json'
    role = json.loads(roles.read_text())
    field_sources = [p for p in role['input_sha256'] if p.endswith('/compiled_charge/fields.json')]
    if len(field_sources) != 1 or m['input_sha256'].get(field_sources[0]) != role['input_sha256'][field_sources[0]]:
        raise ValueError('floating material and conductor maps use different global field identities')
    if sha(producer) != f['input_sha256'][str(producer)] or instances['input_sha256'].get(str(roles)) != sha(roles):
        raise ValueError('floating material instance/role lineage changed')
    parts = f['partitions']
    field_map = mapping/'native/field_nets.bin'
    collapse, merger = controls/'collapse_spatial_matrix', Path(upgrade['merger_binary'])
    matrices = {kind: Path(r[key]) for kind, key in
                (('physical', 'physical_integral_reference_matrix'), ('native_trace', 'native_output_reference_matrix'))}
    source = ROOT/'tools/sheet_charge/floating_material_groups.cpp'
    compiler = Path(shutil.which('g++')).resolve()
    expected = {str(field_map): m['artifacts'][str(field_map)], str(collapse): c['artifacts'][str(collapse)],
                str(merger): upgrade['input_sha256'][str(merger)]}
    expected.update({str(path): r['artifacts'][str(path)] for path in matrices.values()})
    expected.update({row['path']: f['input_sha256'][row['path']] for row in parts})
    paths = list(dict.fromkeys([*receipts, producer, roles, source, source.with_name('conductor_map.hpp'),
             ROOT/'tools/charge_compiler/json.hpp', compiler, Path(__file__).resolve(), *map(Path, expected)]))
    with lease(8, 16, deadline):
        with ThreadPoolExecutor(max_workers=8) as pool:
            pins = dict(zip(map(str, paths), pool.map(sha, paths)))
        if any(pins[path] != value for path, value in expected.items()):
            raise ValueError('material passivity screen input changed')
        binary = out/'floating_material_groups'
        execute([compiler, '-std=c++20', '-O3', '-fopenmp', '-Wall', '-Wextra', '-Wpedantic', source, '-o', binary],
                out/'build.log', deadline, 8)
        group_cfg = out/'groups.json'
        save(group_cfg, dict(field_map=str(field_map), parts=parts,
             expected_floating_conductors=f['indexed_instances'], output=str(out/'groups.bin'), deadline_uptime=deadline))
        execute([binary, group_cfg], out/'groups.log', deadline, 8)
        groups = json.loads((out/'groups.log').read_text())
        results = {}
        os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
        import numpy as np
        for kind, matrix in matrices.items():
            root = out/kind
            root.mkdir()
            cfg = root/'collapse.json'
            save(cfg, dict(matrix=str(matrix), voltage_map=str(out/'groups.bin'), threads=8,
                 max_accumulator_entries=128, output=str(root/'runs'), deadline_uptime=deadline))
            save(out/'status.json', dict(state='screening_material_voltage_subspace', reference=kind, release_qualified=False))
            execute([collapse, cfg], root/'collapse.log', deadline, 8)
            merge = root/'merge.json'
            runs = sorted((root/'runs').glob('*.bin'))
            save(merge, dict(inputs=list(map(str, runs)), output=str(root/'matrix.bin'), deadline_uptime=deadline))
            execute([merger, merge], root/'merge.log', deadline, 1)
            raw = (root/'matrix.bin').read_bytes()
            count = struct.unpack_from('<Q', raw, 8)[0]
            if raw[:8] != b'SPCRUN01' or len(raw) != 16+40*count:
                raise ValueError('material matrix format')
            exact, absolute = {}, {}
            dense = np.zeros((8, 8))
            for i in range(count):
                offset = 16+40*i
                key = struct.unpack_from('<Q', raw, offset)[0]
                a, b = key >> 32, key & (2**32-1)
                if not 0 <= a <= b < 8:
                    raise ValueError('material subspace index')
                value = x87(raw[offset+8:offset+18])
                exact[a, b] = value
                absolute[a, b] = x87(raw[offset+18:offset+28])
                dense[a, b] = dense[b, a] = float(value)
            # All extracted conductors and both ground representations are fixed.
            eigenvalues, vectors = np.linalg.eigh(dense[1:, 1:])
            values = [F(0), *[F(float(v)) for v in vectors[:, 0]]]
            energy = sum(value*values[a]*values[b]*(1 if a == b else 2) for (a, b), value in exact.items())
            magnitude = sum(value*abs(values[a]*values[b])*(1 if a == b else 2)
                            for (a, b), value in absolute.items())
            bound = F(256, 2**63)*magnitude
            results[kind] = dict(eigenvalues=list(map(float, eigenvalues)),
                 witness_material_voltages=list(map(float, values)), witness_energy=float(energy),
                 accumulated_roundoff_bound=float(bound), negative_energy_witness_found=energy < -bound,
                 necessary_subspace_only=True)
        with ThreadPoolExecutor(max_workers=8) as pool:
            if list(pool.map(sha, paths)) != list(pins.values()):
                raise ValueError('material passivity screen input changed')
        save(out/'results.json', dict(groups=groups, results=results))
        products = [binary, out/'groups.bin', out/'groups.log', out/'results.json',
                    *[out/kind/'matrix.bin' for kind in matrices]]
        save(out/'assessment.json', dict(input_sha256=pins, artifacts={str(p): sha(p) for p in products},
             seven_material_voltage_subspace_screen_complete=True,
             physical_reference_negative_energy_witness=results['physical']['negative_energy_witness_found'],
             native_trace_negative_energy_witness=results['native_trace']['negative_energy_witness_found'],
             reference_and_extracted_conductors_fixed=True, all_floating_conductors_grouped_by_material=True,
             full_matrix_passivity_verified=False, global_passivity_qualified=False,
             physical_RC_qualified=False, release_qualified=False))
        save(out/'status.json', dict(state='material_passivity_screen_complete_full_PSD_check_still_required', release_qualified=False))
        print(json.dumps({kind: dict(minimum_eigenvalue=result['eigenvalues'][0],
             negative_witness=result['negative_energy_witness_found']) for kind, result in results.items()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'mapping', 'floating-index', 'controls', 'merger-upgrade', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.reference, args.mapping, args.floating_index, args.controls, args.merger_upgrade, args.output)
