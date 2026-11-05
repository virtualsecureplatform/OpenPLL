#!/usr/bin/env python3
"""Add isolated conductive poly fill to the existing metal-fill diagnostic view.

This is an extraction experiment. FOM/substrate material and process enclosure
remain unqualified; no manufacturing geometry or adopted model is modified.
"""
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
    base = ROOT / 'build/timing400/release_001'
    source = base / 'parent_filled_metal_capacitance_view_002'
    out = base / 'parent_filled_poly_metal_capacitance_view_003'
    receipt = verify(source / 'assessment.json')
    controls_path = base / 'lower_fill_capacitance_controls_001/assessment.json'
    controls = verify(controls_path)['cases']
    assert not controls['poly_drawing']['active_device_records']
    assert controls['poly_drawing']['feedback'] == ''
    assert controls['poly_drawing']['capacitor_records'] != controls['poly_fill']['capacitor_records']
    owner = json.loads((source / 'owner.json').read_text())
    remaining = owner['deadline_uptime'] - time.clock_gettime(time.CLOCK_BOOTTIME)
    assert remaining > 0
    signal.alarm(max(1, math.floor(remaining)))
    gds = source / 'capacitance_view.gds'
    layout = pya.Layout()
    layout.read(str(gds))
    assert layout.dbu == .001
    top = layout.cell(receipt['top'])
    assert top is not None and not list(top.each_inst())
    poly_fill = pya.Region(top.begin_shapes_rec(layout.layer(66, 99))).merged()
    assert not poly_fill.is_empty()
    # Prevent new MOS gates, contacts, resistor geometry or connection to
    # existing poly. Validate actual geometry, not just conservation of area.
    overlap = {}
    for key in [(65,20), (65,44), (66,20), (66,44), (66,13), (66,15)]:
        overlap[str(key)] = (poly_fill & pya.Region(top.begin_shapes_rec(layout.layer(*key)))).area()
    assert not any(overlap.values()), overlap
    original = {i: pya.Region(top.begin_shapes_rec(i)).merged() for i in layout.layer_indices()}
    gate = (original[layout.layer(66,20)] & original[layout.layer(65,20)]).area()
    assert gate == receipt['mos_gate_area_nm2']
    top.shapes(layout.layer(66,99)).clear()
    top.shapes(layout.layer(66,20)).insert(poly_fill)
    for index, region in original.items():
        info = layout.get_info(index)
        key = (info.layer, info.datatype)
        expected = pya.Region() if key == (66,99) else region
        if key == (66,20):
            expected = region | poly_fill
        actual = pya.Region(top.begin_shapes_rec(index)).merged()
        assert (actual ^ expected).is_empty(), key
    new_gate = (pya.Region(top.begin_shapes_rec(layout.layer(66,20))) & original[layout.layer(65,20)]).area()
    assert gate == new_gate
    paths = [Path(__file__).resolve(), Path(sys.executable), source/'assessment.json',
        source/'owner.json', gds, controls_path]
    pins = {str(p): sha(p) for p in paths}
    out.mkdir(exist_ok=False)
    save(out/'owner.json', dict(started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(source/'owner.json'), deadline_uptime=owner['deadline_uptime'], total_budget_restarted=False))
    target = out/'capacitance_view.gds'
    layout.write(str(target))
    for p, digest in pins.items():
        assert sha(p) == digest
    save(out/'assessment.json', dict(input_sha256=pins,
        artifacts={str(p): sha(p) for p in out.iterdir() if p.is_file()},
        top=top.name, extraction_only_view=True, unique_parent_net_labels=359,
        converted_metal_fill_purpose_layers_removed=True, converted_poly_fill_purpose_removed=True,
        converted_fill_material_footprints_preserved=True, drawing_and_fill_overlays_not_used=True,
        all_other_mask_regions_preserved=True, manufacturing_gds_unchanged=True,
        source_manufacturing_gds=receipt['source_manufacturing_gds'],
        source_manufacturing_gds_sha256=receipt['source_manufacturing_gds_sha256'],
        poly_fill_area_um2=poly_fill.area()*1e-6, poly_fill_forbidden_overlap_nm2=overlap,
        mos_gate_area_nm2=gate, no_added_gate_contact_or_resistor_overlap=True,
        fom_substrate_coverage_qualified=False, capacitance_extraction_qualified=False,
        release_qualified=False, adopted=False, scope=__doc__))
    print('Prepared poly+metal diagnostic view; no added gate/contact/resistor overlap, original deadline retained.')


if __name__ == '__main__':
    main()
