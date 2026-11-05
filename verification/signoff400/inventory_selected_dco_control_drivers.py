"""Bind every DCO control to its real physical driver and receiver loads.

This is a structural inventory for a full-derived analog bench. It does not
replace drivers with ideal sources or claim boundary or frequency correlation.
"""
import argparse,json
from collections import defaultdict,Counter
from pathlib import Path
from common_v3 import save,sha,verify
from compare_prototype_physical_primitive_graphs import parsed,Union
from resolve_prototype_loaded_halo_interfaces import local_bindings,library_directions


def run(bias,metadata,wire,hierarchy,library,output):
    if output.exists():raise FileExistsError(output)
    bv=json.loads(bias.read_text());verify(bv['input_sha256'])
    for p in [metadata,hierarchy]:
        if bv['input_sha256'].get(str(p))!=sha(p):raise ValueError('bias/physical extraction identity mismatch')
    wm=wire.parent/'wire_map.json'
    if bv['input_sha256'].get(str(wm))!=sha(wm):raise ValueError('wire attachment identity mismatch')
    receipt=wire.parent/'assessment.json';wr=json.loads(receipt.read_text());verify(wr['artifacts'])
    if wr['artifacts'].get(str(wire))!=sha(wire):raise ValueError('proved physical wire graph required')
    lr=json.loads(library.read_text());verify(lr['artifacts'])
    directions={}
    for p in lr['artifacts']:
        for master,ports in library_directions(Path(p).read_text()).items():
            if master in directions and directions[master]!=ports:raise ValueError('conflicting LEF directions')
            directions[master]=ports
    instances=json.loads(metadata.read_text())['physical_instances']
    cells={i['instance']:json.dumps([i['physical_hierarchy_identity'],i['leaf_master']],separators=(',',':')) for i in instances}
    terms={};union=Union()
    for line in wire.open():
        f=line.split()
        if not f:continue
        if f[0].startswith('Xflat'):
            stop=next(i for i,t in enumerate(f) if t.startswith('sky130_fd_pr__'));terms[f[0]]=f[1:stop]
        elif f[0].startswith('R'):union.join(f[1],f[2])
    bound,aliases=local_bindings(instances,terms,cells,parsed(hierarchy.read_text()))
    pins={};drivers=defaultdict(list);receivers=defaultdict(list)
    for key,entry in bound.items():
        pins[key]={}
        for pin,direction in directions.get(entry['master'],{}).items():
            node=entry['nodes'].get(aliases[entry['master']].find(pin))
            if node is None:continue
            pins[key][pin]=node
            if direction=='OUTPUT':drivers[union.find(node)].append((key,pin))
            elif direction=='INPUT':receivers[union.find(node)].append((key,pin))
    def describe(key):return dict(cell_key=key,master=bound[key]['master'],primitives=bound[key]['primitives'],pins=pins[key])
    dco={i['instance'] for i in instances if i['physical_hierarchy_identity'][0][2][0].startswith('IntegerPLL_DCO_')}
    if len(dco)!=4210:raise ValueError('expected selected DCO primitive inventory')
    controls={};selected=set();inverter_inputs=set()
    for port,c in bv['controls'].items():
        component=union.find(c['physical_driver_anchor']);candidates=drivers[component]
        if len(candidates)!=1:raise ValueError('unique physical control driver required: '+port)
        key,pin=candidates[0];entry=bound[key]
        if entry['master']!='sky130_fd_sc_hs__inv_2' or pin!='Y' or 'A' not in pins[key]:raise ValueError('expected physical HS INV2 control driver')
        if len(entry['primitives'])!=4:raise ValueError('complete four-device control driver required')
        if pins[key]['A'] in inverter_inputs:raise ValueError('control driver inputs unexpectedly shared')
        inverter_inputs.add(pins[key]['A']);selected.add(key)
        controls[port]=dict(driver=describe(key),driver_input_node=pins[key]['A'],driver_input_for_final_bias_V=1.8-c['isolated_bias_V'],
            driver_output_anchor=c['physical_driver_anchor'],native_final_output_V=c['native_final_V'],
            physical_receivers=[dict(cell_key=k,pin=p,master=bound[k]['master'],inside_DCO=set(bound[k]['primitives'])<=dco) for k,p in receivers[component]])
    if len(controls)!=302 or len(selected)!=302:raise ValueError('complete independent 255 fine and 47 coarse drivers required')
    primitives=dco|{n for k in selected for n in bound[k]['primitives']}
    sources=[bias,metadata,wire,wm,receipt,hierarchy,library,Path(__file__).resolve(),Path(__file__).with_name('resolve_prototype_loaded_halo_interfaces.py'),Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py')]
    inputs={str(p):sha(p) for p in sources};inputs.update(lr['artifacts']);verify(inputs)
    save(output,dict(input_sha256=inputs,controls=controls,control_driver_cells=len(selected),control_driver_primitives=len(primitives-dco),
        DCO_primitives=sorted(dco),DCO_with_control_driver_primitives=sorted(primitives),
        required_control_driver_input_nodes=sorted(inverter_inputs),
        receiver_master_counts=dict(Counter(r['master'] for c in controls.values() for r in c['physical_receivers'])),
        control_driver_impedance_retained_by_selection=True,reset_driver_and_output_load_selection_complete=False,
        passive_partition_complete=False,boundary_stimuli_qualified=False,frequency_correlation_qualified=False,release_ready=False))
    print(json.dumps(dict(DCO_primitives=len(dco),control_drivers=len(selected),combined_primitives=len(primitives),receiver_master_counts=dict(Counter(r['master'] for c in controls.values() for r in c['physical_receivers'])))))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['bias','metadata','wire','hierarchy','library','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['bias','metadata','wire','hierarchy','library','output']))
