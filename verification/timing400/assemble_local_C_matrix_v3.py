#!/usr/bin/env python3
"""Assemble saved signed operators on their owned native voltage domains.

No nearest-node attachment, ideal-conductor alias merge, or averaged-field
capacitor shortcut is used. The substrate reference is an explicit vertex.
The output is a candidate matrix; runtime qualification is separate.
"""
import argparse
from collections import Counter, defaultdict
import json
import math
import os
from pathlib import Path
import time
import traceback

from compile_local_C_operators_v2 import digest, save, project
from local_C_field_integrals import area, line, fringe


def intersection(a, b):
    c = [max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])]
    return c if c[0] < c[2] and c[1] < c[3] else None


class Atlas:
    def __init__(self, domain_path, fields):
        self.grid = 800
        self.fields = fields
        self.bins = defaultdict(lambda: defaultdict(set))
        self.domains = []
        lookup = {tuple(key): n for n, key in enumerate(fields)}
        for text in domain_path.open():
            row = json.loads(text)
            key = row['original_conductor'], row['plane'], row['effective_material']
            if key not in lookup:
                continue
            index = len(self.domains)
            self.domains.append(row)
            for cell in self.cells(row['box_internal']):
                self.bins[lookup[key]][cell].add(index)
        self.reference = dict(axis=None, voltage_knots_internal=[(0, '_dco_substrate_reference')])

    def cells(self, box):
        return ((x, y) for x in range(math.floor(box[0]/self.grid), math.floor(box[2]/self.grid)+1)
                for y in range(math.floor(box[1]/self.grid), math.floor(box[3]/self.grid)+1))

    def candidates(self, field, box):
        found = set()
        for cell in self.cells(box):
            found.update(self.bins[field].get(cell, ()))
        return [self.domains[n] for n in sorted(found)]

    def rectangles(self, field, box):
        if field == 0:
            return [(self.reference, box)]
        result = []
        for domain in self.candidates(field, box):
            clip = intersection(box, domain['box_internal'])
            if clip is not None:
                result.append((domain, clip))
        covered = sum((p[2]-p[0])*(p[3]-p[1]) for _, p in result)
        assert covered == (box[2]-box[0])*(box[3]-box[1]), ('area ownership', self.fields[field], box, covered)
        return result

    def edges(self, field, edge, inward):
        if field == 0:
            return [(self.reference, edge)]
        along = 1 if edge[0] == edge[2] else 0
        normal = 1-along
        assert inward in [1, 2, 4, 8]
        assert normal == (0 if inward in [1, 4] else 1)
        offset = .25 if inward in [1, 8] else -.25
        point = edge[normal]+offset
        query = list(edge)
        query[normal] = query[normal+2] = point
        result = []
        for domain in self.candidates(field, query):
            box = domain['box_internal']
            if not box[normal] < point < box[normal+2]:
                continue
            lo, hi = max(edge[along], box[along]), min(edge[along+2], box[along+2])
            if lo < hi:
                clip = list(edge)
                clip[along], clip[along+2] = lo, hi
                result.append((domain, clip))
        result.sort(key=lambda row: row[1][along])
        cursor = edge[along]
        for _, p in result:
            assert p[along] == cursor, ('edge gap/overlap', self.fields[field], edge, inward, cursor, p)
            cursor = p[along+2]
        assert cursor == edge[along+2], ('edge ownership', self.fields[field], edge, inward, cursor)
        return result


