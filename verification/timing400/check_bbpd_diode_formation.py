#!/usr/bin/env python3
"""Check the two repaired detector gates reach distinct physical diodes at M2.

This establishes topology for the two known intermediate-stage defects.
It does not measure every forming component's antenna ratio or analog load.
"""
import argparse
from pathlib import Path
import sys
import pya
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    base=ROOT/'build/timing400/release_001'
    route=base/'bbpd_internal_antenna_001'
    proof=verify(route/'signoff/assessment.json')
    verify(base/'bbpd_internal_antenna_identity_001/assessment.json')
    gds=route/'signoff/route.gds'
    layout=pya.Layout();layout.read(str(gds));assert layout.dbu==.001
    top=layout.cell('IntegerPLL_BBPD')
    def layer(n,d):return pya.Region(top.begin_shapes_rec(layout.layer(n,d))).merged()
    assert layer(235,4).bbox()==pya.Box(0,0,120000,120000)
    poly=layer(66,20)
    geom={'poly':poly,'diff':layer(65,20)-poly,'tap':layer(65,44),
          'licon':layer(66,44),'li':layer(67,20),'mcon':layer(67,44),
          'm1':layer(68,20),'v1':layer(68,44),'m2':layer(69,20)}
    engine=pya.LayoutToNetlist('FLAT',.001)
    for name,reg in geom.items():engine.register(reg,name);engine.connect(reg)
    for name in ('poly','diff','tap','li'):engine.connect(geom[name],geom['licon'])
    for a,b in [('li','mcon'),('mcon','m1'),('m1','v1'),('v1','m2')]:engine.connect(geom[a],geom[b])
    engine.extract_netlist()
    def probe(name,point):
        net=engine.probe_net(geom[name],pya.Point(*point))
        assert net is not None,(name,point)
        return net.cluster_id
    # Physical diode is R0 at (49220,y); point comes from actual extracted
    # ndiode diffusion (31,39) in 5nm units, rather than LEF gate-area metadata.
    gates={'REF':(51990,54845),'CLKDIVR':(52765,60285)}
    diodes={'REF':(49377,54597),'CLKDIVR':(49377,60037)}
    records=[]
    for name in gates:
        gate=probe('poly',gates[name]);diode=probe('diff',diodes[name])
        other=probe('diff',diodes[next(n for n in gates if n!=name)])
        assert gate==diode and gate!=other,(name,gate,diode,other)
        records.append(dict(net=name,formation_layer='metal2',gate_point_nm=gates[name],
                            diode_diffusion_point_nm=diodes[name],connected=True,wrong_diode_rejected=True))
    # Audit actual HD diode active geometry, independent of extraction parameters.
    cell=layout.cell('sky130_fd_sc_hd__diode_2')
    active=pya.Region(cell.begin_shapes_rec(layout.layer(65,20))).merged()
    assert active.area()==434700 and active.perimeter()==2640,(active.area(),active.perimeter())
    native=base/'bbpd_internal_antenna_mos_check_001/native_completion.json'
    n=verify(native);assert n['exit_code']==0
    feedback=base/'bbpd_internal_antenna_mos_check_001/antenna_feedback.txt'
    assert not feedback.read_text().strip()
    paths=[Path(__file__).resolve(),Path(sys.executable),gds,route/'signoff/assessment.json',
           base/'bbpd_internal_antenna_identity_001/assessment.json',native,feedback]
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={},
        boundary_nm=[0,0,120000,120000],local_gate_diode_records=records,
        actual_hd_diode_area_um2=.4347,actual_hd_diode_perimeter_um=2.64,
        mos_only_native_feedback_rectangles=0,all_forming_subnetwork_ratios_checked=False,
        analog_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Both repaired gates reach their own physical diode at M2; wrong diodes rejected. HD diode area/perimeter verified.')

if __name__=='__main__':main()
