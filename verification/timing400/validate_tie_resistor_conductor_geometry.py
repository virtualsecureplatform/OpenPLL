#!/usr/bin/env python3
"""Check the resistor-aware topology against actual conb layout and native devices."""
import json
from pathlib import Path
import re
import sys
import pya
from check_forming_antenna_geometry_v2 import geometry,engine_at_stage
from device_aware_conductor_geometry import conductor_geometry
from inventory_current_digital_pin_geometry import lef_masters
from check_compact_mapping import LEF
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001';native=base/'parent_dco_antenna_native_filled_011'
    verify(native/'native_completion.json');core=base/'compact_internal_antenna_001/signoff'
    gds=core/'route.gds';proof=json.loads((core/'assessment.json').read_text());assert sha(gds)==proof['sha256'][str(gds)]
    layout=pya.Layout();layout.read(str(gds));cell=layout.cell('sky130_fd_sc_hs__conb_1');assert cell is not None
    pins=lef_masters(LEF)['sky130_fd_sc_hs__conb_1']['pins']
    def probe(geom):
        engine,regs=engine_at_stage(geom,'m5');result={}
        for name in ['HI','LO','VPWR','VGND']:
            clusters=set()
            for row in pins[name]['rectangles']:
                kind='li' if row['layer']=='li1' else ('m'+row['layer'][-1] if row['layer'].startswith('met') else None)
                if kind is None:continue
                a,b,c,d=row['rect_nm'];node=engine.probe_net(regs[kind],pya.Point((a+c)//2,(b+d)//2));assert node is not None
                clusters.add(node.cluster_id)
            assert len(clusters)==1;(cluster,)=clusters;result[name]=cluster
        return result
    old=probe(geometry(layout,cell));new=probe(conductor_geometry(layout,cell))
    assert old['HI']==old['VPWR'] and old['LO']==old['VGND']
    assert len(set(new.values()))==4
    extracted=native/'extraction/sky130_fd_sc_hs__conb_1.ext';text=extracted.read_text()
    resistors=[line for line in text.splitlines() if line.startswith('device devres ')]
    assert len(resistors)==2 and all('sky130_fd_pr__res_generic_po' in row for row in resistors)
    terms=[set(re.findall(r'"([^"]+)"',row)[1:]) for row in resistors]
    assert {'HI','VPWR'} in terms and {'LO','VGND'} in terms
    tech=ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech';source=tech.read_text()
    assert 'layer POLYSHORT rmp' in source and 'calma 66 15' in source and 'layer rmp POLYSHORT' in source
    out=base/'tie_resistor_geometry_controls_001';out.mkdir(exist_ok=False)
    paths=[Path(__file__).resolve(),Path(sys.executable),Path(__file__).with_name('device_aware_conductor_geometry.py'),
        Path(__file__).with_name('check_forming_antenna_geometry_v2.py'),Path(__file__).with_name('inventory_current_digital_pin_geometry.py'),
        Path(LEF),gds,core/'assessment.json',native/'native_completion.json',extracted,tech]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={},
        old_ideal_conductor_clusters=old,resistor_aware_clusters=new,native_recognized_resistor_devices=resistors,
        hi_vpwr_and_lo_vgnd_separated=True,old_shortcut_control_rejected=True,recognition_matches_installed_pdk=True,
        other_resistor_device_families_not_qualified=True,full_design_topology_qualified=False,physical_timing_qualified=False,release_qualified=False,scope=__doc__))
    print('Tie-cell resistor control matches native two-device extraction:HI,LO,VPWR,VGND are four distinct nets.')

if __name__=='__main__':main()
