#!/usr/bin/env python3
"""Check the most remote traced C supports against independent GDS conductors.

This is a location diagnostic, not a capacitor assignment. Edge supports are
sampled on both sides by one nanometre to accommodate boundary conventions.
No nearest resistor node is substituted for a distributed capacitor location.
"""
import heapq
import json
import math
from pathlib import Path
import signal
import sys
import time
import pya
from run_dco_qualification import ROOT, sha, save
from device_aware_conductor_geometry import conductor_geometry
from check_forming_antenna_geometry_v2 import engine_at_stage


def main():
    base = ROOT / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    left = json.loads(owner.read_text())['deadline_uptime'] - time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    supports = base / 'DCO_C_R_support_inventory_001/support_boxes.jsonl'
    terminals = base / 'DCO_intercell_wire_rc_geometry_001/terminals.json'
    labels = {}
    for row in json.loads(terminals.read_text()):
        net = row['logical_net']
        if net is None:
            continue
        assert len(row['clusters']) == 1
        cluster = row['clusters'][0]
        assert net not in labels or labels[net] == cluster
        labels[net] = cluster
    # Keep one worst support per signal conductor; examine the 100 worst nets.
    worst = {}
    with supports.open() as stream:
        for line in stream:
            row = json.loads(line)
            net = row['original_conductor']
            if net not in labels:
                continue
            if net not in worst or row['nearest_representative_padding_nm'] > worst[net]['nearest_representative_padding_nm']:
                worst[net] = row
    selected = heapq.nlargest(100, worst.values(), key=lambda r: r['nearest_representative_padding_nm'])
    topname = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    gds = ROOT / f'openlane/{topname}/runs/c1fine_range_001/final/gds/{topname}.gds'
    assert sha(gds) == '0f227ae41fa996eaa23410aecbe7a3b38090185285c768ba24435026f337a2dd'
    layout = pya.Layout()
    layout.read(str(gds))
    assert layout.dbu == .001
    engine, regs = engine_at_stage(conductor_geometry(layout, layout.cell(topname)), 'm5')
    results = []
    for row in selected:
        l, b, r, t = [v * 5 for v in row['box_internal']]
        hits = []
        for x, y in {(l, b), (r, t), ((l+r)//2, (b+t)//2)}:
            for dx, dy in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                for kind in ['poly', 'diff', 'tap', 'li', 'm1', 'm2', 'm3', 'm4', 'm5']:
                    found = engine.probe_net(regs[kind], pya.Point(x+dx, y+dy))
                    if found is not None:
                        hits.append(dict(point_nm=[x+dx, y+dy], layer=kind, cluster=found.cluster_id))
        expected = labels[row['original_conductor']]
        results.append(dict(**row, expected_GDS_cluster=expected, physical_hits=hits,
                            expected_conductor_found=any(h['cluster'] == expected for h in hits)))
    out = base / 'DCO_remote_C_support_geometry_001'
    out.mkdir(exist_ok=False)
    save(out / 'supports.json', results)
    paths = [Path(__file__).resolve(), Path(sys.executable), owner, supports, terminals, gds,
             Path(__file__).with_name('device_aware_conductor_geometry.py'),
             Path(__file__).with_name('check_forming_antenna_geometry_v2.py')]
    save(out / 'assessment.json', dict(input_sha256={str(p): sha(p) for p in paths},
        artifacts={str(out/'supports.json'): sha(out/'supports.json')},
        signal_conductors_in_inventory=len(worst), remote_supports_checked=len(results),
        expected_GDS_conductor_found=sum(r['expected_conductor_found'] for r in results),
        maximum_R_representative_distance_nm=max(r['nearest_representative_padding_nm'] for r in results),
        C_allocation_or_RC_error_qualified=False, release_qualified=False, adopted=False,
        scope=__doc__))
    print('Remote C supports on expected GDS conductor:', sum(r['expected_conductor_found'] for r in results), '/', len(results), flush=True)


if __name__ == '__main__':
    main()
