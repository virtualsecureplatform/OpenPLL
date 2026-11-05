#!/usr/bin/env python3
"""Prepare an extraction-only flat view with conductive metal fill represented.

The stock fill-purpose control contributes no coupling; the same M5 rectangle
on the drawing purpose contributes a floating capacitive branch. Replace only LI
and M1-M5 fill purposes with their conductor drawing purposes for this diagnostic view.
FOM/poly fill electrical coverage and extraction accuracy remain unqualified.
No manufacturing GDS or routed database is changed.
"""
import argparse
import json
import math
from pathlib import Path
import signal
import sys
import time
import pya
from check_bbpd_repair_identity import design
from check_compact_clock_tree import verify
from run_dco_qualification import sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['stream','route','geometry','control','original-layout-owner','output']:parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args();stream=args.stream.resolve();route=args.route.resolve();geo=args.geometry.resolve();control=args.control.resolve();out=args.output.resolve()
    owner_path=args.original_layout_owner.resolve();owner=json.loads(owner_path.read_text());left=owner['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME);assert left>0
    signal.alarm(max(1,math.floor(left)))
    mapped_control=control.parent/'fill_capacitance_mapped_control_001/assessment.json'
    mapped=verify(mapped_control)
    assert mapped['controls']['dual_purpose']['capacitor_records']==['C0 SIG VSUBS 6.09289f **FLOATING']
    s=verify(stream/'assessment.json');t=verify(geo/'topology/assessment.json');c=verify(control/'assessment.json')
    assert t['complete_port_connectivity_screen_passed']
    observations=c['controls'];assert observations['no_tile']['capacitor_records']==observations['fill_purpose']['capacitor_records']
    assert observations['drawing_purpose']['capacitor_records']!=observations['fill_purpose']['capacitor_records']
    gds=stream/'assembly.gds';assert sha(gds)==s['artifacts'][str(gds)]==t['input_sha256'][str(gds)]
    ports=json.loads((geo/'topology/records.json').read_text());assert not ports['shorts'] and not ports['missing_probes'] and not ports['split_logical_nets']
    representatives={}
    for group in ports['port_groups']:
        assert len({p['net'] for p in group})==1
        for p in group:representatives.setdefault(p['net'],p)
    _,_,nets=design(route/'route.def');assert set(representatives)==set(nets) and len(nets)==359
    before=pya.Layout();before.read(str(gds));assert before.dbu==.001
    top=before.cell('IntegerPLL_400MHz_CandidateTop');assert top is not None
    after=pya.Layout();after.dbu=before.dbu;flat=after.create_cell('IntegerPLL_400MHz_FilledCapView')
    original={};fill_areas={}
    for index in before.layer_indices():
        info=before.get_info(index);key=(info.layer,info.datatype)
        region=pya.Region(top.begin_shapes_rec(index)).merged();original[key]=region
        if not region.is_empty():flat.shapes(after.layer(info)).insert(region)
    for layer in range(67,73):
        fill=original.get((layer,99),pya.Region());flat.shapes(after.layer(layer,99)).clear();flat.shapes(after.layer(layer,20)).insert(fill)
        fill_areas[str(layer)]=fill.area()*1e-6
    for key,region in original.items():
        expected=pya.Region() if 67<=key[0]<=72 and key[1]==99 else region
        if 67<=key[0]<=72 and key[1]==20:expected=region|original.get((key[0],99),pya.Region())
        actual=pya.Region(flat.begin_shapes_rec(after.layer(*key))).merged();assert (actual^expected).is_empty(),key
    for net,port in representatives.items():
        layer=67+int(port['layer'][1:]);x,y=port['point_nm'];assert x%5==0 and y%5==0
        flat.shapes(after.layer(layer,5)).insert(pya.Text(net,pya.Trans(x,y)))
    gate=(original[66,20]&original[65,20]).area()
    assert gate==(pya.Region(flat.begin_shapes_rec(after.layer(66,20)))&pya.Region(flat.begin_shapes_rec(after.layer(65,20)))).area()
    assert not list(flat.each_inst())
    paths=[Path(__file__).resolve(),Path(sys.executable),owner_path,stream/'assessment.json',gds,route/'route.def',
        geo/'topology/assessment.json',geo/'topology/records.json',control/'assessment.json',mapped_control]
    pins={str(p):sha(p) for p in paths};out.mkdir(parents=True,exist_ok=False)
    save(out/'owner.json',dict(original_owner=str(owner_path),deadline_uptime=owner['deadline_uptime'],total_budget_restarted=False))
    target=out/'capacitance_view.gds';after.write(str(target))
    for p,d in pins.items():assert sha(p)==d,p
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        extraction_only_view=True,top=flat.name,source_manufacturing_gds=str(gds),source_manufacturing_gds_sha256=sha(gds),
        hierarchy_flattened_for_capacitance_context=True,all_nonconverted_mask_regions_preserved=True,converted_fill_material_footprints_preserved=True,
        converted_metal_fill_purpose_layers_removed=True,drawing_and_fill_overlays_not_used=True,
        original_texts_omitted=True,unique_parent_net_labels=359,parent_labels_from_complete_physical_topology=True,
        copied_li_and_metal_fill_area_um2=fill_areas,mos_gate_area_nm2=gate,
        fom_poly_fill_area_um2={str(layer):original.get((layer,99),pya.Region()).area()*1e-6 for layer in [65,66]},
        fom_poly_fill_electrical_coverage_qualified=False,capacitance_extraction_qualified=False,
        manufacturing_gds_unchanged=True,release_qualified=False,adopted=False,scope=__doc__))
    print('Prepared extraction-only flat view:359parent labels and LI/M1-M5 conductive fill; electrical validation remains open.')

if __name__=='__main__':main()
