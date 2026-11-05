#!/usr/bin/env python3
"""Build one consistent private R/device/voltage-domain family from complete trace.

Use a new node namespace so these primitives cannot silently mix with earlier
mesh families. Every creation endpoint is resolved from its exact tile BP record.
"""
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
import json
import math
import shlex
import signal
import time
from check_compact_clock_tree import verify
from inspect_DCO_retained_R_mesh_geometry import provenance
from build_DCO_private_R_primitives import f32
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    left = json.loads(owner.read_text())['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    index = base/'DCO_complete_R_tile_domain_index_001/assessment.json'
    assert verify(index)['all_snapshot_generations_resolved_to_final_private_nodes']
    exact = base/'DCO_exact_junction_device_primitives_001/assessment.json'
    assert verify(exact)['exact_AP_private_connections_and_all_other_parameters_checked_in_emitted_deck']
    node_path = index.parent/'nodes.json'
    raw_nodes = json.loads(node_path.read_text())
    by_trace = {r['private_id']: r for r in raw_nodes}
    rename = lambda n: n.replace('_rmesh_', '_rdomain_', 1)
    nodes = [dict(r, trace_private_id=r['private_id'], private_id=rename(r['private_id'])) for r in raw_nodes]
    private_ids = {r['private_id'] for r in nodes}
    by_pointer = {(r['private_id'].split('_')[2], r['native_pointer']): r['private_id'] for r in raw_nodes}
    selected_groups = {key[0] for key in by_pointer}
    source = base/'DCO_R_tile_domain_trace_controls_001/trace'
    topname = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    ext = source/(topname+'.ext')
    parent = {}
    def canonical(n):
        parent.setdefault(n, n)
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n
    for line in ext.open():
        if line.startswith('equiv '):
            f = shlex.split(line)
            parent[canonical(f[1])] = canonical(f[2])
    bindings_path = index.parent/'device_bindings.json'
    bindings = defaultdict(set)
    for r in json.loads(bindings_path.read_text()):
        bindings[r['model'], *r['point_internal'], r['terminal']].add(r['private_id'])
    exact_path = exact.parent/'device_connections_candidate.json'
    devices = json.loads(exact_path.read_text())
    device_lines = []
    for name, r in devices.items():
        codes = r['native_terminal_codes']
        x, y = r['rectangle_internal'][:2]
        trace_nodes = []
        for code in codes:
            found = bindings[r['model'], x, y, code]
            assert len(found) == 1
            trace_nodes.append(next(iter(found)))
        assert all(canonical(by_trace[n]['original_conductor']) == canonical(old)
                   for n, old in zip(trace_nodes, r['original_card'][:len(codes)]))
        params = r['exact_junction_private_candidate_card'][len(codes):]
        r['source_family_private_terminals'] = r['private_terminals']
        r['private_terminals'] = list(map(rename, trace_nodes))
        r['exact_junction_private_candidate_card'] = r['private_terminals']+params
        assert all(n in private_ids for n in r['private_terminals'])
        device_lines.append(name+' '+' '.join(r['exact_junction_private_candidate_card']))
    types, groups = provenance(source/'R_provenance.log')
    branch_rows, grouped_branches, printed = [], defaultdict(list), Counter()
    for group_id, group in groups.items():
        if group_id not in selected_groups:
            continue
        offsets, seen = Counter(), set()
        for owner_ptr, a, b, value, type_id, status in group['edges']:
            branch = group['branches'][owner_ptr][offsets[owner_ptr]]
            offsets[owner_ptr] += 1
            if branch in seen:
                continue
            seen.add(branch)
            trace_ends = [by_pointer[group_id, p] for p in [a, b]]
            assert trace_ends[0] != trace_ends[1]
            assert all(by_trace[n]['original_conductor'] == group['original'] for n in trace_ends)
            milliohm = Decimal(value)
            assert milliohm > 0
            row = dict(index=len(branch_rows)+1, native_group=group_id, native_branch=branch,
                private_nodes=list(map(rename, trace_ends)), trace_private_nodes=trace_ends,
                original_conductor=group['original'], resistance_ohm=str(milliohm/1000),
                native_milliohm=value, material_type_id=type_id, material=types[type_id], status=int(status))
            branch_rows.append(row)
            grouped_branches[group_id].append(row)
            names = tuple(sorted(by_trace[n]['printed_name'] for n in trace_ends))
            printed[names, Decimal(format(f32(float(milliohm)/1000), '.6g'))] += 1
    expected = Counter()
    for line in (source/(topname+'.res.ext')).open():
        if line.startswith('resist '):
            f = shlex.split(line)
            expected[tuple(sorted(f[1:3])), Decimal(f[3])] += 1
    assert printed == expected and len(branch_rows) == 166286
    domain_path = index.parent/'tile_domains.jsonl'
    domains = [json.loads(l) for l in domain_path.open()]
    lookup = defaultdict(list)
    for r in domains:
        lookup[r['original_conductor'], r['raw_type_id'], tuple(r['box_internal'])].append(r)
    latest, geometries = {}, []
    by_domain = defaultdict(list)
    for line in (source/'R_segments.log').open():
        f = line.split()
        if f[0] == 'SEG':
            latest[f[1]] = f
        elif f[1] in selected_groups:
            for row in grouped_branches[f[1]]:
                if not row['status'] & 0x600:
                    continue
                seg = latest[row['native_branch']]
                box = tuple(map(int, seg[8:12]))
                candidates = lookup[row['original_conductor'], row['material_type_id'], box]
                assert len(candidates) == 1
                domain = candidates[0]
                points = defaultdict(set)
                for bp in domain['breakpoints']:
                    points[tuple(bp['point_internal'])].add(bp['private_id'])
                a, b = tuple(map(int, seg[4:6])), tuple(map(int, seg[6:8]))
                assert len(points[a]) == len(points[b]) == 1
                oriented = [next(iter(points[a])), next(iter(points[b]))]
                assert set(oriented) == set(row['trace_private_nodes'])
                assert Decimal(seg[12]) == Decimal(row['native_milliohm'])
                assert seg[13] == row['material_type_id']
                item = dict(**row, domain_serial=domain['tile_serial'],
                    oriented_private_nodes=list(map(rename, oriented)), creation_breakpoints_internal=[list(a), list(b)],
                    creation_tile_internal=list(box), centerline=int(seg[15]), width=int(seg[16]))
                geometries.append(item)
                by_domain[domain['tile_serial']].append(item)
    assert len(geometries) == 130708
    fields, counts = [], Counter()
    residue = {
        'polycont': {'active': 'poly', 'locali': 'locali'},
        'ndiffc': {'active': 'ndiff', 'locali': 'locali'},
        'pdiffc': {'active': 'pdiff', 'locali': 'locali'},
        'psubdiffcont': {'well': 'pwell', 'active': 'psubdiff', 'locali': 'locali'},
        'nsubdiffcont': {'well': 'nwell', 'active': 'nsubdiff', 'locali': 'locali'},
        'viali': {'locali': 'locali', 'metal1': 'metal1'},
        **{f'via{i}': {f'metal{i}': f'metal{i}', f'metal{i+1}': f'metal{i+1}'} for i in range(1, 5)}}
    for d in domains:
        assert d['native_working_plane_id'] >= 0 and d['private_voltage_nodes']
        material = residue[d['raw_material']][d['native_working_plane']] if d['raw_material'] in residue else d['raw_material']
        segments = by_domain[d['tile_serial']]
        if len(d['private_voltage_nodes']) == 1:
            assert not segments
            axis, knots = None, [[0, rename(d['private_voltage_nodes'][0])]]
            counts['constant_domains'] += 1
            counts['multi_breakpoint_constant_domains'] += d['initial_breakpoint_count'] > 1
        else:
            assert segments
            axes = {0 if r['status'] & 0x200 else 1 for r in segments}
            assert len(axes) == 1
            axis = next(iter(axes))
            segments.sort(key=lambda r: r['creation_breakpoints_internal'][0][axis])
            knots = [[segments[0]['creation_breakpoints_internal'][0][axis], segments[0]['oriented_private_nodes'][0]]]
            for r in segments:
                assert knots[-1] == [r['creation_breakpoints_internal'][0][axis], r['oriented_private_nodes'][0]]
                knots.append([r['creation_breakpoints_internal'][1][axis], r['oriented_private_nodes'][1]])
            assert {n for _, n in knots} == set(map(rename, d['private_voltage_nodes']))
            counts['wire_domains'] += 1
        fields.append(dict(domain_serial=d['tile_serial'], original_conductor=d['original_conductor'],
            plane=d['native_working_plane'], effective_material=material, raw_material=d['raw_material'],
            box_internal=d['box_internal'], axis=axis, voltage_knots_internal=knots,
            physical_RC_error_qualified=False))
    assert counts['constant_domains'] == 9499 and counts['wire_domains'] == 55663
    out = base/'DCO_complete_domain_model_primitives_001'
    out.mkdir(exist_ok=False)
    save(out/'nodes.json', nodes)
    save(out/'device_connections.json', devices)
    (out/'devices_unqualified.spice').write_text('* Unqualified complete-domain private device primitives.\n'+'\n'.join(device_lines)+'\n')
    with (out/'wire_R_elements_unqualified.spice').open('x') as stream:
        stream.write('* Unqualified complete-domain private native wire resistance primitives.\n')
        for row in branch_rows:
            stream.write(f'Rdomain_{row["index"]} {row["private_nodes"][0]} {row["private_nodes"][1]} {row["resistance_ohm"]}\n')
    for name, rows in [('branches.jsonl', branch_rows), ('wire_geometry.jsonl', geometries), ('voltage_domains.jsonl', fields)]:
        with (out/name).open('x') as stream:
            for row in rows:
                stream.write(json.dumps(row)+'\n')
    inputs = [Path(__file__).resolve(), owner, index, exact, node_path, bindings_path, exact_path, domain_path,
        ext, source/(topname+'.res.ext'), source/'R_provenance.log', source/'R_segments.log',
        Path(__file__).with_name('inspect_DCO_retained_R_mesh_geometry.py'),
        Path(__file__).with_name('build_DCO_private_R_primitives.py')]
    artifacts = [out/n for n in ['nodes.json', 'device_connections.json', 'devices_unqualified.spice',
        'wire_R_elements_unqualified.spice', 'branches.jsonl', 'wire_geometry.jsonl', 'voltage_domains.jsonl']]
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(p): sha(p) for p in artifacts}, native_wire_R_primitives=166286,
        device_primitives=8620, private_voltage_nodes=148346, voltage_domain_counts=dict(counts),
        complete_voltage_domains=len(fields), all_wire_endpoints_bound_by_exact_tile_breakpoint_lifetimes=True,
        full_native_R_multiplicity_and_printed_values_reproduced=True,
        all_devices_bound_by_geometry_with_exact_local_AP_parameters_preserved=True,
        private_namespace='_rdomain_', previous_mesh_family_IDs_mixed=False,
        external_boundary_adaptor_C_weights_and_spatial_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    print('Complete consistent domain family:', len(fields), 'voltage domains;', len(branch_rows), 'native R;',
          len(devices), 'devices; exact BP lifetime binding; external boundaries/C weights remain open.')


if __name__ == '__main__':
    main()
