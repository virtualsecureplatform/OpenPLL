"""Compare every compiled R mesh to the exact reference constructors."""
import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from fractions import Fraction as F
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import resource
import time
from common import save, sha
from native_axis_basis import axis_template
from native_anchored_sheet import prepare as anchored
from native_zero_R_axis_v2 import prepare as zero_axis
from resources import lease


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))


def read_row(fd, offset):
    raw = b''
    while b'\n' not in raw:
        chunk = os.pread(fd, 8192, offset+len(raw))
        if not chunk or len(raw) > 16*1024**2:
            raise ValueError('incomplete bounded R geometry row')
        raw += chunk
    return json.loads(raw.split(b'\n', 1)[0])


def check_part(task):
    path, sources, expected_hash, deadline = task
    streams = [Path(p).open('rb') for p in sources]
    catalog, axes, chains = [s.fileno() for s in streams]
    digest = hashlib.sha256()
    offsets, points, triangles = [], 0, 0
    try:
        with Path(path).open('rb') as rows:
            for raw in rows:
                if time.monotonic() > deadline:
                    raise TimeoutError('R runtime mesh audit deadline')
                digest.update(raw)
                row = json.loads(raw)
                offset = row['source_catalog_byte_offset']
                tile = read_row(catalog, offset)
                for key in ('tile_serial', 'native_group_id', 'catalog_state', 'raw_material'):
                    if row[key] != tile[key]:
                        raise ValueError('runtime mesh/catalog identity mismatch')
                if row['box'] != tile['box_internal'] or row['physical_RC_qualified'] is not False:
                    raise ValueError('runtime mesh box/qualification mismatch')
                if tile['catalog_state'] == 'anchored_sheet_candidate':
                    template = anchored(tile['box_internal'], tile['native_anchor_points'],
                                        tile['latent_node_namespace']+':r1')['template']
                    if row['auxiliary'] != dict(kind='anchored_sheet',
                            nominal_sheet_milliohms_per_square=tile['nominal_sheet_milliohms_per_square']):
                        raise ValueError('anchored auxiliary sheet mismatch')
                else:
                    axis = read_row(axes, tile['axis_registry_byte_offset'])
                    if (axis['native_group_id'], axis['tile_box_internal']) != (tile['native_group_id'], tile['box_internal']):
                        raise ValueError('axis/catalog identity')
                    if tile['axis_preparation_state'] == 'deferred_zero_R_constraint':
                        chain = read_row(chains, axis['source_chain_byte_offset'])
                        model = zero_axis(chain, f'_zero_R_{tile["native_group_id"]}_{tile["tile_serial"]}')
                        template = model['template']
                        if row['auxiliary'] != dict(kind='zero_R_symbolic_ends', constraints=model['constraints'],
                                                    raw_material=chain['raw_material']):
                            raise ValueError('zero-R native constraint mismatch')
                    else:
                        template = axis_template(tile['box_internal'], axis['flow_axis'], axis['candidate_voltage_knots'])
                        if row['auxiliary'] != dict(kind='nominal_axis_ends', stubs=axis['end_stub_resistors']):
                            raise ValueError('axis finite-end metadata mismatch')
                if [tuple(map(F, p)) for p in row['points']] != [tuple(map(F, p)) for p in template['points']]:
                    raise ValueError('compiled R points differ from exact reference')
                if row['point_nodes'] != template['point_nodes'] or row['triangles'] != [list(t) for t in template['triangles']]:
                    raise ValueError('compiled R topology or native/latent identities differ')
                offsets.append(offset)
                points += len(row['points'])
                triangles += len(row['triangles'])
        if digest.hexdigest() != expected_hash:
            raise ValueError('runtime mesh part changed')
        return offsets, points, triangles
    finally:
        for stream in streams:
            stream.close()


def run(runtime, output):
    runtime, out = runtime.resolve(), output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.monotonic()+43200
    receipt = runtime/'assessment.json'
    report = json.loads(receipt.read_text())
    index = Path(report['source_index'])/'assessment.json'
    descriptor = json.loads(index.read_text())
    if report['input_sha256'].get(str(index)) != sha(index):
        raise ValueError('runtime R source index changed')
    sources = [Path(descriptor[k]) for k in ('catalog', 'axes', 'chains')]
    parts = sorted(runtime.glob('native/part_*.jsonl'))
    paths = [receipt, index, *sources, Path(__file__).resolve(),
             *[Path(__file__).with_name(p) for p in ('native_axis_basis.py', 'native_anchored_sheet.py',
                'native_zero_R_axis_v2.py', 'floating_sheet_basis.py')]]
    with lease(8, 16, time.clock_gettime(time.CLOCK_BOOTTIME)+43200):
        with ThreadPoolExecutor(max_workers=8) as pool:
            pins = dict(zip(map(str, paths), pool.map(sha, paths)))
        if any(pins[str(p)] != report['input_sha256'][str(p)] for p in sources):
            raise ValueError('runtime R source bytes changed')
        save(out/'status.json', dict(state='auditing_every_compiled_R_mesh', release_qualified=False))
        tasks = [(str(p), list(map(str, sources)), report['artifacts'][str(p)], deadline) for p in parts]
        with ProcessPoolExecutor(max_workers=8, initializer=limits,
                 mp_context=multiprocessing.get_context('spawn')) as pool:
            results = list(pool.map(check_part, tasks))
        seen = set()
        for offsets, _, _ in results:
            for offset in offsets:
                if offset in seen:
                    raise ValueError('duplicate compiled catalog row')
                seen.add(offset)
        digest, offset = hashlib.sha256(), 0
        with sources[0].open('rb') as stream:
            for raw in stream:
                digest.update(raw)
                if offset not in seen:
                    raise ValueError('missing compiled selected R tile')
                offset += len(raw)
        if digest.hexdigest() != pins[str(sources[0])] or len(seen) != report['tiles']:
            raise ValueError('R runtime selected-tile coverage')
        if sum(n for _, n, _ in results) != report['points'] or sum(n for _, _, n in results) != report['triangles']:
            raise ValueError('R runtime geometry aggregate mismatch')
        with ThreadPoolExecutor(max_workers=8) as pool:
            if list(pool.map(sha, paths)) != list(pins.values()):
                raise ValueError('R runtime audit input changed')
        save(out/'assessment.json', dict(input_sha256=pins,
             all_selected_R_meshes_independently_reconstructed=True, tiles=len(seen),
             points=report['points'], triangles=report['triangles'], source_parts=len(parts),
             exact_native_and_latent_voltage_names_match=True, zero_R_constraints_preserved=True,
             runtime_part_sha256={str(p): report['artifacts'][str(p)] for p in parts},
             physical_RC_qualified=False, full_C_energy_matrix_assembled=False, release_qualified=False))
        save(out/'status.json', dict(state='all_R_runtime_meshes_verified', release_qualified=False))
        print(json.dumps(dict(tiles=len(seen), points=report['points'], triangles=report['triangles'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    run(args.runtime, args.output)
