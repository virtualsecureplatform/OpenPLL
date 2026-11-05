"""Lazy, identity-preserving payloads from a byte-verified floating basis index."""
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction as F
import json
import mmap
import os
from pathlib import Path
import struct
from common import sha


def rational(pair):
    return F(int(pair[0]), int(pair[1]))


def encoded(value):
    value = F(value)
    return [str(value.numerator), str(value.denominator)]


class FloatingBasisResolver:
    def __init__(self, index):
        self.root = Path(index).resolve()
        self.report = json.loads((self.root/'assessment.json').read_text())
        self.files = []
        self.mapping = None
        try:
            proof = Path(self.report['source_audit'])/'assessment.json'
            if sha(proof) != self.report['input_sha256'][str(proof)]:
                raise ValueError('independent instance audit changed')
            checked = json.loads(proof.read_text())
            if not all(checked[k] for k in ('all_instances_independently_checked',
                   'exact_saved_element_matrices_reconstructed', 'physical_field_namespaces_unique')):
                raise ValueError('complete independent instance audit required')
            self.parts = [Path(p['path']) for p in self.report['partitions']]
            source = Path(self.report['source_instances'])
            paths = [*self.parts, source/'atlas/template_aliases.json', source/'atlas/templates.jsonl']
            initial_stats = [p.stat() for p in self.parts]
            with ThreadPoolExecutor(max_workers=8) as pool:
                hashes = list(pool.map(sha, paths))
            if any(h != self.report['input_sha256'][str(p)] for p, h in zip(paths, hashes)):
                raise ValueError('basis source changed after indexing')
            self.aliases = {r['local_template_id']: r['global_template_id']
                            for r in json.loads(paths[-2].read_text())}
            self.templates = {}
            for raw in paths[-1].read_text().splitlines():
                row = json.loads(raw)
                key = row['global_template_id'], row['refinement']
                if key in self.templates:
                    raise ValueError('duplicate atlas variant')
                self.templates[key] = row
            path = self.root/'fields.idx'
            if sha(path) != self.report['artifacts'][str(path)]:
                raise ValueError('field index changed')
            self.index = path.open('rb')
            self.mapping = mmap.mmap(self.index.fileno(), 0, access=mmap.ACCESS_READ)
            if self.mapping[:8] != b'FBSIDX01':
                raise ValueError('field index version')
            self.count = struct.unpack_from('<Q', self.mapping, 8)[0]
            if len(self.mapping) != 16+16*self.count or self.count != self.report['global_fields']:
                raise ValueError('field index size/count')
            self.files = [p.open('rb') for p in self.parts]
            self.stats = [os.fstat(f.fileno()) for f in self.files]
            for before, after in zip(initial_stats, self.stats):
                if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                    raise ValueError('instance source changed while opening verified files')
        except BaseException:
            self.close()
            raise

    def close(self):
        for stream in self.files:
            stream.close()
        self.files = []
        if self.mapping is not None:
            self.mapping.close()
            self.mapping = None
        if hasattr(self, 'index'):
            self.index.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def instance(self, field):
        if isinstance(field, bool) or not isinstance(field, int) or not 0 < field < self.count:
            raise ValueError('physical floating field ID required')
        offset, length, part = struct.unpack_from('<QII', self.mapping, 16+16*field)
        if offset == 2**64-1 or part >= len(self.files) or not length:
            raise ValueError('field has no floating sheet instance')
        stream = self.files[part]
        stat = os.fstat(stream.fileno())
        original = self.stats[part]
        if (stat.st_size, stat.st_mtime_ns) != (original.st_size, original.st_mtime_ns):
            raise ValueError('instance source changed during resolution')
        raw = os.pread(stream.fileno(), length, offset)
        if len(raw) != length:
            raise ValueError('truncated instance payload')
        row = json.loads(raw)
        if row['physical_field_id'] != field or row['voltage_namespace'] != f'_fmesh_{field}':
            raise ValueError('index/field identity mismatch')
        if row['native_type'] != self.report['partitions'][part]['native_type']:
            raise ValueError('index/material mismatch')
        return row

    def resolve(self, field, refinement=1):
        row = self.instance(field)
        if refinement not in row['supported_refinements']:
            raise ValueError('unsupported sheet refinement')
        template = self.templates[self.aliases[row['local_template_id']], refinement]
        scale = row['coordinate_scale']
        if scale <= 0 or row['nominal_sheet_milliohm'] <= 0:
            raise ValueError('positive coordinate scale and nominal sheet required')
        origin = [F(p, scale) for p in row['origin_gds_dbu']]
        points = [[encoded(rational(p[d])+origin[d]) for d in (0, 1)]
                  for p in template['points_native_internal']]
        names = [f'{row["voltage_namespace"]}:r{refinement}:n{i}' for i in range(len(points))]
        return dict(points=points, triangles=template['triangles'], point_nodes=names,
                    physical_field_id=field, refinement=refinement,
                    global_template_id=template['global_template_id'],
                    original_conductor=row['original_conductor'],
                    nominal_sheet_milliohm=row['nominal_sheet_milliohm'],
                    physical_RC_qualified=False, resistance_PVT_qualified=False)

    def nominal_stiffness(self, field, refinement=1):
        row = self.instance(field)
        if refinement not in row['supported_refinements']:
            raise ValueError('unsupported sheet refinement')
        template = self.templates[self.aliases[row['local_template_id']], refinement]
        factor = F(1000, row['nominal_sheet_milliohm'])
        prefix = f'{row["voltage_namespace"]}:r{refinement}:n'
        return {(prefix+str(i), prefix+str(j)): factor*F(int(n), int(d))
                for i, j, n, d in template['unit_sheet_stiffness']}
