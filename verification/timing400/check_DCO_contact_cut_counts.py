#!/usr/bin/env python3
"""Count actual GDS cuts in every native contact domain, independently of R.

Match cut-count multisets for parallel branches rather than assigning by a
printed alias or arbitrarily choosing between coincident private endpoints.
"""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import time
import pya

from compile_local_C_operators_v2 import digest, save


LAYERS = {'pdiffc': (66, 44), 'ndiffc': (66, 44), 'polycont': (66, 44),
    'psubdiffcont': (66, 44), 'nsubdiffcont': (66, 44), 'viali': (67, 44),
    'via1': (68, 44), 'via2': (69, 44), 'via3': (70, 44), 'via4': (71, 44)}


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    top = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    gds = root/f'openlane/{top}/runs/c1fine_range_001/final/gds/{top}.gds'
    assert digest(gds) == '0f227ae41fa996eaa23410aecbe7a3b38090185285c768ba24435026f337a2dd'
    rvalues = base/'DCO_domain_R_corners_002'
    contacts = base/'DCO_direct_native_planes_and_boundaries_001/contact_plane_segments.jsonl'
    out = base/'DCO_contact_cut_count_geometry_001'
    out.mkdir(exist_ok=False)
    layout = pya.Layout()
    layout.read(str(gds))
    assert layout.dbu == .001
    cell = layout.cell(top)
    polygons, bins = {}, {}
    grid = 1000
    def cells(box):
        return ((x, y) for x in range(box[0]//grid, box[2]//grid+1)
                for y in range(box[1]//grid, box[3]//grid+1))
    for layer in sorted(set(LAYERS.values())):
        region = pya.Region(cell.begin_shapes_rec(layout.layer(*layer))).merged()
        polygons[layer] = [p for p in region.each()]
        bins[layer] = defaultdict(set)
        for index, poly in enumerate(polygons[layer]):
            b = poly.bbox()
            for q in cells([b.left, b.bottom, b.right, b.top]):
                bins[layer][q].add(index)
    def key(r, material):
        return r['original_conductor'], tuple(sorted(r['private_nodes'])), material
    expected = defaultdict(Counter)
    for text in (rvalues/'branches.jsonl').open():
        r = json.loads(text)
        if r['kind'] == 'contact':
            expected[key(r, r['material'])][r['native_parallel_cut_count']] += 1
    observed = defaultdict(Counter)
    count = Counter()
    unresolved = []
    with (out/'contact_counts.jsonl').open('x') as stream:
        for text in contacts.open():
            r = json.loads(text)
            layer = LAYERS[r['contact_material']]
            box = [5*v for v in r['contact_rectangle_internal']]
            query = pya.Region(pya.Box(*box))
            candidates = set()
            for q in cells(box):
                candidates.update(bins[layer].get(q, ()))
            inside, crossing = [], []
            for index in candidates:
                poly = pya.Region(polygons[layer][index])
                if not (poly & query).is_empty():
                    (inside if (poly-query).is_empty() else crossing).append(index)
            observed[key(r, r['contact_material'])][len(inside)] += 1
            count['contact_branches'] += 1
            count['actual_cuts_in_contact_branches'] += len(inside)
            if crossing or not inside:
                unresolved.append(dict(contact=r, actual_inside_cuts=len(inside), boundary_crossing_cuts=len(crossing)))
            stream.write(json.dumps(dict(**r, GDS_cut_layer=list(layer), GDS_cuts_fully_inside=len(inside),
                GDS_cuts_crossing_boundary=len(crossing)))+'\n')
            if count['contact_branches'] % 1000 == 0:
                assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
                save(out/'status.json', dict(state='counting_GDS_cuts', counts=dict(count)))
    differences = []
    for k in expected.keys() | observed.keys():
        if expected.get(k) != observed.get(k):
            differences.append(dict(original_conductor=k[0], private_nodes=list(k[1]), material=k[2],
                native_cut_count_multiplicities=dict(expected.get(k, {})),
                GDS_cut_count_multiplicities=dict(observed.get(k, {}))))
    assert count['contact_branches'] == 35578
    save(out/'unresolved.json', unresolved)
    save(out/'differences.json', differences)
    inputs = [Path(__file__).resolve(), owner, gds, contacts, rvalues/'branches.jsonl', rvalues/'assessment.json']
    artifacts = [out/'contact_counts.jsonl', out/'unresolved.json', out/'differences.json']
    passed = not unresolved and not differences
    result = dict(all35578_native_contact_branch_cut_counts_match_actual_GDS=passed,
        counts=dict(count), mismatched_endpoint_material_groups=len(differences), unresolved_boundaries=len(unresolved),
        GDS_cut_polygons_by_layer={str(k): len(v) for k, v in polygons.items()},
        independent_contact_cut_geometry_qualified=passed, finite_contact_sheet_approximation_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256={str(p.resolve()): digest(p) for p in inputs},
        artifacts={str(p.resolve()): digest(p) for p in artifacts})
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(out/'assessment.json', result)
    save(out/'status.json', dict(state='completed', contact_cut_counts_match=passed, counts=dict(count)))
    print(json.dumps({k: v for k, v in result.items() if k not in ['input_sha256', 'artifacts']}, indent=2))


if __name__ == '__main__':
    main()
