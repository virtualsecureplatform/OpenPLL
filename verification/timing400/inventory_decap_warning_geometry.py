#!/usr/bin/env python3
"""Locate every known decap gate in the actual final manufacturing GDS.

Prepare exact expected feedback boxes for per-warning assessment of the flat
extraction. Count agreement alone does not classify a warning as harmless.
"""
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import signal
import sys
import time
import pya
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    final_path = base/'parent_dco_antenna_final_geometry_011/assessment.json'
    final = verify(final_path)
    device_path = base/'parent_filled_extraction_device_audit_002/assessment.json'
    device = json.loads(device_path.read_text())
    expected_counts = device['decap_cell_counts']
    gds = Path(final['assembled_gds'])
    assert sha(gds)==final['assembled_gds_sha256']
    owner_path = base/'candidate_layout_checks_001/owner.json'
    owner = json.loads(owner_path.read_text())
    left = owner['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1,math.floor(left)))
    out = base/'flat_decap_warning_gate_inventory_001'
    assert not out.exists()
    paths = [Path(__file__).resolve(),Path(sys.executable),final_path,device_path,gds,owner_path]
    pins = {str(p):sha(p) for p in paths}
    layout = pya.Layout()
    layout.read(str(gds))
    assert layout.dbu==.001
    top = layout.cell('IntegerPLL_400MHz_CandidateTop')
    assert top is not None
    gate_cache = {}
    counts = Counter()
    records = []

    def walk(cell, transform, path):
        if cell.name in expected_counts:
            if cell.name not in gate_cache:
                gate = (pya.Region(cell.begin_shapes_rec(layout.layer(65,20))) &
                    pya.Region(cell.begin_shapes_rec(layout.layer(66,20)))).merged()
                polys = list(gate.each())
                assert len(polys)==2 and all(p.is_box() for p in polys),cell.name
                well = pya.Region(cell.begin_shapes_rec(layout.layer(64,20))).merged()
                gate_cache[cell.name] = []
                for polygon in polys:
                    overlap = (pya.Region(polygon)&well).area()
                    assert overlap in [0,polygon.area()]
                    rail = 'VPWR' if overlap else 'VGND'
                    gate_cache[cell.name].append((polygon.bbox(),rail))
            counts[cell.name]+=1
            for local_box,rail in gate_cache[cell.name]:
                box = transform*local_box
                coords = [box.left,box.bottom,box.right,box.top]
                assert all(v%5==0 for v in coords)
                records.append(dict(master=cell.name,placement_path=path,gate_box_nm=coords,
                    expected_missing_terminal_rail=rail,rail_from_actual_well_overlap=True,
                    expected_magic_box=[v//5 for v in coords]))
            return
        for index,inst in enumerate(cell.each_inst()):
            assert inst.na<=1 and inst.nb<=1,'unexpected GDS array instance'
            walk(inst.cell,transform*inst.cplx_trans,f'{path}/{index}:{inst.cell.name}')

    walk(top,pya.ICplxTrans(),top.name)
    assert dict(counts)==expected_counts,(counts,expected_counts)
    assert len(records)==2*sum(counts.values())==2288
    keys = [tuple(row['expected_magic_box']) for row in records]
    assert len(set(keys))==len(keys)
    for p,digest in pins.items():
        assert sha(p)==digest,p
    out.mkdir()
    save(out/'gates.json',records)
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(out/'gates.json'):sha(out/'gates.json')},
        decap_cell_counts=dict(counts),decap_instances=sum(counts.values()),
        exact_gds_gate_boxes=len(records),unique_expected_magic_boxes=len(set(keys)),
        actual_gds_hierarchy_transforms_used=True,magic_coordinate_nm_per_unit=5,
        full_flat_extraction_feedback_assessed=False,warnings_classified_by_count_alone=False,
        device_terminal_connection_qualified=False,full_electrical_model_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    print('Located2288 individual decap gates in1144 actual GDS placements; full-feedback classification remains pending.')


if __name__=='__main__':
    main()
