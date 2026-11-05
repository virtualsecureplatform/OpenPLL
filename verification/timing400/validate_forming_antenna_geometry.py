#!/usr/bin/env python3
"""Challenge independent forming-component enumeration with actual HS cells.

Use the same long LI cable and 0/1/2/3 diode placements as the validated native
control. A second separated inverter on the same final net connects only at
M2: its independent LI component must still be enumerated.
"""
import argparse
from pathlib import Path
import sys
import pya
from check_forming_antenna_geometry import check,geometry
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();base=ROOT/'build/timing400/release_001'
    source=base/'compact_internal_antenna_001/signoff/route.gds'
    reference=base/'antenna_diode_style_comparison_001/assessment.json';verify(reference)
    layout=pya.Layout();layout.read(str(source));assert layout.dbu==.001
    inv=layout.cell('sky130_fd_sc_hs__inv_1');diode=layout.cell('sky130_fd_sc_hs__diode_2')
    assert inv is not None and diode is not None
    rows=[]
    for count in range(4):
        top=layout.create_cell('CONTROL_'+str(count))
        top.insert(pya.CellInstArray(inv.cell_index(),pya.Trans()))
        top.shapes(layout.layer(67,20)).insert(pya.Box(-1000000,1300,300,1600))
        for index in range(count):top.insert(pya.CellInstArray(diode.cell_index(),pya.Trans(-4000*(index+1),0)))
        records,coverage=check(geometry(layout,top),['li'])
        long=[r for r in records if r['etch_area_um2']>100]
        assert len(long)==1
        row=long[0];assert abs(row['gate_area_um2']-.279)<1e-12
        assert abs(row['diffusion_area_um2']-count*.6417)<1e-12
        assert row['violation']==(count<3),(count,row)
        rows.append(dict(diode_count=count,**row))
    # Geometry-derived regions with two gates: same final M2 net, distinct LI
    # forming components. The two gated LI clusters must never be collapsed.
    geom=geometry(layout,layout.cell('CONTROL_0'))
    for key in geom:
        if key!='m2':geom[key]+=geom[key].transformed(pya.Trans(0,10000))
    geom['m1']+=pya.Region(pya.Box(0,1300,400,1600))+pya.Region(pya.Box(0,11300,400,11600))
    geom['mcon']+=pya.Region(pya.Box(50,1350,250,1550))+pya.Region(pya.Box(50,11350,250,11550))
    geom['v1']+=pya.Region(pya.Box(50,1350,250,1550))+pya.Region(pya.Box(50,11350,250,11550))
    geom['m2']+=pya.Region(pya.Box(0,1300,400,11600))
    records,coverage=check(geom,['li','m2'])
    early=[r for r in records if r['stage']=='li' and r['etch_area_um2']>100]
    later=[r for r in records if r['stage']=='m2' and r['gate_area_um2']>.5]
    assert len(early)==2 and all(r['violation'] for r in early)
    assert any(abs(r['gate_area_um2']-.558)<1e-12 for r in later)
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    paths=[Path(__file__).resolve(),Path(__file__).with_name('check_forming_antenna_geometry.py'),Path(sys.executable),source,reference]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={},
        native_control_truth_table_reproduced=True,diode_controls=rows,
        final_net_with_two_separate_early_gate_components_detected=True,
        coverage_control=coverage,antenna_qualified=False,release_qualified=False,scope=__doc__))
    print('Actual-cell controls: 0/1/2 diodes fail, 3 pass; two separated forming components remain independently enumerated.')

if __name__=='__main__':main()
