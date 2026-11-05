#!/usr/bin/env python3
"""Associate independently failing forming components with exact macro ports.

Use actual GDS topology at each failing conductor stage, not overlapping gate
bounding boxes. A port alias is reported only when its physical metal probe
shares the gated component. This is repair localization, not qualification.
"""
import argparse
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import re
import sys
import pya
from check_forming_antenna_geometry_v2 import engine_at_stage,geometry
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save
from check_bbpd_repair_identity import design


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['stream','route','geometry','output']:parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args();base=ROOT/'build/timing400/release_001'
    stream,route,observations,out=[getattr(args,k).resolve() for k in ['stream','route','geometry','output']]
    verify(stream/'assessment.json');proof=verify(observations/'assessment.json')
    assert proof['contact_surface_allowance_factor']==2
    records=json.loads((observations/'components.json').read_text());bad=[r for r in records if r['violation']]
    dco='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    macros=[('digital',base/'digital_macro_abstract_001/IntegerPLL_AcquiringCore.lef',(150000,150000)),
        ('oscillator',ROOT/f'openlane/{dco}/runs/c1fine_range_001/final/lef/{dco}.lef',(750000,150000)),
        ('detector',ROOT/'build/timing450/interface_characterization/bbpd_sampled/runs/timing450_sampled_v2/final/lef/IntegerPLL_BBPD.lef',(750000,400000))]
    _,bindings,_=design(route/'route.def');ports=[]
    for instance,lef,offset in macros:
        for pin,body in re.findall(r'^\s*PIN (\S+)\s*$(.*?)^\s*END \1\s*$',lef.read_text(),re.M|re.S):
            layer=None
            for line in body.splitlines():
                f=line.split()
                if f and f[0]=='LAYER':layer=f[1]
                if f and f[0]=='RECT' and re.fullmatch(r'met[1-5]',layer or ''):
                    coords=[Decimal(x)*1000 for x in f[1:5]]
                    x=(coords[0]+coords[2])/2+offset[0];y=(coords[1]+coords[3])/2+offset[1]
                    assert int(x)==x and int(y)==y
                    net=bindings.get((instance,pin))
                    assert net is not None,(instance,pin)
                    ports.append(dict(instance=instance,pin=pin,net=net,layer='m'+layer[-1],point=(int(x),int(y))))
    layout=pya.Layout();gds=stream/'assembly.gds';layout.read(str(gds));geom=geometry(layout,layout.cell('IntegerPLL_400MHz_CandidateTop'))
    localized=[]
    for stage in sorted({r['stage'] for r in bad}):
        engine,regs=engine_at_stage(geom,stage);clusters=defaultdict(list)
        for port in ports:
            if port['layer'] not in regs:continue
            net=engine.probe_net(regs[port['layer']],pya.Point(*port['point']))
            if net is not None:clusters[net.cluster_id].append(port)
        for row in [r for r in bad if r['stage']==stage]:
            aliases=clusters[row['cluster']];nets=sorted({a['net'] for a in aliases})
            assert len(nets)<=1,('physical component includes distinct logical nets',row,nets)
            localized.append(dict(**row,macro_port_aliases=aliases,logical_nets=nets))
    paths=[Path(__file__).resolve(),Path(sys.executable),Path(__file__).with_name('check_forming_antenna_geometry_v2.py'),
        stream/'assessment.json',route/'route.def',observations/'assessment.json',observations/'components.json',gds,*[m[1] for m in macros]]
    out.mkdir(parents=True,exist_ok=False);save(out/'records.json',localized)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={str(out/'records.json'):sha(out/'records.json')},
        violating_components=len(bad),components_with_unique_logical_net=sum(len(r['logical_nets'])==1 for r in localized),
        physical_macro_ports_traced=True,antenna_qualified=False,release_qualified=False,scope=__doc__))
    for row in localized:print(row['stage'],row['logical_nets'],round(row['ratio'],3),round(row['allowed_ratio'],3),row['diffusion_area_um2'])

if __name__=='__main__':main()
