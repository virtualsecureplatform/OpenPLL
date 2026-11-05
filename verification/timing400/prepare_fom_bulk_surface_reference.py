#!/usr/bin/env python3
"""Prepare an ideal bulk-surface reference for the remaining FOM fill footprint.

Use ohmic tap types as counterfactual electrical reference surfaces, separated
by actual nwell membership. Added TAP/implant purposes exist only in this view.
They are not manufacturing masks or a qualified model of dummy FOM material.
No finite bulk impedance or quantitative process enclosure is inferred.
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
    base=ROOT/'build/timing400/release_001'
    source=base/'parent_filled_poly_metal_capacitance_view_003'
    out=base/'fom_bulk_surface_reference_view_004'
    v=verify(source/'assessment.json')
    controls_path=base/'lower_fill_capacitance_controls_001/assessment.json'
    controls=verify(controls_path)['cases']
    node_control=base/'lower_fill_control_node_audit_001/assessment.json'
    node_result=json.loads(node_control.read_text())
    assert node_result['ohmic_p_tap_auto_name_is_substrate_not_floating']
    # This source-audit receipt declares inputs only, with no artifacts field.
    for path,digest in node_result['input_sha256'].items():
        assert sha(Path(path))==digest,path
    for case in ['ohmic_p_tap','nwell_ohmic_n_tap']:
        assert controls[case]['native_exit_code']==0 and not controls[case]['active_device_records']
        assert controls[case]['feedback']==''
    owner=json.loads((source/'owner.json').read_text())
    left=owner['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left>0
    signal.alarm(max(1,math.floor(left)))
    gds=source/'capacitance_view.gds'
    layout=pya.Layout()
    layout.read(str(gds))
    assert layout.dbu==.001
    top=layout.cell(v['top'])
    assert top is not None and not list(top.each_inst())
    original={}
    for index in layout.layer_indices():
        info=layout.get_info(index)
        original[info.layer,info.datatype]=pya.Region(top.begin_shapes_rec(index)).merged()
    fom=original[65,99]
    assert not fom.is_empty()
    overlap={}
    for key in [(65,20),(65,44),(66,20),(66,44),(93,44),(94,20)]:
        overlap[str(key)]=(fom&original.get(key,pya.Region())).area()
    assert not any(overlap.values()),overlap
    nwell=original[64,20]
    n_surface=(fom&nwell).merged()
    p_surface=(fom-nwell).merged()
    assert (n_surface&p_surface).is_empty() and ((n_surface|p_surface)^fom).is_empty()
    replacements={(65,99):pya.Region(),(65,44):original[65,44]|fom,
        (93,44):original[93,44]|n_surface,(94,20):original[94,20]|p_surface}
    for key,region in replacements.items():
        top.shapes(layout.layer(*key)).clear()
        top.shapes(layout.layer(*key)).insert(region)
    for key,region in original.items():
        actual=pya.Region(top.begin_shapes_rec(layout.layer(*key))).merged()
        assert (actual^replacements.get(key,region)).is_empty(),key
    # TAP reference surfaces also must not create a poly crossing or contact.
    assert (fom&original[66,20]).is_empty() and (fom&original[66,44]).is_empty()
    gate=(original[65,20]&original[66,20]).area()
    assert gate==v['mos_gate_area_nm2']
    paths=[Path(__file__).resolve(),Path(sys.executable),source/'assessment.json',source/'owner.json',gds,
        controls_path,node_control]
    pins={str(p):sha(p) for p in paths}
    out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(source/'owner.json'),deadline_uptime=owner['deadline_uptime'],total_budget_restarted=False))
    target=out/'capacitance_view.gds'
    layout.write(str(target))
    for path,digest in pins.items():
        assert sha(path)==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},top=top.name,
        extraction_only_view=True,unique_parent_net_labels=359,manufacturing_gds_unchanged=True,
        source_manufacturing_gds=v['source_manufacturing_gds'],source_manufacturing_gds_sha256=v['source_manufacturing_gds_sha256'],
        converted_metal_fill_purpose_layers_removed=True,converted_poly_fill_purpose_removed=True,
        converted_fill_material_footprints_preserved=True,drawing_and_fill_overlays_not_used=True,
        no_added_gate_contact_or_resistor_overlap=True,mos_gate_area_nm2=gate,
        fom_ideal_bulk_reference_only=True,fom_fill_purpose_removed_in_reference=True,
        added_reference_mask_purposes=[[65,44],[93,44],[94,20]],
        reference_fom_footprint_area_um2=fom.area()*1e-6,
        nwell_reference_surface_area_um2=n_surface.area()*1e-6,
        pwell_reference_surface_area_um2=p_surface.area()*1e-6,
        reference_overlap_with_original_devices_or_implants_nm2=overlap,
        all_nonreference_mask_regions_preserved=True,reference_ohmic_surfaces_are_manufacturing_masks=False,
        finite_bulk_impedance_included=False,actual_fom_electrical_material_qualified=False,
        quantitative_upper_or_lower_enclosure_qualified=False,
        full_electrical_model_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Prepared counterfactual bulk-surface reference; original manufacturing masks unchanged; no material/enclosure claim.')


if __name__=='__main__':
    main()
