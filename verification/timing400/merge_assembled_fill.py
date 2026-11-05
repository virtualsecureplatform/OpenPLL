#!/usr/bin/env python3
"""Merge isolated PDK fill while proving original assembly geometry preserved.

Adds only the eight PDK fill-purpose layers. This creates an unqualified
candidate; all affected layout and electrical checks remain required.
"""
import argparse
import json
from pathlib import Path
import signal
import sys

import pya

from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save
from stream_candidate_assembly_v5 import TOP, layers, same_cell, texts


def instances(cell):
    return sorted((i.cell.name,i.cplx_trans.to_s(),i.a.to_s(),i.b.to_s(),i.na,i.nb)
                  for i in cell.each_inst())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('fill','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    args = parser.parse_args()
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('12h merge budget')))
    signal.alarm(43200)
    base = ROOT/'build/timing400/release_001'
    fill, out = args.fill.resolve(), args.output.resolve()
    assert not out.exists()
    report = verify(fill/'native_completion.json')
    assert report['exit_code'] == 0 and report['fill_pattern_generated']
    stream = base/'candidate_stream_006'
    original = verify(stream/'assessment.json')
    assert original['all_source_macro_geometry_and_labels_preserved']
    pattern = fill/(TOP+'_fill_pattern.gds.gz')
    files = [Path(__file__).resolve(),Path(sys.executable),
        Path(__file__).with_name('stream_candidate_assembly_v5.py'),
        fill/'native_completion.json',pattern,stream/'assessment.json',stream/'assembly.gds']
    pins = {str(p):sha(p) for p in files}
    before = pya.Layout();before.read(str(stream/'assembly.gds'))
    added = pya.Layout();added.read(str(pattern))
    assembled = pya.Layout();assembled.read(str(stream/'assembly.gds'))
    assert before.dbu == added.dbu == assembled.dbu
    assert len(added.top_cells()) == 1
    filltop = added.top_cells()[0]
    before_names = {c.name for c in before.each_cell()}
    assert before_names.isdisjoint({c.name for c in added.each_cell()})
    allowed = {(n,99) for n in range(65,73)}
    alayers = layers(added)
    regions = {}
    for key,index in alayers.items():
        region = pya.Region(filltop.begin_shapes_rec(index))
        assert not texts(filltop,index), ('unexpected fill labels',key)
        if not region.is_empty():
            assert key in allowed, ('unexpected fill-purpose layer',key)
            regions[key] = region
    assert set(regions) == allowed
    die = pya.Region(pya.Box(0,0,round(1000/before.dbu),round(850/before.dbu)))
    for key,region in regions.items():
        assert (region-die).is_empty(), ('fill outside assembly die',key)
        grid = round(0.005/before.dbu)
        assert grid*before.dbu == 0.005
        for polygon in region.each():
            points = list(polygon.each_point_hull())
            for hole in range(polygon.holes()):
                points.extend(polygon.each_point_hole(hole))
            assert all(p.x%grid == p.y%grid == 0 for p in points), ('off-grid fill',key)
    top = assembled.cell(TOP)
    retained = instances(top)
    helper = assembled.create_cell('PLL_ASSEMBLY_DENSITY_FILL')
    assert helper.name not in before_names
    helper.copy_tree(filltop)
    top.insert(pya.CellInstArray(helper.cell_index(),pya.Trans()))
    out.mkdir(parents=True)
    assembled.write(str(out/'assembly.gds'))
    after = pya.Layout();after.read(str(out/'assembly.gds'))
    assert after.top_cells() == [after.cell(TOP)]
    assert not any(c.is_ghost_cell() for c in after.each_cell())
    assert sorted(row for row in instances(after.cell(TOP)) if row[0]!='PLL_ASSEMBLY_DENSITY_FILL') == retained
    macros = ['IntegerPLL_AcquiringCore','IntegerPLL_BBPD',
        'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160']
    for name in macros:
        same_cell(before,before.cell(name),after,after.cell(name))
    blayers, final_layers = layers(before), layers(after)
    for key in blayers.keys()|final_layers.keys():
        bi,ai = blayers.get(key),final_layers.get(key)
        previous = pya.Region(before.cell(TOP).begin_shapes_rec(bi)) if bi is not None else pya.Region()
        current = pya.Region(after.cell(TOP).begin_shapes_rec(ai)) if ai is not None else pya.Region()
        expected = previous|regions[key] if key in regions else previous
        assert (current^expected).is_empty(), ('assembled geometry mismatch',key)
        assert texts(before.cell(TOP),bi) == texts(after.cell(TOP),ai), ('assembled label mismatch',key)
    for path,digest in pins.items():
        assert sha(path) == digest, path
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},top=TOP,
        all_source_macro_geometry_and_labels_preserved=True,missing_cells=0,
        all_original_parent_geometry_and_labels_preserved=True,
        all_original_top_instances_preserved=True,only_fill_purpose_layers_added=True,
        fill_within_1000x850um_die=True,
        all_added_fill_vertices_on_5nm_grid=True,
        added_fill_area_um2={f'{n}/{d}':region.area()*before.dbu**2 for (n,d),region in regions.items()},
        assembled_magic_drc_passed=False,assembled_lvs_passed=False,
        antenna_qualified=False,density_qualified=False,
        previous_parent_rc_matches_filled_geometry=False,
        fill_aware_electrical_extraction_qualified=False,
        physical_signoff_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Merged fill-only candidate; original macros, wires, labels and placements preserved.')


if __name__ == '__main__':
    main()
