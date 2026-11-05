#!/usr/bin/env python3
"""Compare every native MOS junction share with independent GDS diffusion.

Recover the152 missing decap source regions from the checked candidate. Compare
integer geometry before SPICE output rounding. Charge/impedance remain separate.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shlex
import signal
import time
import pya
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    left = deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    candidate = base/'DCO_local_decap_junction_candidate_001/assessment.json'
    assert verify(candidate)['corrected_rail_junction_area_perimeter_exactly_matches_native_inventory']
    device_path = candidate.parent/'device_connections_candidate.json'
    devices = json.loads(device_path.read_text())
    node_path = base/'DCO_private_R_primitives_001/nodes.json'
    nodes = {r['private_id']: r for r in json.loads(node_path.read_text())}
    recovered_path = candidate.parent/'local_junction_regions.json'
    recovered = {r['device']: r['source'] for r in json.loads(recovered_path.read_text())}
    topname = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    ext = base/'DCO_R_binding_trace_controls_001/trace'/(topname+'.ext')
    raw = {}
    for line in ext.open():
        if line.startswith('device msubckt '):
            f = shlex.split(line)
            raw[f[2], int(f[3]), int(f[4])] = f[-10:]
    gds = ROOT/'openlane'/topname/'runs/c1fine_range_001/final/gds'/(topname+'.gds')
    layout = pya.Layout()
    layout.read(str(gds))
    assert layout.dbu == .001
    top = layout.cell(topname)
    def region(layer, datatype):
        return pya.Region(top.begin_shapes_rec(layout.layer(layer, datatype))).merged()
    active, poly, nw = region(65, 20), region(66, 20), region(64, 20)
    diffusion = (active-poly).merged()
    masks = {'sky130_fd_pr__nfet_01v8': pya.Region(top.bbox())-nw,
             'sky130_fd_pr__pfet_01v8_hvt': nw}
    bins = defaultdict(lambda: defaultdict(set))
    polygons, shares = {}, defaultdict(list)
    grid = 1000  # nm; indexing only, no geometry rounding.
    totals = {}
    for model, mask in masks.items():
        physical = (diffusion & mask).merged()
        totals[model] = dict(GDS_area_nm2=physical.area(), GDS_perimeter_nm=physical.perimeter())
        for number, polygon in enumerate(physical.each_merged()):
            key = model, number
            polygons[key] = polygon
            box = polygon.bbox()
            for x in range((box.left-1)//grid, (box.right+1)//grid+1):
                for y in range((box.bottom-1)//grid, (box.top+1)//grid+1):
                    bins[model][x, y].add(key)
    out = base/'DCO_all_junction_region_audit_001'
    out.mkdir(exist_ok=False)
    save(out/'status.json', dict(state='checking_all_source_drain_GDS_regions', runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(), deadline_uptime=deadline))
    rows, unresolved = [], []
    for name, device in devices.items():
        model = device['model']
        if model not in masks:
            continue
        tail = raw[model, *device['rectangle_internal'][:2]]
        for code, off in [(2, 4), (3, 7)]:
            private = device['private_terminals'][device['native_terminal_codes'].index(code)]
            x, y = [v*5 for v in nodes[private]['point_internal']]
            probe = pya.Region(pya.Box(x-1, y-1, x+1, y+1))
            hits = [k for k in bins[model].get((x//grid, y//grid), [])
                    if not (pya.Region(polygons[k]) & probe).is_empty()]
            if code == 2 and name in recovered:
                ap = [recovered[name]['area_internal'], recovered[name]['perimeter_internal']]
                origin = 'independent_GDS_recovered_missing_source'
                assert tail[off+2] == '0'
            else:
                assert ',' in tail[off+2]
                ap = list(map(int, tail[off+2].split(',')))
                origin = 'native_explicit_local_area_perimeter'
            row = dict(device=name, model=model, native_terminal_code=code, private_node=private,
                point_nm=[x, y], local_area_perimeter_internal=ap, origin=origin,
                GDS_region_numbers=[k[1] for k in hits])
            rows.append(row)
            if len(hits) == 1:
                shares[hits[0]].append(row)
            else:
                unresolved.append(row)
    mismatches = []
    region_rows = []
    for key, polygon in polygons.items():
        terminals = shares[key]
        area, perimeter = polygon.area(), polygon.perimeter()
        assert area % 25 == 0 and perimeter % 5 == 0
        # The native extractor divides each connected diffusion region equally
        # among its owning devices, with integer truncation before output.
        expected = [area//25//len(terminals), perimeter//5//len(terminals)] if terminals else None
        for row in terminals:
            if row['local_area_perimeter_internal'] != expected:
                mismatches.append(dict(**row, expected_equal_share_internal=expected,
                    owners=len(terminals), physical_region_nm=polygon.to_s()))
        region_rows.append(dict(model=key[0], region_number=key[1], polygon_nm=polygon.to_s(),
            area_nm2=area, perimeter_nm=perimeter, terminal_shares=len(terminals),
            devices=[r['device'] for r in terminals], expected_equal_share_internal=expected))
    for model in masks:
        selected = [r for r in rows if r['model'] == model]
        totals[model].update(native_or_recovered_area_nm2=sum(r['local_area_perimeter_internal'][0]*25 for r in selected),
            native_or_recovered_perimeter_nm=sum(r['local_area_perimeter_internal'][1]*5 for r in selected),
            terminal_records=len(selected))
    total_match = all(v['GDS_area_nm2'] == v['native_or_recovered_area_nm2'] and
                      v['GDS_perimeter_nm'] == v['native_or_recovered_perimeter_nm'] for v in totals.values())
    assert len(rows) == 17236 and len(polygons) == 10386 and total_match
    orphan = [r for r in region_rows if not r['terminal_shares']]
    save(out/'terminal_regions.json', rows)
    save(out/'physical_diffusion_regions.json', region_rows)
    save(out/'unresolved_and_mismatched.json', dict(unresolved=unresolved, mismatches=mismatches, unowned_physical_regions=orphan))
    inputs = [Path(__file__).resolve(), owner, candidate, device_path, node_path, recovered_path, ext, gds]
    artifacts = [out/'terminal_regions.json', out/'physical_diffusion_regions.json', out/'unresolved_and_mismatched.json']
    passed = not (unresolved or mismatches or orphan)
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(p): sha(p) for p in artifacts}, native_MOS_devices=8618, junction_terminal_records=len(rows),
        physical_diffusion_regions=len(polygons), totals_by_model=totals,
        total_junction_area_perimeter_exact_GDS_conservation_passed=total_match,
        unlocated_or_ambiguous_terminals=len(unresolved), local_share_mismatches=len(mismatches),
        unowned_physical_diffusion_regions=len(orphan), all_local_junction_region_shares_match_GDS=passed,
        nonlinear_charge_spatial_weights_bulk_impedance_or_transient_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    save(out/'status.json', dict(state='all_junction_region_audit_terminal', runner_pid=os.getpid(),
        all_local_region_shares_passed=passed, release_qualified=False))
    print('All junction geometry: total exact;', len(rows), 'terminals;', len(unresolved), 'unlocated;',
          len(mismatches), 'share mismatches;', len(orphan), 'unowned regions')


if __name__ == '__main__':
    main()
