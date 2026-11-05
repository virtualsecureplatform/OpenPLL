#!/usr/bin/env python3
"""Resolve native node lifetimes and device bindings without printed-name merges.

Reuse the completed instrumented R run. Its device-ID diagnostic was incomplete,
but its saved native R comparison and original .ext permit an independent check
of the physical pointer stream. Do not rerun the full extraction to assess it.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import shlex
import signal
import time
from check_compact_clock_tree import verify
from check_magic_cap_clip_windows import native
from check_isolated_magic_stock_v3 import devices
from inspect_DCO_retained_R_mesh_geometry import provenance
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    left = deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    control = base/'DCO_R_binding_trace_controls_001'
    status = json.loads((control/'status.json').read_text())
    assert status['state'] == 'failed' and 'FileNotFoundError' in status['error']
    comparison = json.loads((control/'network_comparison.json').read_text())
    assert comparison['bijective_mapping_proven'] and comparison['unchanged_device_parameters_and_mapped_terminals']
    assert comparison['exact_mapped_R_branch_multiplicity_preserved'] and not comparison['R_C_differences']['R']
    build = base/'magic_R_binding_trace_build_001/assessment.json'
    assert verify(build)['full_geometry_trace_build_completed']
    source = control/'trace'
    reference = base/'DCO_retained_R_mesh_001/trace'
    top = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    a, ar, _ = native(reference/(top+'.ext'))
    b, br, _ = native(source/(top+'.ext'))
    assert all(abs(b.get(k, 0)-a.get(k, 0)) <= ar.get(k, 0)+br.get(k, 0) for k in a.keys() | b.keys())
    assert devices(reference/(top+'.ext')) == devices(source/(top+'.ext'))
    types, groups = provenance(source/'R_provenance.log')
    out = base/'DCO_native_pointer_binding_index_001'
    out.mkdir(exist_ok=False)
    save(out/'status.json', dict(state='resolving_pointer_lifetimes', release_qualified=False))
    active, parent, bindings, singles, last = {}, {}, [], [], {}
    serial = 0
    counters = Counter()
    def resolve(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n
    with (source/'R_bindings.log').open() as stream:
        for event, line in enumerate(stream, 1):
            f = shlex.split(line)
            kind = f[0]
            counters[kind] += 1
            if kind == 'ALLOC':
                assert len(f) == 2 and f[1] not in active, (event, 'allocation reuses a live pointer', f)
                serial += 1
                active[f[1]] = serial
                parent[serial] = serial
            elif kind == 'MERGE':
                assert len(f) == 3 and f[1] in active and f[2] in active and f[1] != f[2], (event, f)
                parent[resolve(active[f[2]])] = resolve(active[f[1]])
                del active[f[2]]
            elif kind == 'BIND':
                assert len(f) == 8 and f[7] in active, (event, f)
                bindings.append(dict(device_pointer=f[1], point_internal=list(map(int, f[2:4])),
                    type_id=f[4], model=f[5], terminal=int(f[6]), generation=active[f[7]]))
            elif kind == 'SINGLE':
                assert len(f) == 8 and f[1] in active, (event, f)
                singles.append(dict(generation=active[f[1]], box_internal=list(map(int, f[2:6])),
                    type_id=f[6], split=int(f[7])))
            else:
                assert kind == 'GROUP' and len(f) == 3
                group = groups[f[1]]
                assert group['original'] == f[2]
                node_ids, nodes = {}, []
                for ptr, row in group['nodes'].items():
                    assert ptr in active, (event, f, ptr)
                    generation = resolve(active[ptr])
                    assert generation not in node_ids, (event, 'distinct final pointers already merged')
                    identifier = f'_rmesh_{group["id"]}_{generation}'
                    node_ids[generation] = identifier
                    nodes.append(dict(private_id=identifier, native_pointer=ptr, original_conductor=group['original'],
                        printed_name=row['name'], point_internal=row['point']))
                resolved_bindings = []
                for row in bindings:
                    root = resolve(row['generation'])
                    assert root in node_ids, (event, 'device binding absent from final mesh', row)
                    resolved_bindings.append(dict(**row, private_id=node_ids[root], original_conductor=group['original']))
                resolved_singles = []
                for row in singles:
                    root = resolve(row['generation'])
                    assert root in node_ids, (event, 'single tile absent from final mesh', row)
                    resolved_singles.append(dict(**row, private_id=node_ids[root], original_conductor=group['original']))
                last[group['original']] = dict(nodes=nodes, bindings=resolved_bindings, singles=resolved_singles)
                active, parent, bindings, singles = {}, {}, [], []
            if event % 200000 == 0:
                assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
                save(out/'status.json', dict(state='resolving_pointer_lifetimes', events=event, release_qualified=False))
    assert not active and not bindings and not singles and len(last) == 2686
    nodes, rows, cells = [], [], []
    for group in last.values():
        nodes.extend(group['nodes'])
        rows.extend(group['bindings'])
        cells.extend(group['singles'])
    actual = defaultdict(set)
    for row in rows:
        key = (row['model'], *row['point_internal'], row['terminal'])
        actual[key].add(row['private_id'])
    ambiguous = {str(k): sorted(v) for k, v in actual.items() if len(v) != 1}
    save(out/'ambiguous_device_bindings.json', ambiguous)
    assert not ambiguous, list(ambiguous.items())[:4]
    save(out/'nodes.json', nodes)
    save(out/'device_bindings.json', rows)
    save(out/'single_breakpoint_tiles.json', cells)
    model_counts = Counter((row['model'], *row['point_internal']) for row in rows)
    paths = [Path(__file__).resolve(), owner, build, control/'status.json', control/'network_comparison.json',
        source/'R_bindings.log', source/'R_provenance.log', source/(top+'.ext'), reference/(top+'.ext'),
        Path(__file__).with_name('inspect_DCO_retained_R_mesh_geometry.py')]
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in paths},
        artifacts={str(p): sha(p) for p in out.iterdir() if p.name != 'status.json'},
        native_R_graph_and_original_C_device_controls_passed=True,
        incomplete_device_ID_diagnostic_not_retried_by_full_R_extraction=True,
        node_lifetime_events=dict(counters), final_original_conductors=len(last),
        final_native_pointer_nodes=len(nodes), final_device_binding_records=len(rows),
        unique_device_geometry_keys=len(model_counts), unique_terminal_geometry_keys=len(actual),
        single_breakpoint_conductor_tiles=len(cells), ambiguous_terminal_bindings=0,
        node_reuse_and_merges_resolved_by_generation=True,
        private_pointer_runtime_export_or_C_weights_qualified=False,
        release_qualified=False, adopted=False))
    save(out/'status.json', dict(state='native_pointer_binding_index_terminal', release_qualified=False))
    print('Native pointer bindings:', len(nodes), 'nodes;', len(actual), 'unique terminals;', len(cells), 'single-breakpoint tiles.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        out = ROOT/'build/timing400/release_001/DCO_native_pointer_binding_index_001'
        if out.exists():
            save(out/'status.json', dict(state='failed', error=repr(error), release_qualified=False))
        raise
