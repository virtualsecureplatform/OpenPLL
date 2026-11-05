#!/usr/bin/env python3
"""Measure remaining dummy-fill overlap with active, implant and well masks.

Geometry observations define the next extraction control; they do not infer
conductivity, substrate impedance or qualify a capacitance enclosure.
"""
import argparse
import json
import math
from pathlib import Path
import signal
import sys
import time
import pya
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();base=ROOT/'build/timing400/release_001';stream=base/'parent_dco_antenna_stream_filled_011';s=verify(stream/'assessment.json')
    owner_path=base/'candidate_layout_checks_001/owner.json';deadline=json.loads(owner_path.read_text())['deadline_uptime'];left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME);assert left>0
    signal.alarm(max(1,math.floor(left)))
    gds=stream/'assembly.gds';assert sha(gds)==s['artifacts'][str(gds)]
    paths=[Path(__file__).resolve(),Path(sys.executable),stream/'assessment.json',gds,owner_path];pins={str(p):sha(p) for p in paths}
    layout=pya.Layout();layout.read(str(gds));assert layout.dbu==.001;top=layout.cell('IntegerPLL_400MHz_CandidateTop')
    names={'active':(65,20),'tap':(65,44),'poly':(66,20),'licon':(66,44),'nwell':(64,20),'deep_nwell':(64,18),
        'nimplant':(93,44),'pimplant':(94,20),'fom_fill':(65,99),'poly_fill':(66,99)}
    regions={name:pya.Region(top.begin_shapes_rec(layout.layer(*key))).merged() for name,key in names.items()}
    records={}
    for kind in ['fom_fill','poly_fill']:
        region=regions[kind]
        records[kind]=dict(area_um2=region.area()*1e-6,polygons=region.count(),
            overlap_area_um2={name:(region&other).area()*1e-6 for name,other in regions.items() if name!=kind})
    metals={}
    for layer in range(67,73):
        fill=pya.Region(top.begin_shapes_rec(layout.layer(layer,99))).merged()
        drawing=pya.Region(top.begin_shapes_rec(layout.layer(layer,20))).merged()
        metals[str(layer)]=dict(fill_area_um2=fill.area()*1e-6,overlap_with_drawing_um2=(fill&drawing).area()*1e-6)
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    for p,d in pins.items():assert sha(p)==d,p
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={},mask_gds_pairs=names,remaining_materials=records,
        li_metal_fill=metals,poly_fill_conversion_has_no_overlap_with_active_tap_or_licon=all(records['poly_fill']['overlap_area_um2'][k]==0 for k in ['active','tap','licon']),
        electrical_material_interpretation_qualified=False,full_capacitance_enclosure_qualified=False,release_qualified=False,scope=__doc__))
    print(json.dumps(records,indent=2),flush=True)

if __name__=='__main__':main()
