#!/usr/bin/env python3
"""Correlate current digital terminals with the flat extraction connectivity.

Probe actual conductor components through M5, including converted metal fill.
Reject missing or split connected terminals and different logical nets on one
physical component. Correlation is prerequisite data, not a timing enclosure.
"""
import argparse
from collections import defaultdict
import copy
import json
import math
from pathlib import Path
import signal
import sys
import time
import pya
from check_compact_clock_tree import verify
from check_forming_antenna_geometry_v2 import geometry,engine_at_stage
from run_dco_qualification import sha,save


def validate(rows,parent_labels):
    logical=defaultdict(set);physical=defaultdict(set)
    for row in rows:
        if row['logical_net'] is None:continue
        assert len(row['clusters'])==1,('missing/split terminal',row['instance'],row['pin'],row['clusters'])
        cluster=row['clusters'][0];logical[row['logical_net']].add(cluster);physical[cluster].add(row['logical_net'])
        if row['logical_net'] in parent_labels:
            assert parent_labels[row['logical_net']]==cluster,('parent alias mismatch',row)
    assert all(len(ids)==1 for ids in logical.values()),'logical net spans distinct physical components'
    assert all(len(nets)==1 for nets in physical.values()),'physical component joins distinct logical nets'
    return logical,physical


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['view','inventory','output']:parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args();view=args.view.resolve();inventory=args.inventory.resolve();out=args.output.resolve()
    v=verify(view/'assessment.json');i=verify(inventory/'assessment.json')
    assert v['converted_metal_fill_purpose_layers_removed'] and v['unique_parent_net_labels']==359
    assert i['exact_def_gds_instance_transforms'] and i['signal_terminals']==22883
    owner=json.loads((view/'owner.json').read_text());left=owner['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME);assert left>0
    signal.alarm(max(1,math.floor(left)))
    gds=view/'capacitance_view.gds';assert sha(gds)==v['artifacts'][str(gds)]
    rows=json.loads((inventory/'terminals.json').read_text())
    paths=[Path(__file__).resolve(),Path(sys.executable),Path(__file__).with_name('check_forming_antenna_geometry_v2.py'),
        view/'assessment.json',view/'owner.json',gds,inventory/'assessment.json',inventory/'terminals.json']
    pins={str(p):sha(p) for p in paths}
    layout=pya.Layout();layout.read(str(gds));assert layout.dbu==.001
    top=layout.cell(v['top']);geom=geometry(layout,top)
    assert geom['gate'].area()==v['mos_gate_area_nm2']
    print('Building full conductor connectivity through M5.',flush=True)
    engine,regs=engine_at_stage(geom,'m5');parent_labels={}
    for index in layout.layer_indices():
        info=layout.get_info(index)
        if info.datatype!=5 or not 68<=info.layer<=72:continue
        kind='m'+str(info.layer-67)
        for shape in top.shapes(index).each():
            if not shape.is_text():continue
            text=shape.text;node=engine.probe_net(regs[kind],pya.Point(text.x,text.y));assert node is not None,text.string
            assert text.string not in parent_labels;parent_labels[text.string]=node.cluster_id
    assert len(parent_labels)==len(set(parent_labels.values()))==359
    resolved=[];missing_probe_count=0;split=[]
    for row in rows:
        clusters=set();missing=[]
        for probe in row['probes']:
            node=engine.probe_net(regs[probe['layer']],pya.Point(*probe['point_nm']))
            if node is None:missing.append(probe)
            else:clusters.add(node.cluster_id)
        missing_probe_count+=len(missing)
        result={k:value for k,value in row.items() if k!='probes'}
        result.update(clusters=sorted(clusters),missing_rectangular_probes=len(missing))
        if len(clusters)!=1:split.append(result)
        resolved.append(result)
    logical,physical=validate(resolved,parent_labels)
    assert not split,('unresolved terminals',split[:10])
    chosen=[r for r in resolved if r['logical_net'] is not None]
    a=chosen[0];b=next(r for r in chosen if r['logical_net']!=a['logical_net'])
    wrong=copy.deepcopy(resolved);index=resolved.index(a);wrong[index]['clusters']=b['clusters']
    try:validate(wrong,parent_labels)
    except AssertionError:negative=True
    else:raise AssertionError('wrong terminal projection accepted')
    groups=defaultdict(list)
    for row in resolved:
        if row['logical_net'] is not None:groups[row['logical_net']].append(row)
    nets=[dict(logical_net=net,cluster=next(iter(logical[net])),terminals=len(terms),
        drivers=[dict(instance=r['instance'],master=r['master'],pin=r['pin']) for r in terms if r['direction']=='OUTPUT'],
        sinks=sum(r['direction'] in ['INPUT','INOUT'] for r in terms),parent_net=net in parent_labels)
        for net,terms in sorted(groups.items())]
    out.mkdir(parents=True,exist_ok=False);save(out/'terminals.json',resolved);save(out/'nets.json',nets)
    save(out/'parent_labels.json',parent_labels)
    for p,d in pins.items():assert sha(p)==d,p
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        correlated_signal_terminals=len(resolved),connected_logical_nets=len(logical),parent_labels_traced=359,
        parent_nets_with_digital_terminals=sum(r['parent_net'] for r in nets),missing_connected_terminals=0,split_connected_nets=0,
        distinct_logical_nets_shorted=0,missing_rectangular_probes_retained=missing_probe_count,all_terminals_have_one_physical_component=True,
        wrong_terminal_projection_control_rejected=negative,exact_physical_terminal_correlation_passed=True,
        effective_load_enclosure_qualified=False,physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Correlated',len(resolved),'terminals and',len(logical),'digital nets; wrong-coordinate control rejected.',flush=True)

if __name__=='__main__':main()
