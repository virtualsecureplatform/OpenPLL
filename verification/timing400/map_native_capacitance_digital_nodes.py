#!/usr/bin/env python3
"""Map native capacitance node names to current digital terminal geometry.

Use native representative coordinates and resistor-aware physical connectivity;
re-probe every digital terminal rather than reuse opaque cluster IDs. This
establishes naming identity only, not an effective-load or timing enclosure.
"""
import argparse
from collections import Counter,defaultdict
import json
import math
from pathlib import Path
import re
import signal
import sys
import time
import pya
from correlate_digital_pin_capacitance_geometry_v2 import validate
from device_aware_conductor_geometry import conductor_geometry,engine_at_stage
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();base=ROOT/'build/timing400/release_001';view=base/'parent_filled_metal_capacitance_view_002';source=base/'parent_filled_metal_capacitance_extract_002'
    inventory=base/'current_digital_pin_geometry_001';correlation=base/'current_digital_cap_geometry_correlation_002'
    v=verify(view/'assessment.json');verify(correlation/'assessment.json');native=verify(source/'native_completion.json')
    assert native['native_extraction_completed'];owner=json.loads((source/'owner.json').read_text());left=owner['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME);assert left>0
    signal.alarm(max(1,math.floor(left)))
    spice=source/'capacitance.spice';ext=source/(v['top']+'.ext');gds=view/'capacitance_view.gds'
    paths=[Path(__file__).resolve(),Path(sys.executable),Path(__file__).with_name('device_aware_conductor_geometry.py'),
        source/'native_completion.json',source/'owner.json',spice,ext,view/'assessment.json',gds,
        inventory/'assessment.json',inventory/'terminals.json',correlation/'assessment.json']
    pins={str(p):sha(p) for p in paths};active=set();device_counts=Counter()
    with spice.open() as stream:
        for line in stream:
            if line[:1].upper()=='C':break
            if line[:1].upper() not in ['M','D','R']:continue
            fields=line.split();kind=fields[0][0].upper();device_counts[kind]+=1;active.update(fields[1:5] if kind=='M' else fields[1:3])
    assert device_counts=={'M':99720,'D':726,'R':16}
    layout=pya.Layout();layout.read(str(gds));top=layout.cell(v['top']);assert top is not None
    print('Building resistor-aware geometry for native coordinate correlation.',flush=True)
    engine,regs=engine_at_stage(conductor_geometry(layout,top),'m5');parents={}
    for index in layout.layer_indices():
        info=layout.get_info(index)
        if info.datatype!=5 or not 68<=info.layer<=72:continue
        kind='m'+str(info.layer-67)
        for shape in top.shapes(index).each():
            if shape.is_text():
                t=shape.text;net=engine.probe_net(regs[kind],pya.Point(t.x,t.y));assert net is not None;parents[t.string]=net.cluster_id
    assert len(parents)==359
    targets={};checks=[]
    for row in json.loads((inventory/'terminals.json').read_text()):
        ids=set()
        for p in row['probes']:
            net=engine.probe_net(regs[p['layer']],pya.Point(*p['point_nm']))
            if net is not None:ids.add(net.cluster_id)
        assert len(ids)==1,(row['instance'],row['pin'],ids)
        check=dict(instance=row['instance'],pin=row['pin'],logical_net=row['logical_net'],clusters=sorted(ids));checks.append(check)
        name=row['logical_net'] or ('digital/__unconnected__/'+row['instance']+'/'+row['pin'])
        if name in targets:assert targets[name]['cluster']==next(iter(ids))
        else:targets[name]=dict(cluster=next(iter(ids)),unconnected_output=row['logical_net'] is None,terminals=[])
        targets[name]['terminals'].append(dict(instance=row['instance'],master=row['master'],pin=row['pin'],direction=row['direction']))
    validate(checks,parents)
    needed=active|set(parents);representatives={};unrecognized=[];ambiguous=[]
    aliases={'p':'poly','ndif':'diff','pdif':'diff','ndi':'diff','li':'li',**{f'm{i}':f'm{i}' for i in range(1,6)}}
    node_pattern=re.compile(r'^(?:node|substrate) "([^"]+)"\s+\S+\s+\S+\s+(-?\d+)\s+(-?\d+)\s+(\S+)')
    with ext.open() as stream:
        for line in stream:
            if line.startswith(('device ','cap ')) and representatives:break
            if not line.startswith(('node ','substrate ')):continue
            first=line.index('"');last=line.index('"',first+1);name=line[first+1:last]
            if name not in needed:continue
            match=node_pattern.match(line);assert match,line[:150]
            _,x,y,kind=match.groups();x=int(x)*5;y=int(y)*5
            if name in parents:
                ids={parents[name]};basis='explicit_parent_label'
            elif kind in aliases:
                ids=set();region=regs[aliases[kind]]
                for dx,dy in [(0,0),(1,1),(-1,1),(1,-1),(-1,-1)]:
                    net=engine.probe_net(region,pya.Point(x+dx,y+dy))
                    if net is not None:ids.add(net.cluster_id)
                basis='native_representative_coordinate'
            else:ids=set();basis='unsupported_native_material';unrecognized.append(dict(name=name,kind=kind,point_nm=[x,y]))
            if len(ids)!=1:ambiguous.append(dict(name=name,kind=kind,point_nm=[x,y],clusters=sorted(ids)))
            representatives[name]=dict(material=kind,point_nm=[x,y],clusters=sorted(ids),basis=basis)
    by_cluster=defaultdict(list)
    for name,row in representatives.items():
        if len(row['clusters'])==1:by_cluster[row['clusters'][0]].append(name)
    mapped=[];failures=[]
    for name,row in sorted(targets.items()):
        native_names=sorted(by_cluster[row['cluster']]);item=dict(logical_net=name,**row,native_names=native_names)
        mapped.append(item)
        if len(native_names)!=1:failures.append(item)
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    save(out/'digital_nodes.json',mapped);save(out/'native_representatives.json',representatives);save(out/'failures.json',failures)
    for p,d in pins.items():assert sha(p)==d,p
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        active_native_device_nodes=len(active),native_device_counts=dict(device_counts),native_nodes_with_representative=len(representatives),
        missing_native_device_representatives=sorted(active-set(representatives)),unsupported_native_materials=unrecognized,
        ambiguous_native_representatives=ambiguous,digital_targets=len(targets),connected_digital_nets=7284,unconnected_outputs=184,
        digital_target_mapping_failures=len(failures),digital_node_identity_complete=not failures,
        capacitance_load_enclosure_qualified=False,physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Mapped',len(mapped)-len(failures),'of',len(mapped),'digital conductor nodes to native capacitor names.',flush=True)

if __name__=='__main__':main()
