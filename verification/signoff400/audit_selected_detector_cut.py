"""Inventory every primitive and capacitor attachment at a proposed detector cut.

Uses primitive terminals rather than LEF pin directions so antenna diodes and
INOUT loads cannot disappear from the load inventory. No boundary is qualified.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from common_v3 import save, sha, verify
from compare_prototype_physical_primitive_graphs import Union

RAILS={'0','VPWR','VPB','VGND','VNB'}


def attachments(terms, resistors, capacitors, selected):
    if not selected or not selected <= terms.keys():
        raise ValueError('selected primitive identity missing')
    u=Union()
    for _,a,b in resistors:u.join(a,b)
    rail_components={u.find(n) for n in RAILS}
    active={u.find(n) for name in selected for n in terms[name]}-rail_components
    external=defaultdict(list)
    for name,nodes in terms.items():
        if name in selected:continue
        for index,node in enumerate(nodes):
            if u.find(node) in active:
                external[name].append(dict(terminal_index=index,node=node,component=u.find(node)))
    crossing=[];internal=0
    for name,a,b,value in capacitors:
        ca,cb=u.find(a),u.find(b)
        if ca not in active and cb not in active:continue
        if ca in active and cb in active:internal+=1
        else:
            crossing.append(dict(card=name,nodes=[a,b],value=value,
                                 remote_node=b if ca in active else a,
                                 remote_is_fixed_rail=(cb if ca in active else ca) in rail_components))
    return dict(external_primitive_terminals=dict(external),crossing_capacitors=crossing,
                internal_capacitor_count=internal,signal_resistor_component_count=len(active))


def run(detector,receivers,metadata_path,model,output):
    if output.exists():raise FileExistsError(output)
    dv=json.loads(detector.read_text());rv=json.loads(receivers.read_text())
    verify(dv['input_sha256']);verify(rv['input_sha256'])
    if rv['input_sha256'].get(str(detector))!=sha(detector):raise ValueError('receiver detector identity mismatch')
    for path in [metadata_path,model]:
        if dv['input_sha256'].get(str(path))!=sha(path):raise ValueError('physical source identity mismatch')
    pins={str(p):sha(p) for p in [detector,receivers,metadata_path,model,Path(__file__).resolve(),Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py')]}
    items={i['instance']:i for i in json.loads(metadata_path.read_text())['physical_instances']}
    terms={};resistors=[];capacitors=[];inside=False
    for line in model.open():
        f=line.split()
        if not f:continue
        if f[0].lower()=='.subckt':inside=f[1]=='IntegerPLL_400MHz_PrototypeTop';continue
        if f[0].lower()=='.ends':inside=False;continue
        if not inside:continue
        if f[0].startswith('Xflat'):
            count=len(items[f[0]]['local_primitive_signature'][1])
            if f[0] in terms:raise ValueError('duplicate native primitive')
            terms[f[0]]=f[1:count+1]
        elif f[0][0].upper()=='R':resistors.append((f[0],f[1],f[2]))
        elif f[0][0].upper()=='C':capacitors.append((f[0],f[1],f[2],f[3]))
    if terms.keys()!=items.keys():raise ValueError('incomplete native primitive coverage')
    selected=set(dv['selected_detector_primitives'])|set(rv['selected_receiver_primitives'])
    report=attachments(terms,resistors,capacitors,selected)
    loads=report['external_primitive_terminals']
    report['external_primitive_master_counts']=dict(Counter(items[n]['leaf_master'] for n in loads))
    report['external_primitive_models']={n:items[n]['local_primitive_signature'][0] for n in loads}
    report['selected_primitive_count']=len(selected)
    report['crossing_capacitor_count']=len(report['crossing_capacitors'])
    report['input_sha256']=pins
    report.update(boundary_conditions_validated=False,receiver_loading_bounded=False,
                  native_phase_bench_exported=False,physical_models_qualified=False,release_ready=False)
    verify(pins);save(output,report)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['detector','receivers','metadata','model','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=run(a.detector.resolve(),a.receivers.resolve(),a.metadata.resolve(),a.model.resolve(),a.output.resolve())
    print(json.dumps({k:r[k] for k in ['selected_primitive_count','signal_resistor_component_count','external_primitive_master_counts','crossing_capacitor_count','release_ready']}))
