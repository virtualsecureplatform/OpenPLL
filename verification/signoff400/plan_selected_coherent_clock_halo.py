"""Retain complete closed clock-driver cones for high-ranked DCO coupling cuts."""
import argparse,json,os
from pathlib import Path
from common_v3 import save,sha,verify
from plan_selected_detector_passive_cut import passive_cut
from compare_prototype_physical_primitive_graphs import Union


def run(base,cones,metadata,model,output):
    if output.exists():raise FileExistsError(output)
    b,c=[json.loads(p.read_text()) for p in [base,cones]]
    verify(b['input_sha256']);verify(c['input_sha256'])
    for p in [metadata,model]:
        if b['input_sha256'].get(str(p))!=sha(p):raise ValueError('same native physical circuit required')
    if c['input_sha256'].get(str(metadata))!=sha(metadata):raise ValueError('same driver geometry required')
    selected=set(b['selected_primitives']);added_cells={};resolved=[];unresolved=[]
    for row in c['records']:
        if not row['closed_to_retained_cells_and_supplies']:unresolved.append(row['node']);continue
        if any(f['kind'] not in ['retained_cell','supply','prescribed_program_input'] for f in row['frontiers']):raise ValueError('closed cone has unresolved frontier')
        for cell in row['combinational_driver_cells']:
            if 'D' in cell['pins'] and any(p in cell['pins'] for p in ['CLK','CLK_N','CLKN']):raise ValueError('stateful driver cannot be silently retained')
            added_cells[cell['cell_key']]=cell;selected.update(cell['primitives'])
        resolved.append(row['node'])
    if not resolved or selected==set(b['selected_primitives']):raise ValueError('nonempty resolved physical driver expansion required')
    prescribed=set(b['prescribed_control_driver_input_nodes'])|{b['prescribed_reset_driver_input']}
    items={i['instance']:i for i in json.loads(metadata.read_text())['physical_instances']};terms={};passives=[];inside=False;wires=Union()
    for line in model.open():
        f=line.split()
        if not f:continue
        if f[0].lower()=='.subckt':inside=f[1]=='IntegerPLL_400MHz_PrototypeTop';continue
        if f[0].lower()=='.ends':inside=False;continue
        if not inside:continue
        if f[0].startswith('Xflat'):
            count=len(items[f[0]]['local_primitive_signature'][1]);terms[f[0]]=f[1:count+1]
        elif f[0][0].upper() in ['R','C']:
            passives.append((f[0],f[1],f[2]))
            if f[0][0].upper()=='R':wires.join(f[1],f[2])
    if terms.keys()!=items.keys():raise ValueError('complete native primitive graph required')
    private,boundary,cards,omitted=passive_cut(terms,passives,selected,prescribed)
    if not set(resolved)<=private:raise ValueError('resolved clock voltages must become native unknowns')
    if not {'__parent_R_node_616','__parent_R_node_618'}<=private:raise ValueError('DCO output/reset must remain native unknowns')
    if any(wires.find(n)==wires.find('__parent_R_node_616') for n in boundary):raise ValueError('DCO output resistive component has a voltage clamp')
    pins=dict(b['input_sha256']);pins.update({str(p):sha(p) for p in [base,cones,Path(__file__).resolve(),Path(__file__).with_name('plan_selected_detector_passive_cut.py')]});verify(pins)
    result=dict(input_sha256=pins,selected_primitives=sorted(selected),private_unknown_nodes=sorted(private),required_non_supply_boundary_voltage_nodes=sorted(boundary),retained_passive_cards=[passives[i][0] for i in sorted(cards)],omitted_primitives_touching_private_nodes=omitted,prescribed_control_driver_input_nodes=b['prescribed_control_driver_input_nodes'],prescribed_reset_driver_input=b['prescribed_reset_driver_input'],fixed_supply_nodes=b['fixed_supply_nodes'],added_clock_driver_cells=list(added_cells.values()),added_primitives=sorted(selected-set(b['selected_primitives'])),resolved_dynamic_boundary_nodes=resolved,unresolved_dynamic_boundary_nodes=unresolved,capacitor_only_unknowns_preserved=True,coherent_clock_driver_outputs_unclamped=True,full_dynamic_boundary_forcing_covered=False,physical_models_qualified=False,release_ready=False)
    save(output,result);print(json.dumps(dict(selected_primitives=len(selected),added_cells=len(added_cells),added_primitives=len(result['added_primitives']),resolved_clock_nodes=len(resolved),unresolved_clock_nodes=len(unresolved),retained_passives=len(cards))))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['base','cones','metadata','model','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();os.sched_setaffinity(0,{29});run(*(getattr(a,n).resolve() for n in ['base','cones','metadata','model','output']))
