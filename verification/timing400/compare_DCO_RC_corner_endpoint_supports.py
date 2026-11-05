#!/usr/bin/env python3
"""Check min/max endpoint geometry against the fully sampled nominal inventory.

Compare support sets, never capacitance coefficients or physical RC accuracy.
"""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shlex
import signal
import time
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    left = deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    geometry_proof = base/'DCO_all_C_endpoint_GDS_identity_001/assessment.json'
    assert verify(geometry_proof)['all_nominal_endpoint_samples_on_expected_GDS_layer_conductor_or_well']
    inventory_proof = base/'DCO_layer_qualified_C_endpoint_inventory_001/assessment.json'
    inventory = verify(inventory_proof)
    nominal = inventory_proof.parent/'endpoints.jsonl'
    lookup = {}
    for line in nominal.open():
        row = json.loads(line)
        key = (row['original_conductor'], row['plane'], row['effective_material'], row['raw_type'], *row['box_internal'])
        assert key not in lookup
        lookup[key] = len(lookup)
    assert len(lookup) == inventory['unique_layer_material_endpoints']
    out = base/'DCO_RC_corner_endpoint_support_comparison_001'
    out.mkdir(exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    results, inputs = [], [Path(__file__).resolve(), owner, geometry_proof, inventory_proof, nominal]
    def status(state, **data):
        save(out/'status.json', dict(state=state, runner_pid=os.getpid(), started_utc=started,
            deadline_uptime=deadline, **data))
    for corner, expected_events in [('min', 8297231), ('max', 8297288)]:
        trace = base/'DCO_C_surface_trace_controls_001'/(corner+'_trace')
        mapping = json.loads((trace/'node_ids.json').read_text())
        types, planes, seen, extras = {}, {}, set(), set()
        count = occurrences = 0
        status('comparing_corner_endpoint_supports', corner=corner, contributions_checked=0)
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
                    endpoints = [(f[1], f[5:9], surface[3:6])]
                else:
                    endpoints = [(f[1], f[6:10], surface[3:6]), (f[2], f[10:14], surface[6:9])]
                for ptr, box, material in endpoints:
                    name = mapping[ptr]
                    if name == '@SUBSTRATE':
                        name = 'VGND'
                    plane, raw, effective = map(int, material)
                    key = (name, planes[plane], types[effective], raw, *map(int, box))
                    index = lookup.get(key)
                    if index is None:
                        extras.add(key)
                    else:
                        seen.add(index)
                    occurrences += 1
                if count % 500000 == 0:
                    status('comparing_corner_endpoint_supports', corner=corner, contributions_checked=count,
                        nominal_unique_supports_seen=len(seen), unique_extra_supports=len(extras))
            assert next_surface() is None
        assert count == expected_events
        missing = [key for key, index in lookup.items() if index not in seen]
        save(out/(corner+'_extra_endpoints.json'), sorted(extras))
        save(out/(corner+'_missing_endpoints.json'), missing)
        results.append(dict(corner=corner, native_contributions=count, endpoint_occurrences=occurrences,
            nominal_unique_supports_seen=len(seen), unique_extra_supports=len(extras),
            unique_missing_supports=len(missing), endpoint_support_set_identical_to_nominal=not extras and not missing))
        inputs.extend([trace/'node_ids.json', trace/'contributions.log', trace/'surfaces.log'])
    artifacts = [out/(corner+'_'+which+'_endpoints.json') for corner in ['min', 'max'] for which in ['extra', 'missing']]
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(p): sha(p) for p in artifacts}, results=results,
        nominal_unique_layer_material_endpoints=len(lookup),
        min_max_support_sets_identical_to_nominal=all(r['endpoint_support_set_identical_to_nominal'] for r in results),
        capacitance_coefficients_equal=False, physical_weights_or_RC_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    status('corner_endpoint_support_comparison_terminal', results=results, release_qualified=False)
    print('Min/max endpoint support comparison:', results)


if __name__ == '__main__':
    main()
