#!/usr/bin/env python3
"""Bind unreduced native resistor creation tiles to exported mesh branches.

Use creation-time breakpoints rather than assuming that representative node
coordinates describe the routed path. Require branch type/value conservation.
Only rectangular wire segments receive a support rectangle; contacts and split
tiles remain explicitly separate. This does not assign capacitors or qualify RC.
"""
from collections import Counter
from decimal import Decimal
import json
import math
from pathlib import Path
import shlex
import signal
import time
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def provenance(path):
    types, groups = {}, {}
    group = None
    for line in path.open():
        f = shlex.split(line)
        if f[0] == 'TYPE':
            types[f[1]] = f[2]
        elif f[0] == 'BEGIN':
            assert group is None
            group = dict(id=f[1], original=f[2], nodes={}, branches={}, edges=[])
        elif f[0] == 'NODE':
            assert f[1] == group['id'] and len(f) == 8
            group['nodes'][f[2]] = dict(name=f[3], point=list(map(int, f[4:6])))
        elif f[0] == 'BRANCH':
            assert f[1] == group['id'] and len(f) == 4
            group['branches'].setdefault(f[2], []).append(f[3])
        elif f[0] == 'EDGE':
            assert f[1] == group['id'] and len(f) == 8
            group['edges'].append(f[2:])
        elif f[0] == 'END':
            assert f[1] == group['id']
            groups[group['id']] = group
            group = None
        else:
            raise AssertionError(f)
    assert group is None
    return types, groups


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    left = json.loads(owner.read_text())['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    proof = base/'DCO_retained_R_mesh_001/assessment.json'
    assert verify(proof)['original_pre_RC_C_matrix_and_devices_preserved']
    source = proof.parent/'trace'
    types, groups = provenance(source/'R_provenance.log')
    latest, results, creation_count = {}, {}, 0
    for line in (source/'R_segments.log').open():
        f = shlex.split(line)
        if f[0] == 'SEG':
            assert len(f) == 17
            latest[f[1]] = dict(a_creation=f[2], b_creation=f[3],
                breakpoints_internal=[list(map(int, f[4:6])), list(map(int, f[6:8]))],
                tile_internal=list(map(int, f[8:12])), milliohm=f[12],
                type_id=f[13], status=int(f[14]), centerline=int(f[15]), width=int(f[16]))
            creation_count += 1
            continue
        assert f[0] == 'GROUP' and len(f) == 3
        group = groups[f[1]]
        assert group['original'] == f[2]
        counters = Counter()
        records, seen = [], {}
        offsets = Counter()
        for owner_ptr, a, b, value, type_id, status in group['edges']:
            branch = group['branches'][owner_ptr][offsets[owner_ptr]]
            offsets[owner_ptr] += 1
            actual = (frozenset([a, b]), Decimal(value), type_id, int(status))
            if branch in seen:
                assert seen[branch] == actual
                continue
            seen[branch] = actual
            row = dict(original_conductor=group['original'],
                nodes=[group['nodes'][p]['name'] for p in [a, b]],
                representative_points_internal=[group['nodes'][p]['point'] for p in [a, b]],
                milliohm=value, material=types[type_id], type_id=type_id, status=int(status))
            # Every ordinary branch carries EW/NS; contacts have neither flag.
            if int(status) & (0x200 | 0x400):
                assert branch in latest, (group['original'], branch)
                segment = latest[branch]
                assert Decimal(segment['milliohm']) == Decimal(value), (group['original'], segment, row)
                assert segment['type_id'] == type_id
                assert segment['status'] & 0xe00 == int(status) & 0xe00
                row['creation_geometry'] = segment
                counters['wire_segments'] += 1
                if int(status) & 0x800:
                    counters['split_tile_segments'] += 1
                else:
                    # Clip the creation tile to the two resistor breakpoints
                    # on its current-flow axis. Do not move any native node.
                    l, bot, r, top = segment['tile_internal']
                    p, q = segment['breakpoints_internal']
                    if int(status) & 0x200:
                        l, r = sorted([p[0], q[0]])
                    else:
                        bot, top = sorted([p[1], q[1]])
                    assert l <= r and bot <= top
                    row['segment_support_internal'] = [l, bot, r, top]
                    counters['rectangular_wire_segments'] += 1
            else:
                counters['contacts'] += 1
            records.append(row)
        assert all(offsets[p] == len(rows) for p, rows in group['branches'].items())
        results[group['original']] = dict(records=records, counts=dict(counters))
    assert len(results) == 2686
    total = Counter()
    rows = []
    for result in results.values():
        total.update(result['counts'])
        rows.extend(result['records'])
    target = 'COARSETHERMAL_CODE[23]'
    box = [16113, 5266, 16113, 5269]
    remote_hits = []
    for row in results[target]['records']:
        if 'segment_support_internal' not in row:
            continue
        l, b, r, t = row['segment_support_internal']
        if l <= box[2] and r >= box[0] and b <= box[3] and t >= box[1]:
            remote_hits.append(row)
    out = base/'DCO_retained_R_mesh_geometry_001'
    out.mkdir(exist_ok=False)
    save(out/'branches.json', rows)
    save(out/'coarse23_remote_support.json', dict(box_internal=box, intersecting_segments=remote_hits))
    paths = [Path(__file__).resolve(), owner, proof, source/'R_provenance.log', source/'R_segments.log']
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in paths},
        artifacts={str(p): sha(p) for p in out.iterdir()},
        original_conductors=len(results), creation_records=creation_count, final_branch_counts=dict(total),
        wire_branch_type_and_value_preserved_at_creation_and_export=True,
        remote_C_support_intersecting_wire_segments=len(remote_hits),
        native_node_locations_modified=False, capacitor_assignment_qualified=False,
        physical_RC_or_transient_error_qualified=False, release_qualified=False, adopted=False, scope=__doc__))
    print('Native R segment geometry:', dict(total), '; remote C support intersections:', len(remote_hits))


if __name__ == '__main__':
    main()
