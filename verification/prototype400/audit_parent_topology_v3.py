#!/usr/bin/env python3
"""Check final-GDS macro-port topology against parent logical bindings.

This independent short screen probes every rectangular metal LEF port against
actual GDS connectivity through all conductor stages. Missing probes and split
logical nets are retained. Full native extraction/LVS remains mandatory.
"""
import argparse
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import re
import sys
from klayout_compat import pya
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'timing400'))
from check_bbpd_repair_identity import design
from common import verify as verify_hashes,source_pins
import json
from check_forming_antenna_geometry_v2 import geometry,engine_at_stage
from run_dco_qualification import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['stream','route','frame','output']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();stream=args.stream.resolve();route=args.route.resolve();out=args.output.resolve()
    report=json.loads((stream/'stream_assessment.json').read_text());verify_hashes(report['input_sha256'])
    assert sha(stream/'assembly.gds')==report['assembly_gds_sha256']
    frame=args.frame.resolve();frame_path=frame/'assessment.json'
    selected=json.loads(frame_path.read_text());verify_hashes(selected['input_sha256']);verify_hashes(selected['artifacts'])
    assert selected['assembly_frame_pass']
    assert all(selected['input_sha256'].get(k)==v for k,v in source_pins().items())
    assert report['input_sha256'].get(str(frame_path))==sha(frame_path)
    assert report['input_sha256'].get(str(route/'route.def'))==sha(route/'route.def')
    macros=[(name,Path(view['lef']),tuple(selected['macro_bboxes_dbu'][name][:2]))
            for name,view in selected['macro_sources'].items()]
    _,bindings,_=design(route/'route.def');ports=[]
    for instance,lef,offset in macros:
        for pin,body in re.findall(r'^\s*PIN (\S+)\s*$(.*?)^\s*END \1\s*$',lef.read_text(),re.M|re.S):
            layer=None
            for line in body.splitlines():
                fields=line.split()
                if fields and fields[0]=='LAYER':layer=fields[1]
                if fields and fields[0]=='RECT' and re.fullmatch(r'met[1-5]',layer or ''):
                    a,b,c,d=[Decimal(v)*1000 for v in fields[1:5]]
                    x=(a+c)/2+offset[0];y=(b+d)/2+offset[1]
                    assert int(x)==x and int(y)==y
                    ports.append(dict(instance=instance,pin=pin,net=bindings[(instance,pin)],layer='m'+layer[-1],point_nm=[int(x),int(y)]))
    gds=stream/'assembly.gds';layout=pya.Layout();layout.read(str(gds));assert layout.dbu==.001
    engine,regs=engine_at_stage(geometry(layout,layout.cell('IntegerPLL_400MHz_PrototypeTop')),'m5')
    groups=defaultdict(list);missing=[];logical=defaultdict(set)
    for port in ports:
        net=engine.probe_net(regs[port['layer']],pya.Point(*port['point_nm']))
        if net is None:missing.append(port);continue
        row=dict(port,cluster=net.cluster_id);groups[net.cluster_id].append(row);logical[port['net']].add(net.cluster_id)
    shorts=[dict(cluster=cluster,logical_nets=sorted({p['net'] for p in aliases}),ports=aliases)
        for cluster,aliases in groups.items() if len({p['net'] for p in aliases})>1]
    splits={net:sorted(ids) for net,ids in logical.items() if len(ids)>1}
    out.mkdir(parents=True,exist_ok=False)
    save(out/'records.json',dict(port_groups=list(groups.values()),missing_probes=missing,shorts=shorts,split_logical_nets=splits))
    paths=[Path(__file__).resolve(),Path(sys.executable),ROOT/'verification/timing400/check_forming_antenna_geometry_v2.py',
        route/'route.def',stream/'stream_assessment.json',gds,frame_path,Path(__file__).with_name('klayout_compat.py'),Path(sys.modules[pya.Layout.__module__].__file__),*[m[1] for m in macros]]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={str(out/'records.json'):sha(out/'records.json')},
        rectangular_macro_port_probes=len(ports),missing_probes=len(missing),distinct_logical_nets_shorted=len(shorts),
        split_logical_nets=len(splits),all_probed_logical_nets_distinct=not shorts,
        complete_port_connectivity_screen_passed=not(shorts or missing or splits),
        native_lvs_required=True,release_qualified=False,adopted=False,scope=__doc__))
    print(dict(probes=len(ports),missing=len(missing),shorts=[r['logical_nets'] for r in shorts],split_logical_nets=splits),flush=True)

if __name__=='__main__':main()
