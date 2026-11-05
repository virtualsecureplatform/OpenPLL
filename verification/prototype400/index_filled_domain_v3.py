#!/usr/bin/env python3
"""Index new full-assembly R/contact domains through native node lifetimes.

This resolves recorded topology; C attachment and domain coverage remain open.
"""
from collections import Counter
import json
import math
from pathlib import Path
import shlex
import signal
import time
import argparse
import sys
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'timing400'))
from check_compact_clock_tree import verify
from inspect_DCO_retained_R_mesh_geometry import provenance
from common import ROOT, sha, save, verify as verify_hashes
from status_store import update_root


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--original-owner',required=True,type=Path)
    args=parser.parse_args();domain=args.domain.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    original=json.loads(args.original_owner.read_text());budget_start=original.get('budget_started_utc',original['started_utc'])
    elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(budget_start)).total_seconds();remaining=43200-max(0,elapsed)
    assert remaining>0
    started=time.monotonic();deadline=started+remaining
    def expired(*_):raise TimeoutError('original whole-check deadline exhausted')
    signal.signal(signal.SIGALRM,expired);signal.alarm(max(1,int(remaining)))
    def status(state,**kw):
        value=dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False,**kw)
        save(out/'status.json',value);update_root('retained_domain_index',dict(value,path=str(out/'status.json')))
    save(out/'owner.json',dict(started_utc=datetime.now(timezone.utc).isoformat(),wall_limit_s=43200,budget_started_utc=budget_start,original_owner=str(args.original_owner.resolve()),automatic_identical_retry=False))
    while not (domain/'assessment.json').exists():
        if (domain/'status.json').exists():assert json.loads((domain/'status.json').read_text())['state']!='failed'
        assert time.monotonic()<deadline;status('waiting_for_retained_domain_trace');time.sleep(10)
    control=domain/'assessment.json';receipt=json.loads(control.read_text());verify_hashes(receipt['input_sha256']);verify_hashes(receipt['artifacts'])
    assert receipt['native_rc_export_completed']
    signal.alarm(max(1,math.floor(deadline-time.monotonic())))
    base=ROOT/'build/timing400/release_001';source=domain/'trace'
    owner=domain/'owner.json'
    status('indexing_native_domain_records')
    types, groups = provenance(source/'R_provenance.log')
    plane_path = base/'DCO_C_surface_trace_controls_001/nom_trace/surfaces.log'
    plane_names, cap_types = {}, {}
    for line in plane_path.open():
        if line.startswith('PLANE '):
            f = shlex.split(line)
            plane_names[int(f[1])] = f[2]
        elif line.startswith('TYPE '):
            f = shlex.split(line)
            cap_types[f[1]] = f[2]
        elif line.startswith('SURFACE '):
            break
    assert all(cap_types.get(k) == v for k, v in types.items() if k in cap_types)
    active, parent, domains, contacts, bindings, singles = {}, {}, [], [], [], []
    serial = 0
    selected, counts = {}, Counter()
    pending = None
    def resolve(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n
    for line in (source/'R_bindings.log').open():
        f = line.split()
        kind = f[0]
        counts[kind] += 1
        if kind == 'ALLOC':
            assert f[1] not in active
            serial += 1
            active[f[1]] = serial
            parent[serial] = serial
        elif kind == 'MERGE':
            assert f[1] in active and f[2] in active
            parent[resolve(active[f[2]])] = resolve(active[f[1]])
            del active[f[2]]
        elif kind == 'TILE':
            assert len(f) == 11 and (pending is None or len(pending['breakpoints']) == pending['initial_breakpoint_count'])
            pending = dict(tile_serial=int(f[1]), native_tile_pointer=f[2], native_working_plane_id=int(f[3]),
                native_working_plane=plane_names.get(int(f[3]), 'UNKNOWN'), raw_type_id=f[4], raw_material=types[f[4]],
                split=int(f[5]), box_internal=list(map(int, f[6:10])), initial_breakpoint_count=int(f[10]), breakpoints=[])
            domains.append(pending)
        elif kind == 'TBP':
            assert len(f) == 5 and pending and int(f[1]) == pending['tile_serial'] and f[2] in active
            pending['breakpoints'].append(dict(generation=active[f[2]], point_internal=list(map(int, f[3:5]))))
            assert len(pending['breakpoints']) <= pending['initial_breakpoint_count']
        elif kind == 'CONTACT':
            assert len(f) == 15 and f[2] in active
            contacts.append(dict(contact_pointer=f[1], generation=active[f[2]], copy_index=int(f[3]), copies=int(f[4]),
                contact_type_id=f[5], contact_material=types[f[5]], native_working_plane_id=int(f[6]),
                native_working_plane=plane_names.get(int(f[6]), 'UNKNOWN'), tile_pointer=f[7],
                tile_raw_type_id=f[8], tile_material=types[f[8]], center_internal=list(map(int, f[9:11])),
                contact_rectangle_internal=list(map(int, f[11:15]))))
        elif kind == 'BIND':
            f = shlex.split(line)
            assert len(f) == 8 and f[7] in active
            bindings.append(dict(device_pointer=f[1], point_internal=list(map(int, f[2:4])),
                type_id=f[4], model=f[5], terminal=int(f[6]), generation=active[f[7]]))
        elif kind == 'SINGLE':
            assert len(f) == 8 and f[1] in active
            singles.append(dict(generation=active[f[1]], box_internal=list(map(int, f[2:6])), type_id=f[6], split=int(f[7])))
        else:
            assert kind == 'GROUP'
            f = shlex.split(line)
            group = groups[f[1]]
            assert group['original'] == f[2]
            assert pending is None or len(pending['breakpoints']) == pending['initial_breakpoint_count']
            final, nodes = {}, []
            for ptr, node in group['nodes'].items():
                assert ptr in active
                generation = resolve(active[ptr])
                assert generation not in final
                identifier = f'_rmesh_{group["id"]}_{generation}'
                final[generation] = identifier
                nodes.append(dict(private_id=identifier, native_pointer=ptr, original_conductor=group['original'],
                    printed_name=node['name'], point_internal=node['point']))
            def private(generation):
                root = resolve(generation)
                assert root in final, ('snapshot root absent from final mesh', group['original'], generation, root)
                return final[root]
            for row in domains:
                row['original_conductor'] = group['original']
                for bp in row['breakpoints']:
                    bp['private_id'] = private(bp['generation'])
                row['private_voltage_nodes'] = sorted({bp['private_id'] for bp in row['breakpoints']})
            for row in contacts+bindings+singles:
                row['private_id'] = private(row['generation'])
                row['original_conductor'] = group['original']
            selected[group['original']] = dict(nodes=nodes, domains=domains, contacts=contacts, bindings=bindings, singles=singles)
            active, parent, domains, contacts, bindings, singles, pending = {}, {}, [], [], [], [], None
    assert not active and len(selected)>0
    nodes = [r for g in selected.values() for r in g['nodes']]
    domains = [r for g in selected.values() for r in g['domains']]
    contacts = [r for g in selected.values() for r in g['contacts']]
    bindings = [r for g in selected.values() for r in g['bindings']]
    singles = [r for g in selected.values() for r in g['singles']]
    assert nodes
    domain_counts = Counter()
    for row in domains:
        domain_counts['domains'] += 1
        if not row['private_voltage_nodes']:
            domain_counts['no_voltage_anchor'] += 1
        elif len(row['private_voltage_nodes']) == 1:
            domain_counts['constant_voltage_domain'] += 1
            if row['initial_breakpoint_count'] > 1:
                domain_counts['multiple_breakpoints_collapsed_to_one_voltage'] += 1
        else:
            domain_counts['multiple_voltage_wire_domain'] += 1
        if row['native_working_plane_id'] < 0:
            domain_counts['working_plane_not_found'] += 1
    save(out/'nodes.json', nodes)
    save(out/'device_bindings.json', bindings)
    save(out/'single_breakpoint_tiles.json', singles)
    for name, rows in [('tile_domains.jsonl', domains), ('contact_domains.jsonl', contacts)]:
        with (out/name).open('x') as stream:
            for row in rows:
                stream.write(json.dumps(row)+'\n')
    inputs = [Path(__file__).resolve(), owner, control, source/'R_bindings.log', source/'R_provenance.log', plane_path,
        ROOT/'verification/timing400/inspect_DCO_retained_R_mesh_geometry.py']
    artifacts = [out/n for n in ['nodes.json', 'device_bindings.json', 'single_breakpoint_tiles.json', 'tile_domains.jsonl', 'contact_domains.jsonl']]
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(p): sha(p) for p in artifacts}, stream_event_counts=dict(counts), private_nodes=len(nodes),
        original_conductors=len(selected), domain_counts=dict(domain_counts), contact_plane_records=len(contacts),
        contact_working_planes_missing=sum(r['native_working_plane_id'] < 0 for r in contacts),
        
        all_snapshot_generations_resolved_to_final_private_nodes=True,
        physical_voltage_domain_coverage_and_contact_impedance_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    status('retained_domain_index_terminal',private_nodes=len(nodes),original_conductors=len(selected))
    print('Indexed native R domains',dict(domain_counts))


if __name__ == '__main__':
    try:main()
    except BaseException as e:
        if '--output' in sys.argv:
            out=Path(sys.argv[sys.argv.index('--output')+1])
            if out.exists():save(out/'status.json',dict(state='failed',reason=repr(e),release_qualified=False))
        raise
