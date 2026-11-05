"""Resolve corrected native R tile bases locally; reject unsupported geometry."""
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import json
import mmap
import os
from pathlib import Path
import struct
from common import sha
from floating_basis_resolver import encoded
from native_axis_basis import axis_template
from native_anchored_sheet import prepare as anchored
from native_zero_R_axis_v2 import prepare as zero_axis


def intersects(tile, support):
    x0, y0, x1, y1 = support
    a, b, c, d = tile
    if x0 > x1 or y0 > y1:
        raise ValueError('ordered operator support required')
    if x0 == x1:
        return a <= x0 <= c and max(b, y0) < min(d, y1)
    if y0 == y1:
        return b <= y0 <= d and max(a, x0) < min(c, x1)
    return max(a, x0) < min(c, x1) and max(b, y0) < min(d, y1)


class RBasisResolver:
    def __init__(self, index):
        self.root = Path(index).resolve()
        self.report = json.loads((self.root/'assessment.json').read_text())
        self.files, self.mapping = {}, None
        try:
            proof = Path(self.report['source_audit'])/'assessment.json'
            if sha(proof) != self.report['input_sha256'][str(proof)]:
                raise ValueError('R map independent audit changed')
            if not json.loads(proof.read_text())['all_field_associations_independently_checked']:
                raise ValueError('complete independent R map audit required')
            paths = [Path(self.report[k]) for k in ('catalog', 'axes', 'chains', 'bundles')]
            initial = [p.stat() for p in paths]
            with ThreadPoolExecutor(max_workers=4) as pool:
                hashes = list(pool.map(sha, paths))
            if any(h != self.report['input_sha256'][str(p)] for p, h in zip(paths, hashes)):
                raise ValueError('corrected R geometry source changed')
            for key, path, before in zip(('catalog', 'axes', 'chains', 'bundles'), paths, initial):
                stream = path.open('rb')
                self.files[key] = stream
                after = os.fstat(stream.fileno())
                if (before.st_ino, before.st_dev, before.st_size, before.st_mtime_ns) != (
                        after.st_ino, after.st_dev, after.st_size, after.st_mtime_ns):
                    raise ValueError('R source changed while opening')
            self.stats = {k: os.fstat(f.fileno()) for k, f in self.files.items()}
            path = self.root/'fields.idx'
            if sha(path) != self.report['artifacts'][str(path)]:
                raise ValueError('R field index changed')
            self.index = path.open('rb')
            self.mapping = mmap.mmap(self.index.fileno(), 0, access=mmap.ACCESS_READ)
            self.count = struct.unpack_from('<Q', self.mapping, 8)[0]
            if self.mapping[:8] != b'RBSIDX01' or len(self.mapping) != 16+16*self.count:
                raise ValueError('R field index format/size')
        except BaseException:
            self.close()
            raise

    def close(self):
        self.bundle.cache_clear()
        for stream in self.files.values():
            stream.close()
        self.files = {}
        if self.mapping is not None:
            self.mapping.close()
            self.mapping = None
        if hasattr(self, 'index'):
            self.index.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def read(self, key, offset, length=None):
        stream = self.files[key]
        stat, before = os.fstat(stream.fileno()), self.stats[key]
        if (stat.st_size, stat.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
            raise ValueError('R geometry source changed during resolution')
        if length is not None:
            raw = os.pread(stream.fileno(), length, offset)
            if len(raw) != length:
                raise ValueError('truncated R bundle')
        else:
            raw = b''
            while b'\n' not in raw:
                chunk = os.pread(stream.fileno(), 65536, offset+len(raw))
                if not chunk or len(raw) > 16*1024**2:
                    raise ValueError('truncated or excessive R geometry row')
                raw += chunk
            raw = raw.split(b'\n', 1)[0]
        return json.loads(raw)

    @lru_cache(maxsize=8)
    def bundle(self, field):
        if isinstance(field, bool) or not isinstance(field, int) or not 0 < field < self.count:
            raise ValueError('physical R field ID required')
        offset, length, number = struct.unpack_from('<QII', self.mapping, 16+16*field)
        if offset == 2**64-1 or not length:
            raise ValueError('field has no corrected R tile bundle')
        bundle = self.read('bundles', offset, length)
        if bundle['bundle_id'] != number:
            raise ValueError('R field/index bundle mismatch')
        tiles = []
        for reference in bundle['tile_references']:
            tile = self.read('catalog', reference[0])
            if (tile['native_group_id'], tile['tile_serial'], int(tile['raw_type_id'])) != tuple(reference[2:5]):
                raise ValueError('R bundle/catalog reference identity mismatch')
            if tile['original_conductor'] != bundle['field_key'][0]:
                raise ValueError('R conductor identity mismatch')
            tiles.append(tile)
        return bundle['field_key'], tiles

    def resolve(self, field, support, refinement=1):
        if refinement != 1:
            raise ValueError('R resolver currently requires native refinement one')
        key, candidates = self.bundle(field)
        points, triangles, names, selected, constraints, auxiliary = [], [], [], [], [], []
        for tile in candidates:
            if not intersects(tile['box_internal'], support):
                continue
            if tile['split'] != 0:
                raise ValueError('split native R tile needs explicit basis')
            state = tile['catalog_state']
            if state == 'anchored_sheet_candidate':
                model = anchored(tile['box_internal'], tile['native_anchor_points'],
                                 tile['latent_node_namespace']+':r1', refinement=1)
                template = model['template']
                auxiliary.append(dict(tile_serial=tile['tile_serial'], kind='anchored_unit_sheet',
                     nominal_sheet_milliohms_per_square=tile['nominal_sheet_milliohms_per_square'],
                     unit_sheet_conductance=[[a, b, *encoded(v)] for (a, b), v in model['conductance'].items()]))
            else:
                axis = self.read('axes', tile['axis_registry_byte_offset'])
                if (axis['native_group_id'], axis['tile_box_internal']) != (tile['native_group_id'], tile['box_internal']):
                    raise ValueError('R tile/axis identity mismatch')
                if tile['axis_preparation_state'] == 'deferred_zero_R_constraint':
                    chain = self.read('chains', axis['source_chain_byte_offset'])
                    if (chain['native_group_id'], chain['tile_box_internal']) != (tile['native_group_id'], tile['box_internal']):
                        raise ValueError('zero-R chain identity mismatch')
                    model = zero_axis(chain, f'_zero_R_{tile["native_group_id"]}_{tile["tile_serial"]}')
                    template = model['template']
                    constraints.extend({k: encoded(v) if k == 'voltage_rhs' else v for k, v in c.items()}
                                       for c in model['constraints'])
                    auxiliary.append(dict(tile_serial=tile['tile_serial'], kind='zero_R_symbolic_ends',
                         stubs=[dict(endpoint_nodes=[e['new_latent_node'], e['anchor']],
                                     resistance_squares_exact=encoded(e['resistance_squares_exact']),
                                     requires_sheet_model_for_material=e['requires_sheet_model_for_material'])
                                for e in model['symbolic_end_stub_resistors']]))
                elif axis['geometric_axis_prepared']:
                    template = axis_template(tile['box_internal'], axis['flow_axis'], axis['candidate_voltage_knots'])
                    auxiliary.append(dict(tile_serial=tile['tile_serial'], kind='nominal_axis_ends',
                                          stubs=axis['end_stub_resistors']))
                else:
                    raise ValueError('unresolved native R axis')
            base = len(points)
            points.extend([[encoded(v) for v in p] for p in template['points']])
            triangles.extend([[base+i for i in t] for t in template['triangles']])
            names.extend(template['point_nodes'])
            selected.append(tile['tile_serial'])
        if not selected:
            raise ValueError('operator support misses corrected native R geometry')
        return dict(points=points, triangles=triangles, point_nodes=names,
                    physical_field_id=field, field_key=key, refinement=1,
                    selected_tile_serials=selected, exact_zero_voltage_constraints=constraints,
                    auxiliary_R_models=auxiliary,
                    physical_RC_qualified=False, resistance_PVT_qualified=False,
                    native_core_resistors_rewritten=False)
