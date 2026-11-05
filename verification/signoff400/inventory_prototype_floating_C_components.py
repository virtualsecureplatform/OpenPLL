"""Inventory capacitor-only components, retaining every device, wire and port node."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
from common_v3 import save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from prepare_prototype_BBPD_receiver_v3 import header


def components(text,top):
    blocks=subcircuits(text)
    if set(blocks)!={top}:raise ValueError('one flat primitive hierarchy required')
    block=blocks[top];retained=set(header(block));caps=[];resistors=0;devices=0
    for line in block.splitlines():
        f=line.split()
        if not f or f[0].startswith(('*','.','+')):continue
        if f[0].startswith('Cflat'):
            if len(f)!=4:raise ValueError('constant two-terminal capacitor required')
            caps.append((f[1],f[2],f[3].startswith('-')))
        elif f[0].startswith('Rwire'):
            if len(f)!=4:raise ValueError('constant wire resistor required')
            retained.update(f[1:3]);resistors+=1
        elif f[0].startswith('Xflat'):
            positional=[]
            for token in f[1:]:
                if '=' in token:break
                positional.append(token)
            if not positional or not positional[-1].startswith('sky130_fd_pr__'):
                raise ValueError('explicit native primitive required')
            retained.update(positional[:-1]);devices+=1
        else:raise ValueError('unreviewed flat element: '+f[0])
    all_nodes={n for a,b,_ in caps for n in (a,b)};floating=all_nodes-retained
    parent={n:n for n in floating}
    def find(n):
        while parent[n]!=n:parent[n]=parent[parent[n]];n=parent[n]
        return n
    def join(a,b):parent[find(a)]=find(b)
    for a,b,_ in caps:
        if a in floating and b in floating:join(a,b)
    groups=defaultdict(list)
    for n in sorted(floating):groups[find(n)].append(n)
    boundary=defaultdict(set);counts=Counter();negative=Counter()
    for a,b,neg in caps:
        roots={find(n) for n in (a,b) if n in floating}
        for component in roots:
            boundary[component].update(n for n in (a,b) if n not in floating)
            counts[component]+=1;negative[component]+=neg
    rows=[dict(nodes=nodes,boundaries=sorted(boundary[key]),nodes_count=len(nodes),
               boundary_count=len(boundary[key]),incident_capacitors=counts[key],
               negative_incident_capacitors=negative[key]) for key,nodes in groups.items()]
    rows.sort(key=lambda r:(-r['nodes_count'],r['nodes'][0]))
    return rows,dict(flat_primitives=devices,wire_resistors=resistors,capacitor_pairs=len(caps),
        retained_device_wire_and_port_nodes=len(retained),capacitor_only_nodes=len(floating),
        floating_components=len(rows),largest_floating_component=max((r['nodes_count'] for r in rows),default=0),
        largest_component_boundary=max((r['boundary_count'] for r in rows),default=0),
        component_size_histogram=dict(Counter(str(r['nodes_count']) for r in rows)),
        floating_components_without_retained_boundary=sum(not r['boundaries'] for r in rows))


def run(models,attachment,output):
    receipt=models/'assessment.json';m=json.loads(receipt.read_text());verify(m['input_sha256']);verify(m['artifacts'])
    source=models/(attachment+'.spice')
    if m['artifacts'].get(str(source))!=sha(source) or not m['each_fixed_supply_dynamic_C_operator_passivity_certified']:
        raise ValueError('certified completed source model required')
    blocks=subcircuits(source.read_text())
    if len(blocks)!=1:raise ValueError('one analog hierarchy required')
    rows,stats=components(source.read_text(),next(iter(blocks)))
    inputs={str(p):sha(p) for p in (receipt,source,Path(__file__).resolve(),
        Path(__file__).with_name('prepare_prototype_analog_reference.py'),Path(__file__).with_name('prepare_prototype_BBPD_receiver_v3.py'))}
    verify(inputs);output.mkdir(parents=True,exist_ok=False);save(output/'components.json',rows)
    save(output/'assessment.json',dict(input_sha256=inputs,artifacts={str(output/'components.json'):sha(output/'components.json')},
        **stats,attachment=attachment,topology_inventory_only=True,floating_nodes_not_removed_or_grounded=True,
        terminal_equivalent_reduction_verified=False,release_ready=False))
    print(json.dumps({k:v for k,v in stats.items() if k!='component_size_histogram'}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('models','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--attachment',choices=('driver','farthest'),required=True)
    a=parser.parse_args();run(a.models.resolve(),a.attachment,a.output.resolve())
