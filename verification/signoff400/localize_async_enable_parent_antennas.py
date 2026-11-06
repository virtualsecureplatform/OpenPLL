#!/usr/bin/env python3
"""Map native antenna gates through actual geometry to all parent macro ports."""
import argparse
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'verification/prototype400'))
from klayout_compat import pya
import signal
from common_v3 import ROOT,save,sha,verify
from build_assembly_frame import expected,DCO
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_forming_antenna_geometry_v2 import geometry,engine_at_stage


def main():
    def exhausted(*_):raise TimeoutError('antenna localization exceeded whole-check budget')
    signal.signal(signal.SIGALRM,exhausted);signal.alarm(43200)
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('layout','antenna','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--frame',type=Path,required=True)
    p.add_argument('--route',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    gds=a.layout.resolve()/'assembly.gds';ant=a.antenna.resolve()
    receipt=json.loads((ant/'assessment.json').read_text());verify(receipt['input_sha256']);verify(receipt['artifacts'])
    assert receipt['input_sha256'][str(gds)]==sha(gds)
    assert receipt['native_flat_layout_antenna_run_completed']
    log=ant/'magic.log'
    pattern=r'Antenna violation detected at plane (\w+)\nEffective antenna ratio ([0-9.eE+-]+) > limit ([0-9.eE+-]+)\nGate rect \((-?\d+) (-?\d+)\) to \((-?\d+) (-?\d+)\)'
    failures=[]
    for index,match in enumerate(re.finditer(pattern,log.read_text())):
        plane,ratio,limit,*coordinates=match.groups()
        failures.append(dict(stage='native_'+plane,cluster=index,
             native_effective_ratio=float(ratio),native_limit=float(limit),
             gate_bbox_nm=[int(v)*5 for v in coordinates]))
    if not failures or not receipt['native_antenna_feedback_entries']:
        raise ValueError('native nonpass with explicit gate records required')
    frame=a.frame.resolve();frame_path=frame/'assessment.json'
    selected=json.loads(frame_path.read_text());verify(selected['input_sha256']);verify(selected['artifacts'])
    assert selected['assembly_frame_pass']
    verify(selected['candidate_source_sha256'])
    assert all(selected['input_sha256'].get(k)==v for k,v in selected['candidate_source_sha256'].items())
    stream=a.layout.resolve()/'stream_assessment.json'
    streamed=json.loads(stream.read_text());verify(streamed['input_sha256'])
    assert streamed['input_sha256'].get(str(frame_path))==sha(frame_path)
    assert streamed['assembly_gds_sha256']==sha(gds)
    lefs={name:Path(view['lef']) for name,view in selected['macro_sources'].items()}
    offsets={name:tuple(box[:2]) for name,box in selected['macro_bboxes_dbu'].items()}
    route=a.route.resolve();route_receipt=route/'assessment.json';connections=route/'connections.tsv'
    routed=json.loads(route_receipt.read_text());verify(routed['artifacts'])
    assert streamed['input_sha256'].get(str(route_receipt))==sha(route_receipt)
    assert routed['artifacts'].get(str(connections))==sha(connections)
    bindings={}
    for line in connections.read_text().splitlines():
        instance,pin,net=line.split('\t')
        if (instance,pin) in bindings:raise ValueError('duplicate routed pin')
        bindings[instance,pin]=net
    assert set(expected())<=set(bindings)
    ports=[]
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
    engine,regs=engine_at_stage(geom,'m5');aliases=defaultdict(list)
    for port in ports:
        net=engine.probe_net(regs[port['layer']],pya.Point(*port['point']))
        if net is not None:aliases[net.cluster_id].append(port)
    result=[]
    for row in failures:
        x1,y1,x2,y2=row['gate_bbox_nm']
        net=engine.probe_net(regs['gate'],pya.Point((x1+x2)//2,(y1+y2)//2))
        if net is None:raise ValueError('native gate coordinate is absent from source channel geometry')
        result.append(dict(row,full_topology_cluster=net.cluster_id,macro_ports=aliases[net.cluster_id]))
    save(out/'records.json',result)
    nets=sorted({port['net'] for r in result for port in r['macro_ports']})
    paths=[route_receipt,connections,Path(__file__).resolve(),ROOT/'verification/prototype400/klayout_compat.py',frame_path,stream,gds,ant/'assessment.json',log,*lefs.values()]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
         artifacts={str(out/'records.json'):sha(out/'records.json')},violations=len(result),
         violations_with_macro_port=sum(bool(r['macro_ports']) for r in result),affected_parent_nets=nets,
         native_gate_records=len(failures),native_feedback_rectangles=receipt['native_antenna_feedback_entries'],
         record_semantics='native_gate_records_not_feedback_rectangle_count',
         full_topology_used_for_net_identity_only=True,independent_forming_pass_does_not_waive_native_failures=True,
         release_qualified=False))
    signal.alarm(0)
    print(json.dumps(dict(violations=len(result),mapped=sum(bool(r['macro_ports']) for r in result),nets=len(nets))))


if __name__=='__main__':
    import os,time
    from resources import lease
    os.sched_setaffinity(0,{28})
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+43200):main()
