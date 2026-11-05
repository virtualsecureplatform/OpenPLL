"""Add a complete physical-cell layer of omitted loads to a DCO partition.

Keep programming/reset cuts unchanged, preserve floating capacitor unknowns,
and report all newly exposed loads. This is a sensitivity control, not a
qualified closure of the surrounding controller.
"""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from extend_selected_detector_loads import full_load_cells
from plan_selected_detector_passive_cut import passive_cut
from compare_prototype_physical_primitive_graphs import Union


def run(base,metadata,model,output):
    if output.exists():raise FileExistsError(output)
    b=json.loads(base.read_text());verify(b['input_sha256'])
    for p in [metadata,model]:
        if b['input_sha256'].get(str(p))!=sha(p):raise ValueError('same physical DCO extraction required')
    items={i['instance']:i for i in json.loads(metadata.read_text())['physical_instances']}
    selected,masters=full_load_cells(set(b['selected_primitives']),b['omitted_primitives_touching_private_nodes'],items)
    prescribed=set(b['prescribed_control_driver_input_nodes'])|{b['prescribed_reset_driver_input']}
    if None in prescribed or len(prescribed)!=303:raise ValueError('unchanged complete programming/reset input cuts required')
    terms={};passives=[];inside=False;wires=Union()
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
    if terms.keys()!=items.keys():raise ValueError('complete native physical primitive graph required')
    private,boundary,cards,omitted=passive_cut(terms,passives,selected,prescribed)
    # These are the selected DCO's physical output and reset contacts in this
    # frozen candidate, not guessed macro net aliases.
    observed={'__parent_R_node_616','__parent_R_node_618'}
    if not observed<=private:raise ValueError('DCO output/reset must remain unknown voltages')
    if any(wires.find(n)==wires.find('__parent_R_node_616') for n in boundary):raise ValueError('DCO output wire component is clamped by a boundary source')
    pins=dict(b['input_sha256']);pins.update({str(p):sha(p) for p in [base,Path(__file__).resolve(),Path(__file__).with_name('extend_selected_detector_loads.py'),Path(__file__).with_name('plan_selected_detector_passive_cut.py')]});verify(pins)
    save(output,dict(input_sha256=pins,selected_primitives=sorted(selected),private_unknown_nodes=sorted(private),
        required_non_supply_boundary_voltage_nodes=sorted(boundary),retained_passive_cards=[passives[i][0] for i in sorted(cards)],
        omitted_primitives_touching_private_nodes=omitted,prescribed_control_driver_input_nodes=b['prescribed_control_driver_input_nodes'],
        prescribed_reset_driver_input=b['prescribed_reset_driver_input'],added_cell_masters=masters,added_primitives=sorted(selected-set(b['selected_primitives'])),
        fixed_supply_nodes=b['fixed_supply_nodes'],capacitor_only_unknowns_preserved=True,control_driver_outputs_unclamped=True,
        shared_node_loads_bounded=False,boundary_waveforms_bound=False,native_model_ready=False,physical_models_qualified=False,release_ready=False))
    print(json.dumps(dict(selected_primitives=len(selected),added_primitives=len(selected-set(b['selected_primitives'])),added_cell_masters=masters,
        private_nodes=len(private),boundary_nodes=len(boundary),retained_passives=len(cards),remaining_omitted_primitives=len(omitted))))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['base','metadata','model','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['base','metadata','model','output']))
