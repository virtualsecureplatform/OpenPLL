#!/usr/bin/env python3
"""Inventory every nominal C endpoint with its native plane/material identity.

No voltage-node assignment or integration weight is inferred by this inventory.
"""
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import os
import shlex
import signal
import time
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    left = json.loads(owner.read_text())['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    trace = base/'DCO_C_surface_trace_controls_001/nom_trace'
    mapping = json.loads((trace/'node_ids.json').read_text())
    nodes = base/'DCO_private_R_primitives_001/nodes.json'
    conductors = {r['original_conductor'] for r in json.loads(nodes.read_text())}
    out = base/'DCO_layer_qualified_C_endpoint_inventory_001'
    out.mkdir(exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    def status(state, **values):
        save(out/'status.json', dict(state=state, runner_pid=os.getpid(), started_utc=started,
            deadline_uptime=json.loads(owner.read_text())['deadline_uptime'], **values))
    status('scanning_native_C_endpoints')
    types, planes, endpoints = {}, {}, Counter()
    count = endpoint_count = 0
    with (trace/'surfaces.log').open() as auxiliary:
        def next_surface():
            for line in auxiliary:
                if line.startswith(('TYPE ', 'PLANE ')):
                    f = shlex.split(line)
                    (types if f[0] == 'TYPE' else planes)[int(f[1])] = f[2]
                elif line.startswith('SURFACE '):
                    return line.split()
                elif line.startswith('END '):
                    assert int(line.split()[1]) == count
            return None
        for line in (trace/'contributions.log').open():
            if not line.startswith(('OPENPLL_G ', 'OPENPLL_P ')):
                continue
            f = line.split()
            count += 1
            surface = next_surface()
            kind = f[0][-1]
            assert surface is not None and surface[:3] == ['SURFACE', str(count), kind]
            if kind == 'G':
                assert f[4] == 'box'
                parts = [(f[1], f[5:9], surface[3:6])]
            else:
                parts = [(f[1], f[6:10], surface[3:6]), (f[2], f[10:14], surface[6:9])]
            for ptr, box, material in parts:
                name = mapping[ptr]
                if name == '@SUBSTRATE':
                    name = 'VGND'
                plane, raw, effective = map(int, material)
                assert plane in planes and effective in types
                endpoints[name, plane, raw, effective, *map(int, box)] += 1
                endpoint_count += 1
            if count % 500000 == 0:
                status('scanning_native_C_endpoints', native_contributions=count,
                    endpoint_occurrences=endpoint_count, unique_endpoints=len(endpoints))
        assert next_surface() is None
    assert count == 8297230
    by_plane, by_material, by_coverage = Counter(), Counter(), Counter()
    unmatched = Counter()
    status('writing_layer_qualified_endpoint_inventory', native_contributions=count,
        endpoint_occurrences=endpoint_count, unique_endpoints=len(endpoints))
    with (out/'endpoints.jsonl').open('x') as stream:
        for key, occurrences in endpoints.items():
            name, plane, raw, effective, *box = key
            coverage = 'native_private_R_conductor' if name in conductors else 'outside_private_R_conductor_inventory'
            by_plane[planes[plane]] += 1
            by_material[types[effective]] += 1
            by_coverage[coverage] += 1
            if name not in conductors:
                unmatched[name] += 1
            stream.write(json.dumps(dict(original_conductor=name, plane=planes[plane],
                effective_material=types[effective], raw_type=raw, box_internal=box,
                native_endpoint_occurrences=occurrences, conductor_coverage=coverage), separators=(',', ':'))+'\n')
    inputs = [Path(__file__).resolve(), owner, nodes, trace/'node_ids.json',
        trace/'contributions.log', trace/'surfaces.log', trace.parent/'assessment.json']
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(out/'endpoints.jsonl'): sha(out/'endpoints.jsonl')},
        RC_corner='nom', native_contributions=count, endpoint_occurrences=endpoint_count,
        unique_layer_material_endpoints=len(endpoints), counts_by_plane=dict(by_plane),
        counts_by_effective_material=dict(by_material), counts_by_conductor_coverage=dict(by_coverage),
        conductors_outside_private_R_inventory=dict(unmatched),
        implicit_ground_endpoint_representation='VGND substrate/well mesh remains physically unqualified',
        physical_endpoint_geometry_weights_and_transient_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    status('layer_qualified_endpoint_inventory_terminal', native_contributions=count,
        endpoint_occurrences=endpoint_count, unique_endpoints=len(endpoints), release_qualified=False)
    print('Complete nominal plane/material endpoint inventory:', len(endpoints), 'unique; unmatched', dict(unmatched))


if __name__ == '__main__':
    main()