def integrate_operator(atlas, row):
    kind, a, b, serial, *data = row
    if kind == 'A':
        patch, density = data
        if not density or patch[0] == patch[2] or patch[1] == patch[3]:
            return
        for source, clip in atlas.rectangles(a, patch):
            for target, cell in atlas.rectangles(b, clip):
                yield area(source, target, cell, density)
    elif kind == 'L':
        source_edge, target_edge, density, source_inside, target_inside = data
        if not density:
            return
        along = 1 if source_edge[0] == source_edge[2] else 0
        for source, se in atlas.edges(a, source_edge, source_inside):
            te = list(target_edge)
            te[along], te[along+2] = se[along], se[along+2]
            for target, tc in atlas.edges(b, te, target_inside):
                sc = list(se)
                sc[along], sc[along+2] = tc[along], tc[along+2]
                yield line(source, target, sc, tc, density)
    else:
        assert kind == 'F'
        source_edge, patch, direction, cap, mult = data
        if not cap or not mult or patch[0] == patch[2] or patch[1] == patch[3]:
            return
        along = 1 if source_edge[0] == source_edge[2] else 0
        edge = project(source_edge, patch)
        for source, segment in atlas.edges(a, edge, direction):
            strip = list(patch)
            strip[along], strip[along+2] = segment[along], segment[along+2]
            for target, cell in atlas.rectangles(b, strip):
                yield fringe(source, target, source_edge, cell, direction, cap, mult)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--operators', type=Path, required=True)
    parser.add_argument('--family', type=Path, required=True)
    parser.add_argument('--owner', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--corner', choices=['min', 'nom', 'max'], required=True)
    args = parser.parse_args()
    deadline = json.loads(args.owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    # Require the compiler's terminal assessment, not a partly written stream.
    proof = json.loads((args.operators/'assessment.json').read_text())
    assert proof['local_operator_integrals_match_native_physical_totals']
    trace_directories = {Path(name).parent.name for name in proof['input_sha256']
        if Path(name).name == 'kernels.log'}
    assert trace_directories == {args.corner+'_trace'}
    assert proof['finite_R_same_conductor_pair_energy_restored']
    fields = json.loads((args.operators/'fields.json').read_text())
    atlas = Atlas(args.family/'voltage_domains.jsonl', fields)
    nodes = ['_dco_substrate_reference'] + sorted(row['private_id'] for row in json.loads((args.family/'nodes.json').read_text()))
    node_index = {name: index for index, name in enumerate(nodes)}
    size = len(nodes)
    matrix = defaultdict(float)
    count = Counter()
    args.output.mkdir(parents=True, exist_ok=False)
    def status(state, **extra):
        save(args.output/'status.json', dict(state=state, runner_pid=os.getpid(), counts=dict(count),
            upper_nonzeros=len(matrix), deadline_uptime=deadline, **extra))
    status('assembling')
    try:
        with (args.operators/'operators.jsonl').open() as stream:
            for text in stream:
                row = json.loads(text)
                count['operators'] += 1
                count[row[0]] += 1
                for local in integrate_operator(atlas, row):
                    count['domain_cells'] += 1
                    for (a, b), value in local.items():
                        ia, ib = node_index[a], node_index[b]
                        if ia > ib:
                            ia, ib = ib, ia
                        matrix[ia*size+ib] += value
                if count['operators'] % 10000 == 0:
                    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
                    status('assembling', event_serial=row[3])
        assert count['operators'] == proof['counts']['operators']
        assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
        status('serializing_and_checking_charge_conservation')
        import numpy as np
        from scipy.sparse import coo_matrix, save_npz, diags
        encoded = np.fromiter(matrix.keys(), dtype=np.int64, count=len(matrix))
        values = np.fromiter(matrix.values(), dtype=np.float64, count=len(matrix))
        upper = coo_matrix((values, (encoded//size, encoded % size)), shape=(size, size)).tocsr()
        symmetric = upper + upper.T - diags(upper.diagonal())
        charge_error = np.asarray(symmetric.sum(axis=1)).ravel()
        row_norm = np.asarray(abs(symmetric).sum(axis=1)).ravel()
        scaled = abs(charge_error)/np.maximum(row_norm, 1e-30)
        assert np.isfinite(values).all() and max(scaled) < 1e-11, max(scaled)
        save_npz(args.output/'C_native_units.npz', symmetric)
        save(args.output/'nodes.json', nodes)
        inputs = [Path(__file__).resolve(), Path(__file__).with_name('local_C_field_integrals.py'),
            Path(__file__).with_name('compile_local_C_operators_v2.py'), args.owner,
            args.operators/'assessment.json', args.operators/'operators.jsonl', args.operators/'fields.json',
            args.family/'nodes.json', args.family/'voltage_domains.jsonl', args.family/'assessment.json']
        artifacts = [args.output/'C_native_units.npz', args.output/'nodes.json']
        assessment = dict(full_nominal_C_energy_matrix_assembled=args.corner == 'nom',
            full_C_energy_matrix_assembled=True, RC_corner=args.corner, counts=dict(count),
            explicit_substrate_reference_vertex=True, native_private_voltage_vertices=len(nodes)-1,
            maximum_relative_charge_row_residual=float(max(scaled)), matrix_nonzeros=symmetric.nnz,
            capacitance_unit_F=1e-18, signed_global_passivity_qualified=False,
            runtime_model_eligible=False, release_qualified=False, adopted=False,
            input_sha256={str(p.resolve()): digest(p) for p in inputs},
            artifacts={str(p.resolve()): digest(p) for p in artifacts}, deadline_uptime=deadline)
        assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
        save(args.output/'assessment.json', assessment)
        status('completed')
    except BaseException:
        status('failed_or_inconclusive', error=traceback.format_exc())
        raise


if __name__ == '__main__':
    main()
