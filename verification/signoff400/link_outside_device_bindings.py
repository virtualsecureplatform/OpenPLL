#!/usr/bin/env python3
"""Retain exact current outside-endpoint/device-private-node associations.

The BIND point is the native extracted device location, not a certified
terminal contact coordinate. No association relocates or qualifies a node.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import time
from common import ROOT, save, sha


def classify(endpoint, bindings):
    for b in bindings:
        if (b['native_group_id'], b['private_id'], b['original_conductor']) != (
                endpoint['group'], endpoint['private_id'], endpoint['conductor']):
            raise ValueError('device association crosses native snapshot/private identity')
        if b['terminal'] not in (1, 2, 3, 4):
            raise ValueError('unmodeled native terminal enum')
    exact = [b for b in bindings if b['point_internal'] == endpoint['creation_point']]
    kind = ('exact_device_location' if exact else 'same_private_node_different_device_location'
            if bindings else 'no_device_binding')
    return dict(endpoint=endpoint, association=kind, device_bindings=bindings,
                exact_device_location_count=len(exact),
                binding_location_is_certified_terminal_coordinate=False,
                endpoint_relocated=False, physical_interface_qualified=False, release_qualified=False)


def run(registration, index, output):
    registration, index, out = (Path(p).resolve() for p in (registration, index, output))
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    save(out/'status.json', dict(state='linking_current_outside_device_private_nodes', release_qualified=False))
    try:
        rr, ir = registration/'assessment.json', index/'assessment.json'
        r, i = json.loads(rr.read_text()), json.loads(ir.read_text())
        domains = [p for p in i['input_sha256'] if p.endswith('/domain/assessment.json')]
        if len(domains) != 1 or r['input_sha256'].get(domains[0]) != i['input_sha256'][domains[0]]:
            raise ValueError('registration/index domain lineage mismatch')
        source, binding = registration/'native/outside_endpoints.jsonl', index/'device_bindings.json'
        native = ROOT/'build/timing400/magic_R_tile_domain_source_001/resis'
        paths = [rr, ir, source, binding, Path(domains[0]), native/'ResPrint.c', native/'ResRex.c',
                 native/'ResReadExt.c', native/'resis.h', Path(__file__).resolve(), Path(__file__).with_name('common.py')]
        pins = {str(p): sha(p) for p in paths}
        if pins[str(source)] != r['artifacts'][str(source)] or pins[str(binding)] != i['artifacts'][str(binding)]:
            raise ValueError('complete association input hashes differ from producer')
        code = (native/'ResPrint.c').read_text()
        if 'dev->location.p_x, dev->location.p_y' not in code:
            raise ValueError('native BIND coordinate semantics changed')
        endpoints = [json.loads(line) for line in source.open()]
        if len(endpoints) != r['outside_endpoint_count']:
            raise ValueError('outside endpoint coverage mismatch')
        wanted = {(e['group'], e['private_id']) for e in endpoints}
        matches = defaultdict(list)
        for b in json.loads(binding.read_text()):
            key = (b['native_group_id'], b['private_id'])
            if key in wanted:
                matches[key].append(b)
        counts, materials, models, terminals = Counter(), Counter(), Counter(), Counter()
        branches = set()
        with (out/'associations.jsonl').open('x') as target:
            for e in endpoints:
                if time.monotonic()-start >= 43200:
                    raise TimeoutError('outside device association deadline')
                record = classify(e, matches.get((e['group'], e['private_id']), []))
                counts[record['association']] += 1
                materials[e['material']] += 1
                branches.add((e['group'], e['branch']))
                for b in record['device_bindings']:
                    models[b['model']] += 1
                    terminals[str(b['terminal'])] += 1
                target.write(json.dumps(record)+'\n')
        for p, h in pins.items():
            if sha(p) != h:
                raise ValueError('association input changed: '+p)
        result = dict(input_sha256=pins, artifacts={str(out/'associations.jsonl'): sha(out/'associations.jsonl')},
             outside_endpoints=len(endpoints), outside_branches=len(branches), association_counts=counts,
             endpoint_material_counts=materials, binding_model_occurrences=models, binding_terminal_occurrences=terminals,
             all_outside_endpoints_retained=True, device_location_is_not_terminal_geometry=True,
             physical_interface_qualified=False, outside_geometry_resolved=False,
             runtime_model_eligible=False, release_qualified=False, elapsed_s=time.monotonic()-start)
        save(out/'assessment.json', result)
        save(out/'status.json', dict(state='outside_binding_associations_complete_geometry_unresolved',
             release_qualified=False, elapsed_s=result['elapsed_s']))
        return result
    except BaseException as exc:
        save(out/'status.json', dict(state='failed', reason=repr(exc), release_qualified=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('registration', 'index', 'output'):
        p.add_argument('--'+name, required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(run(a.registration, a.index, a.output)))
