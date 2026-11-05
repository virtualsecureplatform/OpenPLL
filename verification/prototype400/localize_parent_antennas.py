#!/usr/bin/env python3
"""Map conservative forming-stage antenna failures to actual macro ports."""
import argparse
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import re
import sys
import pya
from common import ROOT,save,sha,verify
from build_assembly_frame import expected,DCO
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_forming_antenna_geometry_v2 import geometry,engine_at_stage


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('layout','antenna','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    gds=a.layout.resolve()/'assembly.gds';ant=a.antenna.resolve()
    receipt=json.loads((ant/'assessment.json').read_text());verify(receipt['input_sha256']);verify(receipt['artifacts'])
    assert receipt['input_sha256'][str(gds)]==sha(gds)
    failures=[r for r in json.loads((ant/'components.json').read_text()) if r['violation']]
    lefs={'digital':ROOT/'build/timing400/prototype_001/local_antenna_001/digital.lef',
          'oscillator':ROOT/f'openlane/{DCO}/runs/c1fine_range_001/final/lef/{DCO}.lef',
          'detector':ROOT/'build/timing450/interface_characterization/bbpd_sampled/runs/timing450_sampled_v2/final/lef/IntegerPLL_BBPD.lef'}
    offsets=dict(digital=(150000,150000),oscillator=(750000,150000),detector=(750000,400000))
    ports=[];bindings=expected()
    for inst,lef in lefs.items():
        x,y=offsets[inst]
        for pin,body in re.findall(r'^\s*PIN (\S+)\s*$(.*?)^\s*END \1\s*$',lef.read_text(),re.M|re.S):
            layer=None
            for line in body.splitlines():
                f=line.split()
                if f and f[0]=='LAYER':layer=f[1]
                if f and f[0]=='RECT' and re.fullmatch(r'met[1-5]',layer or ''):
                    aa,bb,cc,dd=[Decimal(v)*1000 for v in f[1:5]]
                    ports.append(dict(instance=inst,pin=pin,net=bindings[inst,pin],layer='m'+layer[-1],
                                      point=[int((aa+cc)/2)+x,int((bb+dd)/2)+y]))
    l=pya.Layout();l.read(str(gds));geom=geometry(l,l.cell('IntegerPLL_400MHz_PrototypeTop'))
    result=[]
    for stage in sorted({r['stage'] for r in failures}):
        engine,regs=engine_at_stage(geom,stage);aliases=defaultdict(list)
        for port in ports:
            if port['layer'] not in regs:continue
            net=engine.probe_net(regs[port['layer']],pya.Point(*port['point']))
            if net is not None:aliases[net.cluster_id].append(port)
        for r in failures:
            if r['stage']==stage:result.append(dict(r,macro_ports=aliases[r['cluster']]))
    save(out/'records.json',result)
    nets=sorted({port['net'] for r in result for port in r['macro_ports']})
    paths=[Path(__file__).resolve(),gds,ant/'assessment.json',ant/'components.json',*lefs.values()]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
         artifacts={str(out/'records.json'):sha(out/'records.json')},violations=len(result),
         violations_with_macro_port=sum(bool(r['macro_ports']) for r in result),affected_parent_nets=nets,
         release_qualified=False))
    print(json.dumps(dict(violations=len(result),mapped=sum(bool(r['macro_ports']) for r in result),nets=len(nets))))


if __name__=='__main__':main()
