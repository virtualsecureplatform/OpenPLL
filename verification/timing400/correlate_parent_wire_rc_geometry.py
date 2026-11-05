#!/usr/bin/env python3
"""Locate current parent SPEF nodes on matching full-GDS conductor components.

SPEF coordinates lack conductor layers. Probe every signal metal at each point
and require the expected logical component among the physical matches. This
correlates coordinates; it does not distribute full-GDS C onto resistor nodes.
"""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import signal
import time
import pya
from audit_current_parent_wire_rc import parse
from check_compact_clock_tree import verify
from check_forming_antenna_geometry_v2 import engine_at_stage
from device_aware_conductor_geometry import conductor_geometry
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    view = base/'parent_filled_poly_metal_capacitance_view_003'
    source = base/'current_parent_wire_rc_001'
    out = base/'current_parent_wire_rc_geometry_001'
    v = verify(view/'assessment.json')
    verify(base/'current_parent_wire_rc_audit_001/assessment.json')
    owner = json.loads((view/'owner.json').read_text())
    left = owner['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1,math.floor(left)))
    out.mkdir(exist_ok=False)
    save(out/'owner.json', dict(runner_pid=__import__('os').getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(), deadline_uptime=owner['deadline_uptime'],
        original_owner=str(view/'owner.json'), total_budget_restarted=False))
    gds = view/'capacitance_view.gds'
    paths = [Path(__file__).resolve(),Path(__file__).with_name('audit_current_parent_wire_rc.py'),
        Path(__file__).with_name('device_aware_conductor_geometry.py'),view/'assessment.json',gds,
        base/'current_parent_wire_rc_audit_001/assessment.json',*[source/f'{c}.spef' for c in ['min','nom','max']]]
    pins = {str(p):sha(p) for p in paths}
    save(out/'input_manifest.json', dict(input_sha256=pins, scope=__doc__))
    layout = pya.Layout()
    layout.read(str(gds))
    assert layout.dbu == .001
    top = layout.cell(v['top'])
    geom = conductor_geometry(layout,top)
    assert geom['gate'].area() == v['mos_gate_area_nm2']
    print('Building resistor-aware full-GDS conductor graph for parent RC coordinates.',flush=True)
    engine,regs = engine_at_stage(geom,'m5')
    labels = {}
    for index in layout.layer_indices():
        info = layout.get_info(index)
        if info.datatype != 5 or not 68 <= info.layer <= 72:
            continue
        kind = 'm'+str(info.layer-67)
        for shape in top.shapes(index).each():
            if shape.is_text():
                text = shape.text
                node = engine.probe_net(regs[kind],pya.Point(text.x,text.y))
                assert node is not None and text.string not in labels
                labels[text.string] = node.cluster_id
    assert len(labels)==len(set(labels.values()))==359
    records = []
    unmatched = []
    for corner in ['min','nom','max']:
        for net,row in parse(source/f'{corner}.spef').items():
            assert net in labels
            for name,xy in row['coordinates'].items():
                point = [round(value*1000) for value in xy]
                matches = []
                for kind in ['li','m1','m2','m3','m4','m5']:
                    node = engine.probe_net(regs[kind],pya.Point(*point))
                    if node is not None:
                        matches.append(dict(layer=kind,cluster=node.cluster_id))
                passed = labels[net] in {m['cluster'] for m in matches}
                result = dict(corner=corner,logical_net=net,spef_node=name,point_nm=point,
                    expected_cluster=labels[net],physical_matches=matches,expected_net_found=passed)
                records.append(result)
                if not passed:
                    unmatched.append(result)
    save(out/'coordinates.json',records)
    save(out/'unmatched.json',unmatched)
    chosen = next(r for r in records if r['expected_net_found'])
    other = next(cluster for name,cluster in labels.items() if name!=chosen['logical_net']
        and cluster not in {m['cluster'] for m in chosen['physical_matches']})
    assert other not in {m['cluster'] for m in chosen['physical_matches']}
    for p,digest in pins.items():
        assert sha(p)==digest,p
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in [out/'coordinates.json',out/'unmatched.json']},
        coordinates_tested=len(records),coordinates_on_expected_net=len(records)-len(unmatched),
        unmatched_coordinates=len(unmatched),all_coordinates_correlated=not unmatched,
        wrong_logical_net_negative_control_rejected=True,expected_net_membership_only=True,
        unique_conductor_layer_identity_qualified=False,distributed_capacitance_assignment_qualified=False,
        full_rc_enclosure_qualified=False,physical_timing_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    print('Parent RC coordinate correlation terminal:',len(records),'points;',len(unmatched),'unmatched.',flush=True)


if __name__ == '__main__':
    main()
