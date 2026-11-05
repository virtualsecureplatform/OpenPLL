#!/usr/bin/env python3
"""Enumerate MOS-gated forming components from low-voltage SKY130 drawing GDS.

Diagnostic independent geometry implementation. Register poly/active overlap
as MOS gate area, and active minus poly as diffusion; pure diodes never add
gate area. Enumerate every gated component at every layer stage, including
cut stages before their overlying conductor exists. Do not infer process
qualification until reference controls and device/layer coverage are audited.
"""
import argparse
from pathlib import Path
import signal
import sys
import pya
from run_dco_qualification import sha,save

STAGES=['poly','licon','li','mcon','m1','v1','m2','v2','m3','v3','m4','v4','m5']
# Installed PDK antenna/height rules: ratio, diffusion bonus, diffusion slope,
# sidewall thickness in microns (None means bottom surface area).
RULES={'poly':(50,0,0,.18),'licon':(3,0,0,None),'li':(75,0,450,.10),
       'mcon':(3,0,18,None),'m1':(400,2200,400,.36),'v1':(3,0,18,None),
       'm2':(400,2200,400,.36),'v2':(6,0,36,None),'m3':(400,2200,400,.845),
       'v3':(6,0,36,None),'m4':(400,2200,400,.845),'v4':(6,0,36,None),
       'm5':(400,2200,400,1.26)}


def geometry(layout,top):
    def layer(n,d):return pya.Region(top.begin_shapes_rec(layout.layer(n,d))).merged()
    poly=layer(66,20);active=layer(65,20);tap=layer(65,44)
    # Tap geometry is connected for topology, but receives no diffusion credit:
    # this conservative diagnostic does not assume substrate or well discharge.
    result={'gate':poly&active,'diff':active-poly,'tap':tap,'poly':poly,
            'licon':layer(66,44),'li':layer(67,20),'mcon':layer(67,44)}
    for i in range(1,6):result[f'm{i}']=layer(67+i,20)
    for i in range(1,5):result[f'v{i}']=layer(67+i,44)
    return result


def check(geom,stages=STAGES):
    records=[];coverage=[]
    for stage in stages:
        selected=['gate','diff','tap']+STAGES[:STAGES.index(stage)+1]
        regs={k:geom[k].dup() for k in selected}
        engine=pya.LayoutToNetlist('FLAT',.001)
        for name,region in regs.items():engine.register(region,name);engine.connect(region)
        engine.connect(regs['gate'],regs['poly'])
        if 'licon' in regs:
            for key in ['poly','diff','tap','li']:
                if key in regs:engine.connect(regs[key],regs['licon'])
        for a,b in [('li','mcon'),('mcon','m1')]+[(a,b) for i in range(1,5) for a,b in [(f'm{i}',f'v{i}'),(f'v{i}',f'm{i+1}')]]:
            if a in regs and b in regs:engine.connect(regs[a],regs[b])
        engine.extract_netlist()
        circuit=engine.netlist().top_circuit();gated=0;gate_area=0
        limit,bonus,slope,thickness=RULES[stage]
        for net in circuit.each_net():
            gates=engine.shapes_of_net(net,regs['gate'],True).merged()
            if gates.is_empty():continue
            gated+=1;area=gates.area();gate_area+=area
            diffusion=engine.shapes_of_net(net,regs['diff'],True).merged().area()*1e-6
            conductor=engine.shapes_of_net(net,regs[stage],True).merged()
            etch=conductor.area()*1e-6 if thickness is None else conductor.perimeter()*.001*thickness
            ratio=etch/(area*1e-6)
            allowed=limit+(bonus+slope*diffusion if diffusion>0 else 0)
            records.append(dict(stage=stage,cluster=net.cluster_id,gate_area_um2=area*1e-6,
                diffusion_area_um2=diffusion,etch_area_um2=etch,ratio=ratio,allowed_ratio=allowed,
                violation=ratio>allowed+1e-9,gate_bbox_nm=list(gates.bbox().to_s().replace('(', '').replace(')','').replace(';',',').split(','))))
        assert gate_area==geom['gate'].area(),('gate coverage mismatch',stage,gate_area,geom['gate'].area())
        coverage.append(dict(stage=stage,gated_components=gated,gate_area_nm2=gate_area,
            violations=sum(r['violation'] for r in records if r['stage']==stage)))
        print(coverage[-1],flush=True)
    return records,coverage


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gds',type=Path,required=True)
    parser.add_argument('--top',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();signal.alarm(43200)
    source=args.gds.resolve();out=args.output.resolve();assert not out.exists()
    layout=pya.Layout();layout.read(str(source));assert layout.dbu==.001
    top=layout.cell(args.top);assert top is not None
    records,coverage=check(geometry(layout,top))
    out.mkdir(parents=True)
    save(out/'components.json',records)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [Path(__file__).resolve(),Path(sys.executable),source]},
        artifacts={str(out/'components.json'):sha(out/'components.json')},formation_coverage=coverage,
        all_drawing_mos_gate_area_enumerated_at_each_stage=True,
        violations=sum(r['violation'] for r in records),tap_credit_excluded=True,
        reference_controls_validated=False,antenna_qualified=False,release_qualified=False,scope=__doc__))

if __name__=='__main__':main()
