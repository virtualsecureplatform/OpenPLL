#!/usr/bin/env python3
"""Locate each actual diode diffusion for corner-wrapper warning assessment."""
from collections import Counter
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
    base=ROOT/'build/timing400/release_001'
    final_path=base/'parent_dco_antenna_final_geometry_011/assessment.json'
    final=verify(final_path)
    inventory=base/'current_diode_geometry_inventory_001'
    assert verify(inventory/'assessment.json')['diode_instances']==726
    records=json.loads((inventory/'geometries.json').read_text())
    expected={r['master']:r for r in records}
    gds=Path(final['assembled_gds']);assert sha(gds)==final['assembled_gds_sha256']
    owner_path=base/'candidate_layout_checks_001/owner.json'
    owner=json.loads(owner_path.read_text());left=owner['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left>0;signal.alarm(max(1,math.floor(left)))
    out=base/'corner_diode_warning_geometry_001';assert not out.exists()
    layout=pya.Layout();layout.read(str(gds));assert layout.dbu==.001
    top=layout.cell('IntegerPLL_400MHz_CandidateTop');assert top is not None
    cache={};counts=Counter();diodes=[]
    def walk(cell,tr,path):
        if cell.name in expected:
            if cell.name not in cache:
                active=pya.Region(cell.begin_shapes_rec(layout.layer(65,20))).merged()
                poly=pya.Region(cell.begin_shapes_rec(layout.layer(66,20))).merged()
                polygons=list(active.each())
                assert len(polygons)==1 and polygons[0].is_box() and (active&poly).is_empty(),cell.name
                area=active.area();perimeter=polygons[0].perimeter()
                row=expected[cell.name]
                assert abs(area-float(row['effective_area_um2'])*1e6)<1e-6
                assert abs(perimeter-float(row['effective_perimeter_um'])*1000)<1e-6
                cache[cell.name]=(polygons[0].bbox(),area,int(perimeter))
            box,area,perimeter=cache[cell.name];box=tr*box
            bounds=[box.left,box.bottom,box.right,box.top];assert all(v%5==0 for v in bounds)
            counts[cell.name]+=1
            diodes.append(dict(master=cell.name,placement_path=path,diffusion_box_nm=bounds,
                native_internal_box=[v//5 for v in bounds],diffusion_area_nm2=area,diffusion_perimeter_nm=perimeter))
            return
        for index,inst in enumerate(cell.each_inst()):
            assert inst.na<=1 and inst.nb<=1
            walk(inst.cell,tr*inst.cplx_trans,f'{path}/{index}:{inst.cell.name}')
    walk(top,pya.ICplxTrans(),top.name)
    assert counts==Counter({m:r['instances'] for m,r in expected.items()})
    assert len(diodes)==len({tuple(r['native_internal_box']) for r in diodes})==726
    paths=[Path(__file__).resolve(),Path(sys.executable),final_path,gds,inventory/'assessment.json',inventory/'geometries.json',owner_path]
    out.mkdir()
    save(out/'diodes.json',diodes)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(out/'diodes.json'):sha(out/'diodes.json')},actual_diode_instances=726,
        master_counts=dict(counts),exact_diffusion_area_and_perimeter_match_native_control=True,
        actual_hierarchy_transforms_used=True,coordinate_nm_per_internal_unit=5,
        wrapper_warning_locations_classified=False,model_equivalence_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    print('Located726 actual diode diffusions with exact control area/perimeter; corner diagnostics can now be matched individually.')


if __name__=='__main__':main()
