#!/usr/bin/env python3
"""Inventory current digital wire-capacitance matrix diagonals by driver type.

Use the verified native-node identities and exact-positive capacitor network.
Do not include nonlinear transistor gate/junction charge, infer effective loads,
exclude zero-load fixtures or qualify interpolation/timing from these sums.
"""
import argparse
from array import array
from collections import defaultdict
import json
import math
from pathlib import Path
import signal
import time
from audit_parent_capacitance_network import value
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();base=ROOT/'build/timing400/release_001';positive=base/'parent_filled_metal_capacitance_positive_001'
    mapping=base/'current_digital_native_capacitance_nodes_001';m=verify(mapping/'assessment.json');assert m['digital_node_identity_complete']
    p=verify(positive/'assessment.json');assert p['representation_reduction_exact_for_parsed_network']
    owner=json.loads((positive/'owner.json').read_text());left=owner['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME);assert left>0
    signal.alarm(max(1,math.floor(left)))
    rows=json.loads((mapping/'digital_nodes.json').read_text());assert len(rows)==7468
    by_native={row['native_names'][0]:row for row in rows};assert len(by_native)==len(rows)
    source=positive/'capacitance_positive.spice';plan=base/'compact_propagation_tt27_001/plan.json';char=json.loads(plan.read_text())
    domains={}
    for fixture in char['fixtures']:
        master=fixture['master'];domains.setdefault(master,set()).add(fixture['external_load_pf'])
    assert len(domains)==40
    files=[Path(__file__).resolve(),Path(__file__).with_name('audit_parent_capacitance_network.py'),positive/'assessment.json',positive/'owner.json',source,
        mapping/'assessment.json',mapping/'digital_nodes.json',plan]
    pins={str(f):sha(f) for f in files};values={name:array('d') for name in by_native};counts=0
    with source.open() as stream:
        for line in stream:
            if line[:1]!='C':continue
            counts+=1;fields=line.split();a,b,raw=fields[1:4]
            if a in values or b in values:
                c=value(raw);assert c>0
                if a in values:values[a].append(c)
                if b in values:values[b].append(c)
            if counts%5000000==0:print('Scanned',counts,'positive C branches.',flush=True)
    assert counts==p['retained_positive_capacitors']
    records=[];drivers=defaultdict(list)
    for name,row in sorted(by_native.items()):
        cap=math.fsum(values[name])*1e12
        item=dict(logical_net=row['logical_net'],native_node=name,unconnected_output=row['unconnected_output'],
            reported_wire_matrix_diagonal_pf=cap,positive_capacitor_branches=len(values[name]),terminals=row['terminals'])
        records.append(item)
        for terminal in row['terminals']:
            if terminal['direction']=='OUTPUT':drivers[terminal['master']].append(dict(logical_net=row['logical_net'],instance=terminal['instance'],pin=terminal['pin'],
                unconnected_output=row['unconnected_output'],reported_wire_matrix_diagonal_pf=cap))
    summary=[]
    for master,items in sorted(drivers.items()):
        limits=sorted(domains.get(master,[]));caps=[r['reported_wire_matrix_diagonal_pf'] for r in items]
        summary.append(dict(master=master,driver_outputs=len(items),unconnected_outputs=sum(r['unconnected_output'] for r in items),
            minimum_observed_wire_diagonal_pf=min(caps),maximum_observed_wire_diagonal_pf=max(caps),
            existing_fixture_external_loads_pf=limits,
            wire_diagonal_exceeds_existing_maximum_fixture=[r for r in items if limits and r['reported_wire_matrix_diagonal_pf']>limits[-1]]))
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);save(out/'nodes.json',records);save(out/'driver_types.json',summary)
    for path,d in pins.items():assert sha(path)==d,path
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        digital_nodes=len(records),connected_digital_nets=7284,unconnected_outputs=184,positive_capacitors_scanned=counts,
        driver_master_types=len(summary),existing_characterized_combinational_types=40,
        types_with_wire_diagonal_above_fixture_maximum=sum(bool(r['wire_diagonal_exceeds_existing_maximum_fixture']) for r in summary),
        nonlinear_transistor_capacitance_included=False,reported_sums_are_effective_loads=False,
        load_or_slew_enclosure_qualified=False,physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Inventoried',len(records),'current digital nodes;',sum(bool(r['wire_diagonal_exceeds_existing_maximum_fixture']) for r in summary),'driver types exceed an existing fixture maximum (diagnostic only).',flush=True)

if __name__=='__main__':main()
