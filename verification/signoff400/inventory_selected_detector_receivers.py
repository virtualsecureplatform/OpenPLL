"""Identify actual detector event-clock receivers and feedback cells.

This inventories downstream loading obligations; it neither grounds terminals
nor substitutes a nominal capacitor for an uncharacterized receiver.
"""
import argparse,json,os
from collections import defaultdict,deque
from pathlib import Path
from common_v3 import save,sha,verify
from compare_prototype_physical_primitive_graphs import parsed,Union
from resolve_prototype_loaded_halo_interfaces import local_bindings,library_directions


def run(inventory_path,ports_path,metadata_path,wire,hierarchy,library_inputs,output):
    if output.exists():raise FileExistsError(output)
    inv=json.loads(inventory_path.read_text());ports=json.loads(ports_path.read_text())
    verify(inv['input_sha256']);verify(ports['input_sha256'])
    for path in [metadata_path,wire,hierarchy]:
        if inv['input_sha256'].get(str(path))!=sha(path):raise ValueError('same physical source graph required')
    if ports['input_sha256'].get(str(inventory_path))!=sha(inventory_path):raise ValueError('port map/inventory mismatch')
    pins={str(p):sha(p) for p in [inventory_path,ports_path,metadata_path,wire,hierarchy,Path(__file__).resolve(),Path(__file__).with_name('resolve_prototype_loaded_halo_interfaces.py'),Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py')]}
    metadata=json.loads(metadata_path.read_text());instances=metadata['physical_instances']
    cells={i['instance']:json.dumps([i['physical_hierarchy_identity'],i['leaf_master']],separators=(',',':')) for i in instances}
    terms={};u=Union()
    for line in wire.open():
        f=line.split()
        if not f:continue
        if f[0].startswith('Xflat'):
            stop=next(i for i,t in enumerate(f) if t.startswith('sky130_fd_pr__'));terms[f[0]]=f[1:stop]
        elif f[0].startswith('R'):u.join(f[1],f[2])
    models=parsed(hierarchy.read_text());bound,aliases=local_bindings(instances,terms,cells,models)
    library_receipt=library_inputs/'assessment.json'
    lr=json.loads(library_receipt.read_text());verify(lr['artifacts'])
    directions={}
    for path in lr['artifacts']:
        for master,pins_here in library_directions(Path(path).read_text()).items():
            if master in directions and directions[master]!=pins_here:raise ValueError('conflicting physical pin directions')
            directions[master]=pins_here
    pins[str(library_receipt)]=sha(library_receipt);pins.update(lr['artifacts'])
    cp={};by_component=defaultdict(set);drivers=defaultdict(set)
    for key,entry in bound.items():
        master=entry['master'];cp[key]={}
        for pin,direction in directions.get(master,{}).items():
            node=entry['nodes'].get(aliases[master].find(pin))
            if node is None:continue
            cp[key][pin]=node;component=u.find(node);by_component[component].add(key)
            if direction=='OUTPUT':drivers[component].add(key)
    detector=set(inv['selected_detector_primitives']);detector_cells={cells[n] for n in detector}
    def sequential(key):return 'D' in cp[key] and any(p in cp[key] for p in ('CLK','CLK_N','CLKN'))
    def description(key):return dict(cell_key=key,master=bound[key]['master'],primitives=bound[key]['primitives'],pins=cp[key])
    selected=set();roles={};unknown=set()
    for role in ['BBPD[0]','BBPD[1]']:
        queue=deque([u.find(ports['ports'][role]['outside_wire_endpoint'])]);seen=set();reached=[]
        while queue:
            component=queue.popleft()
            if component in seen:continue
            seen.add(component)
            for key in by_component[component]-detector_cells:
                entry=bound[key];pd=directions.get(entry['master'],{})
                inputs=[p for p,n in cp[key].items() if pd.get(p)=='INPUT' and u.find(n)==component]
                if not inputs:continue
                selected.add(key)
                if sequential(key):
                    reached.append(dict(cell_key=key,master=entry['master'],input_pins=inputs));continue
                outputs=[n for p,n in cp[key].items() if pd.get(p)=='OUTPUT']
                if not outputs:unknown.add(key)
                queue.extend(u.find(n) for n in outputs)
        clock_targets={r['cell_key'] for r in reached if any(p in ('CLK','CLK_N','CLKN') for p in r['input_pins'])}
        if len(clock_targets)!=1:raise ValueError('one event-clock receiver required after complete combinational fanout traversal')
        roles[role]=dict(sequential_endpoints=reached,event_clock_receiver=next(iter(clock_targets)))
    # Complete D-input feedback cones while stopping at sequential state sources.
    pending=deque()
    for key in list(selected):
        pd=directions[bound[key]['master']]
        pending.extend(u.find(n) for pin,n in cp[key].items() if (pin=='D' if sequential(key) else pd.get(pin)=='INPUT'))
    roots={u.find(p['detector_wire_endpoint']) for p in ports['ports'].values()}
    roots.update(u.find(n) for n in ['0','VPWR','VPB','VGND','VNB'])
    visited=set();external_state=set();unresolved=set()
    while pending:
        component=pending.popleft()
        if component in roots or component in visited:continue
        visited.add(component)
        candidates=drivers[component]-detector_cells
        if len(candidates)!=1:
            unresolved.add(component);continue
        key=next(iter(candidates))
        if sequential(key):
            if key not in selected:external_state.add(key)
            continue
        selected.add(key);pd=directions[bound[key]['master']]
        pending.extend(u.find(n) for pin,n in cp[key].items() if pd.get(pin)=='INPUT')
    # Any other cells physically attached to the clock/data nets remain obligations.
    seq=[k for k in selected if sequential(k)];downstream={}
    for key in seq:
        pd=directions[bound[key]['master']];targets=set()
        for pin,node in cp[key].items():
            if pd.get(pin)=='OUTPUT':targets.update(by_component[u.find(node)]-selected-detector_cells)
        downstream[key]=[description(k) for k in sorted(targets)]
    verify(pins)
    save(output,dict(input_sha256=pins,roles=roles,selected_cells=[description(k) for k in sorted(selected)],
        selected_receiver_primitives=sorted({n for k in selected for n in bound[k]['primitives']}),
        downstream_sequential_output_cells=downstream,external_state_input_cells=[description(k) for k in sorted(external_state)],
        unresolved_input_driver_components=sorted(unresolved),unresolved_forward_cells=[description(k) for k in sorted(unknown)],
        clock_and_data_fanout_traced=True,downstream_loading_bounded=False,receiver_reset_stimuli_validated=False,
        native_phase_bench_exported=False,physical_models_qualified=False,release_ready=False))
    return dict(selected_cells=len(selected),primitives=sum(len(bound[k]['primitives']) for k in selected),
        sequential_cells=len(seq),masters=dict(__import__('collections').Counter(bound[k]['master'] for k in selected)),
        unresolved_input_driver_components=len(unresolved),external_state_inputs=len(external_state))



if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['inventory','ports','metadata','wire','hierarchy','library-inputs','output']:p.add_argument('--'+key,required=True,type=Path)
    a=p.parse_args();os.sched_setaffinity(0,{28});print(run(*(getattr(a,k).resolve() for k in ['inventory','ports','metadata','wire','hierarchy','library_inputs','output'])))
