"""Trace physical drivers of the largest omitted DCO boundary-voltage forcing.

Stop at retained cells, prescribed inputs, supplies, or unresolved/sequential
frontiers. No frontier is replaced with an assumed waveform or ideal driver.
"""
import argparse,json
from collections import defaultdict
from pathlib import Path
from common_v3 import save,sha,verify
from compare_prototype_physical_primitive_graphs import parsed,Union
from resolve_prototype_loaded_halo_interfaces import local_bindings,library_directions


def run(receivers,forcing,reference,output,count=8):
    if output.exists():raise FileExistsError(output)
    if not 1<=count<=128:raise ValueError('bounded top-node count required')
    r=json.loads(receivers.read_text());verify(r['input_sha256'])
    a=json.loads((forcing/'assessment.json').read_text());verify(a['input_sha256']);verify(a['artifacts'])
    from audit_selected_dco_history_inputs import sources
    prescribed=set(sources(reference/'sources.spice'));base=json.loads((reference/'manifest.json').read_text())
    plans=[Path(p) for p in base['input_sha256'] if p.endswith('/selected_DCO_real_driver_reset_cut_247.json')]
    if len(plans)!=1:raise ValueError('one original DCO partition required')
    plan=json.loads(plans[0].read_text());verify(plan['input_sha256']);selected=set(plan['selected_primitives'])
    for name in ['sources.spice','devices.spice']:
        if a['input_sha256'].get(str(reference/name))!=sha(reference/name):raise ValueError('same reduced DCO forcing reference required')
    def unique(suffix):
        paths=[Path(p) for p in r['input_sha256'] if p.endswith(suffix)]
        if len(paths)!=1:raise ValueError('unique physical source required: '+suffix)
        return paths[0]
    metadata=unique('/nodes.json');wire=unique('/context.spice');hierarchy=unique('/ng47.spice')
    instances=json.loads(metadata.read_text())['physical_instances']
    cells={i['instance']:json.dumps([i['physical_hierarchy_identity'],i['leaf_master']],separators=(',',':')) for i in instances}
    terms={};u=Union()
    for line in wire.open():
        f=line.split()
        if not f:continue
        if f[0].startswith('Xflat'):
            stop=next(i for i,t in enumerate(f) if t.startswith('sky130_fd_pr__'));terms[f[0]]=f[1:stop]
        elif f[0].startswith('R'):u.join(f[1],f[2])
    bound,aliases=local_bindings(instances,terms,cells,parsed(hierarchy.read_text()))
    directions={}
    for path in r['input_sha256']:
        if path.endswith('.lef'):
            for master,pins in library_directions(Path(path).read_text()).items():
                if master in directions and directions[master]!=pins:raise ValueError('conflicting pin directions')
                directions[master]=pins
    cp={};drivers=defaultdict(set)
    for key,entry in bound.items():
        cp[key]={}
        for pin,direction in directions.get(entry['master'],{}).items():
            node=entry['nodes'].get(aliases[entry['master']].find(pin))
            if node is None:continue
            cp[key][pin]=node
            if direction=='OUTPUT':drivers[u.find(node)].add(key)
    def describe(key):return dict(cell_key=key,master=bound[key]['master'],primitives=bound[key]['primitives'],pins=cp[key])
    rails={u.find(n) for n in ['0','VPWR','VGND','VPB','VNB']}
    # Prescribed voltage nodes are endpoints only after leaving the queried
    # boundary: otherwise the old constant cut would stop every new trace.
    records=[];chosen=json.loads((forcing/'boundaries.json').read_text())[:count]
    for row in chosen:
        pending=[(row['node'],True)];seen=set();added={};frontiers=[]
        while pending:
            node,initial=pending.pop();component=u.find(node)
            if component in seen:continue
            seen.add(component)
            if len(seen)>4096:raise ValueError('driver cone exceeds bounded traversal')
            if component in rails:frontiers.append(dict(node=node,kind='supply'));continue
            candidates=drivers[component]
            if len(candidates)!=1:
                frontiers.append(dict(node=node,kind='unresolved_driver',candidates=[describe(k) for k in sorted(candidates)]));continue
            key=next(iter(candidates));cell=describe(key)
            if set(cell['primitives'])<=selected:frontiers.append(dict(node=node,kind='retained_cell',cell=cell));continue
            if not initial and node in prescribed and node in plan.get('prescribed_control_driver_input_nodes',[]):frontiers.append(dict(node=node,kind='prescribed_program_input'));continue
            if 'D' in cp[key] and any(pin in cp[key] for pin in ['CLK','CLK_N','CLKN']):
                frontiers.append(dict(node=node,kind='sequential_state',cell=cell));continue
            added[key]=cell
            pending.extend((n,False) for pin,n in cp[key].items() if directions[cell['master']].get(pin)=='INPUT')
        records.append(dict(node=row['node'],forcing_rank=len(records)+1,combinational_driver_cells=list(added.values()),frontiers=frontiers,
            closed_to_retained_cells_and_supplies=all(f['kind'] in ['retained_cell','supply','prescribed_program_input'] for f in frontiers)))
    pins=dict(r['input_sha256']);pins.update({str(p):sha(p) for p in [receivers,forcing/'assessment.json',forcing/'boundaries.json',reference/'manifest.json',reference/'sources.spice',plans[0],Path(__file__).resolve()]});verify(pins)
    save(output,dict(input_sha256=pins,records=records,all_sampled_driver_cones_closed=all(x['closed_to_retained_cells_and_supplies'] for x in records),native_model_expanded=False,physical_models_qualified=False,release_ready=False))
    print(json.dumps([dict(node=x['node'],added_cells=len(x['combinational_driver_cells']),frontier_kinds=[f['kind'] for f in x['frontiers']],closed=x['closed_to_retained_cells_and_supplies']) for x in records]))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['receivers','forcing','reference','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--count',type=int,default=8);a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['receivers','forcing','reference','output']),a.count)
