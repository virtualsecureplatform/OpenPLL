#!/usr/bin/env python3
"""Recover exact ordered material metadata for the unresolved signal supports."""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
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
    preceding = base/'DCO_C_single_tile_support_001'
    rows = json.loads((preceding/'supports.json').read_text())
    targets = {(r['original_conductor'], tuple(r['box_internal'])): r for r in rows
               if r['classification'] != 'one_single_tile_voltage_candidate'}
    assert len(targets) == 301
    trace = base/'DCO_C_surface_trace_controls_001/nom_trace'
    mapping = json.loads((trace/'node_ids.json').read_text())
    details = defaultdict(Counter)
    examples = defaultdict(list)
    types, planes = {}, {}
    count = 0
    with (trace/'surfaces.log').open() as auxiliary:
        def next_surface():
            for line in auxiliary:
                if line.startswith('TYPE '):
                    f = shlex.split(line)
                    types[int(f[1])] = f[2]
                elif line.startswith('PLANE '):
                    f = shlex.split(line)
                    planes[int(f[1])] = f[2]
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
                if f[4] != 'box':
                    continue
                endpoints = [(f[1], f[5:9], surface[3:6])]
                reason = f[3]
            else:
                endpoints = [(f[1], f[6:10], surface[3:6]), (f[2], f[10:14], surface[6:9])]
                reason = f[4]
            for ptr, box, material in endpoints:
                key = mapping[ptr], tuple(map(int, box))
                if key not in targets:
                    continue
                plane, raw, effective = map(int, material)
                label = (planes[plane], types[effective], raw, reason)
                details[key][label] += 1
                if len(examples[key]) < 2:
                    examples[key].append(dict(serial=count, contribution=line.strip(), surface=' '.join(surface)))
        assert next_surface() is None
    assert count == 8297230 and details.keys() == targets.keys(), (len(details), len(targets))
    result = []
    materials = Counter()
    for key, row in targets.items():
        groups = [dict(plane=k[0], material=k[1], raw_type=k[2], reason=k[3], events=v)
                  for k, v in sorted(details[key].items())]
        for g in groups:
            materials[g['material']] += 1
        result.append(dict(**row, surface_groups=groups, native_examples=examples[key]))
    out = base/'DCO_unresolved_C_surface_survey_001'
    out.mkdir(exist_ok=False)
    save(out/'supports.json', result)
    paths = [Path(__file__).resolve(), owner, preceding/'assessment.json', preceding/'supports.json',
        trace.parent/'assessment.json', trace/'node_ids.json', trace/'contributions.log', trace/'surfaces.log']
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in paths},
        artifacts={str(out/'supports.json'): sha(out/'supports.json')},
        unresolved_signal_supports=301, all_targets_recovered_with_exact_serial_alignment=True,
        surface_material_group_counts=dict(materials), native_contributions_scanned=count,
        physical_C_attachment_and_weights_qualified=False, runtime_model_eligible=False,
        release_qualified=False, adopted=False))
    print('Unresolved301 signal supports recovered with material metadata:', dict(materials))


if __name__ == '__main__':
    main()
