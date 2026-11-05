"""Find complete physical cells on uncut DCO driver-domain signal nets.

Only the 302 programming-driver input components are prescribed. Supply nets
are excluded. Reset drivers and output receivers remain physical-cell closure
obligations rather than ideal output waveforms or guessed capacitors.
"""
import argparse,json
from collections import defaultdict,Counter
from pathlib import Path
from common_v3 import save,sha,verify
from compare_prototype_physical_primitive_graphs import parsed,Union
from resolve_prototype_loaded_halo_interfaces import local_bindings,library_directions
from plan_selected_detector_passive_cut import RAILS


def closure(bound,pins,directions,union,selected,prescribed):
    selected_cells={k for k,e in bound.items() if set(e['primitives'])&selected}
    if any(not set(bound[k]['primitives'])<=selected for k in selected_cells):raise ValueError('selection cuts a physical cell')
    excluded={union.find(n) for n in RAILS|set(prescribed)}
    internal=defaultdict(list);external=defaultdict(list)
    for key,ports in pins.items():
        for pin,node in ports.items():
            direction=directions[bound[key]['master']][pin];component=union.find(node)
            if component in excluded or direction not in ['INPUT','OUTPUT','INOUT']:continue
            (internal if key in selected_cells else external)[component].append(dict(cell_key=key,pin=pin,node=node,direction=direction))
    nets={c:dict(inside=internal[c],outside=external[c]) for c in internal.keys()&external.keys()}
    additions={e['cell_key'] for net in nets.values() for e in net['outside']}
    return nets,additions


def run(inventory,metadata,wire,hierarchy,library,output):
    if output.exists():raise FileExistsError(output)
    inv=json.loads(inventory.read_text());verify(inv['input_sha256'])
    for p in [metadata,wire,hierarchy,library]:
        if inv['input_sha256'].get(str(p))!=sha(p):raise ValueError('same driver inventory physical sources required')
    lr=json.loads(library.read_text());verify(lr['artifacts']);directions={}
    for p in lr['artifacts']:directions.update(library_directions(Path(p).read_text()))
    instances=json.loads(metadata.read_text())['physical_instances']
    cells={i['instance']:json.dumps([i['physical_hierarchy_identity'],i['leaf_master']],separators=(',',':')) for i in instances}
    terms={};union=Union()
    for line in wire.open():
        f=line.split()
        if not f:continue
        if f[0].startswith('Xflat'):
            stop=next(i for i,t in enumerate(f) if t.startswith('sky130_fd_pr__'));terms[f[0]]=f[1:stop]
        elif f[0].startswith('R'):union.join(f[1],f[2])
    bound,aliases=local_bindings(instances,terms,cells,parsed(hierarchy.read_text()));pins={}
    for key,e in bound.items():
        pins[key]={p:e['nodes'][aliases[e['master']].find(p)] for p in directions.get(e['master'],{}) if aliases[e['master']].find(p) in e['nodes']}
    selected=set(inv['DCO_with_control_driver_primitives']);nets,added=closure(bound,pins,directions,union,selected,inv['required_control_driver_input_nodes'])
    expanded=selected|{n for k in added for n in bound[k]['primitives']}
    next_nets,next_added=closure(bound,pins,directions,union,expanded,inv['required_control_driver_input_nodes'])
    inputs={str(p):sha(p) for p in [inventory,metadata,wire,hierarchy,library,Path(__file__).resolve(),Path(__file__).with_name('resolve_prototype_loaded_halo_interfaces.py'),Path(__file__).with_name('plan_selected_detector_passive_cut.py')]};verify(inputs)
    save(output,dict(input_sha256=inputs,signal_interfaces=nets,added_cells=[dict(cell_key=k,master=bound[k]['master'],primitives=bound[k]['primitives'],pins=pins[k]) for k in sorted(added)],
        expanded_selected_primitives=sorted(expanded),prescribed_control_driver_input_nodes=inv['required_control_driver_input_nodes'],
        next_signal_interfaces=next_nets,next_external_cell_count=len(next_added),
        fixed_supply_nodes=sorted(RAILS),programming_input_components_excluded=True,reset_output_closure_qualified=False,
        boundary_stimuli_qualified=False,frequency_correlation_qualified=False,release_ready=False))
    print(json.dumps(dict(signal_interfaces=len(nets),added_cell_masters=dict(Counter(bound[k]['master'] for k in added)),expanded_primitives=len(expanded),next_external_cells=len(next_added))))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['inventory','metadata','wire','hierarchy','library','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['inventory','metadata','wire','hierarchy','library','output']))
