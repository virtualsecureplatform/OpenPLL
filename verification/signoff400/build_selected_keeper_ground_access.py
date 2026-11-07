"""Add a met1 ground extension to an isolated HS inverter macro view."""
import argparse
from pathlib import Path
import klayout.db as k
from common_v3 import save,sha


def run(lef,gds,output):
    output.mkdir(parents=True,exist_ok=True)
    text=lef.read_text()
    changes={'CLASS CORE ;':'CLASS BLOCK ;','SITE unit ;':'',
        'SIZE  1.440000 BY  3.330000 ;':'SIZE  4.800000 BY  3.330000 ;',
        'RECT 0.000000 -0.245000 1.440000 0.245000 ;':'RECT 0.000000 -0.245000 4.500000 0.245000 ;'}
    for old,new in changes.items():
        if text.count(old)!=1:raise ValueError('unexpected source abstract: '+old)
        text=text.replace(old,new)
    l=k.Layout();l.read(str(gds));name='sky130_fd_sc_hs__inv_2';c=l.cell(name)
    if l.dbu!=0.001:raise ValueError('expected 1 nm DBU')
    li=l.layer(68,20);before=k.Region(c.begin_shapes_rec(li))
    extension=k.Region(k.Box(0,-245,4500,245));c.shapes(li).insert(k.Box(0,-245,4500,245))
    after=k.Region(c.begin_shapes_rec(li));delta=after-before
    if (before-after).area()!=0 or (delta^(extension-before)).area()!=0:raise ValueError('unexpected metal change')
    outlef=output/(name+'.lef');outgds=output/(name+'.gds');outlef.write_text(text);l.write(str(outgds))
    save(output/'ground_access.json',dict(input_sha256={str(p):sha(p)for p in [Path(__file__).resolve(),lef,gds]},
        artifacts={str(p):sha(p)for p in [outlef,outgds]},added_met1_area_um2=delta.area()*l.dbu**2,
        ground_extension_um=[0,-0.245,4.5,0.245],macro_width_um=4.8,
        source_transistors_unchanged=True,new_parasitics_require_extraction=True,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--lef',type=Path,required=True);p.add_argument('--gds',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.lef.resolve(),a.gds.resolve(),a.output.resolve())
