#!/usr/bin/env python3
"""Replace insufficient new metal5 fill with an isolated denser pattern.

Preserves original GDS and every other fill layer. Geometric clearance and
density preflight do not replace native DRC/LVS/density or fill-aware RC.
"""
import argparse
import json
from pathlib import Path
import signal
import sys
import time
import math

import pya

from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save
from stream_candidate_assembly_v5 import TOP,layers,same_cell,texts


def region(layout,top,key):
    index = layers(layout).get(key)
    return pya.Region(top.begin_shapes_rec(index)) if index is not None else pya.Region()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    for name in ('stock','original','original-layout-owner'):parser.add_argument('--'+name,required=True,type=Path)
    args = parser.parse_args()
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('12h fill repair')))
    original_owner=args.original_layout_owner.resolve()
    original_budget=json.loads(original_owner.read_text());left=original_budget['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME);assert left>0
    signal.alarm(max(1,math.floor(left)))
    base = ROOT/'build/timing400/release_001'
    stock=args.stock.resolve();original=args.original.resolve()
    stock_proof=verify(stock/'assessment.json');original_proof=verify(original/'assessment.json')
    assert stock_proof['only_fill_purpose_layers_added'] and stock_proof['all_original_parent_geometry_and_labels_preserved']
    files = [original_owner,Path(__file__).resolve(),Path(sys.executable),
        Path(__file__).with_name('stream_candidate_assembly_v5.py'),
        stock/'assessment.json',stock/'assembly.gds',original/'assessment.json',original/'assembly.gds',
        ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech']
    pins = {str(p):sha(p) for p in files}
    before = pya.Layout();before.read(str(original/'assembly.gds'))
    prior = pya.Layout();prior.read(str(stock/'assembly.gds'))
    after = pya.Layout();after.read(str(stock/'assembly.gds'))
    assert before.dbu == prior.dbu == after.dbu == 0.001
    original_names = {c.name for c in before.each_cell()}
    new_names = {c.name for c in after.each_cell()}-original_names
    fill_index = layers(after)[72,99]
    for cell in after.each_cell():
        if cell.name in new_names:
            cell.shapes(fill_index).clear()
    top = before.cell(TOP)
    metal = pya.Region()
    for datatype in (20,16,5,13,99):
        metal |= region(before,top,(72,datatype))
    forbidden = metal|region(before,top,(72,98))
    for datatype in (20,16,5):
        forbidden |= region(before,top,(76,datatype))
    die = pya.Region(pya.Box(3000,3000,997000,847000))
    allowed = die-forbidden.sized(1600)
    candidates = []
    for offset in (0,2500,5000,7500):
        grid = pya.Region()
        for x in range(-10000+offset,1000000,10000):
            for y in range(-10000+offset,850000,10000):
                grid.insert(pya.Box(x,y,x+8000,y+8000))
        # Opening removes clipped slivers while preserving the original gaps.
        fill = (grid&allowed).sized(-800).sized(800).merged()
        assert (fill-allowed).is_empty()
        assert fill.width_check(1600).is_empty()
        combined = metal|fill
        values = []
        for x in range(0,351000,70000):
            for y in range(0,211000,70000):
                box = pya.Box(x,y,min(x+700000,1000000),min(y+700000,850000))
                values.append((combined&pya.Region(box)).area()/box.area())
        values.append(combined.area()/(1000000*850000))
        candidates.append((min(values),-max(values),offset,fill,values))
    _,_,offset,fill,values = max(candidates,key=lambda row:(row[0],row[1]))
    assert min(values)>=0.45 and max(values)<=0.76, (offset,min(values),max(values))
    helper = after.create_cell('PLL_METAL5_DENSITY_REPAIR')
    assert helper.name not in original_names|new_names
    helper.shapes(fill_index).insert(fill)
    after.cell(TOP).insert(pya.CellInstArray(helper.cell_index(),pya.Trans()))
    for name in ('IntegerPLL_AcquiringCore','IntegerPLL_BBPD',
        'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'):
        same_cell(before,before.cell(name),after,after.cell(name))
    for key in layers(prior).keys()|layers(after).keys():
        if key != (72,99):
            assert (region(prior,prior.cell(TOP),key)^region(after,after.cell(TOP),key)).is_empty(),key
        pi,ai = layers(prior).get(key),layers(after).get(key)
        assert texts(prior.cell(TOP),pi)==texts(after.cell(TOP),ai),key
    expected = region(before,top,(72,99))|fill
    assert (expected^region(after,after.cell(TOP),(72,99))).is_empty()
    for polygon in fill.each():
        assert all(p.x%5==p.y%5==0 for p in polygon.each_point_hull())
    out = args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    save(out/'owner.json',dict(original_owner=str(original_owner),deadline_uptime=original_budget['deadline_uptime'],total_budget_restarted=False))
    after.write(str(out/'assembly.gds'))
    for path,digest in pins.items():assert sha(path)==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},top=TOP,
        all_source_macro_geometry_and_labels_preserved=True,missing_cells=0,
        parent_diode_instances=original_proof['parent_diode_instances'],parent_well_tap_instances=original_proof['parent_well_tap_instances'],
        external_physical_cell_placements_match_plan=original_proof['external_physical_cell_placements_match_plan'],
        all_original_parent_geometry_and_labels_preserved=True,
        only_new_metal5_fill_replaced=True,other_seven_fill_layers_unchanged=True,
        original_metal5_fill_preserved=True,fill_spacing_preflight_nm=1600,
        fill_min_width_preflight_nm=1600,pattern_pitch_nm=10000,pattern_tile_nm=8000,
        selected_offset_nm=offset,geometric_metal5_window_global_densities=values,
        all_added_fill_vertices_on_5nm_grid=True,
        assembled_magic_drc_passed=False,assembled_lvs_passed=False,
        antenna_qualified=False,density_qualified=False,
        previous_parent_rc_matches_filled_geometry=False,
        fill_aware_electrical_extraction_qualified=False,
        physical_signoff_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print(json.dumps(dict(metal5_preflight_min=min(values),metal5_preflight_max=max(values),offset_nm=offset)))


if __name__ == '__main__':
    main()
