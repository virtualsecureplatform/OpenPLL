"""Plan a full-derived DCO partition retaining real programming drivers.

Keep every passive incident on private nodes, including floating capacitor-only
unknowns. Exposed active loads and exterior source voltages are obligations,
never arbitrary grounded capacitance ports or qualified behavioral inputs.
"""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from plan_selected_detector_passive_cut import passive_cut,RAILS
from extend_selected_detector_loads import full_load_cells


def run(inventory,metadata,model,output,halo=None):
    if output.exists():raise FileExistsError(output)
    inv=json.loads(inventory.read_text());verify(inv['input_sha256'])
    if inv['input_sha256'].get(str(metadata))!=sha(metadata):raise ValueError('physical metadata identity mismatch')
    items={i['instance']:i for i in json.loads(metadata.read_text())['physical_instances']}
    wire=[Path(p) for p in inv['input_sha256'] if p.endswith('/context.spice')]
    if len(wire)!=1:raise ValueError('one proved physical graph required')
    terms={};passives=[];original={};inside=False
    for line in wire[0].open():
        f=line.split()
        if f and f[0].startswith('Xflat'):
            count=len(items[f[0]]['local_primitive_signature'][1]);original[f[0]]=f[1:count+1]
    for line in model.open():
        f=line.split()
        if not f:continue
        if f[0].lower()=='.subckt':inside=f[1]=='IntegerPLL_400MHz_PrototypeTop';continue
        if f[0].lower()=='.ends':inside=False;continue
        if not inside:continue
        if f[0].startswith('Xflat'):
            count=len(items[f[0]]['local_primitive_signature'][1]);terms[f[0]]=f[1:count+1]
        elif f[0][0].upper() in ['R','C']:passives.append((f[0],f[1],f[2]))
    if terms!=original or terms.keys()!=items.keys():raise ValueError('native model and proved physical terminal graphs differ')
    prescribed=set(inv['required_control_driver_input_nodes']);selected=set(inv['DCO_with_control_driver_primitives'])
    if len(prescribed)!=302:raise ValueError('all independent control driver inputs required')
    reset_input=None
    if halo is not None:
        hv=json.loads(halo.read_text());verify(hv['input_sha256'])
        if hv['input_sha256'].get(str(inventory))!=sha(inventory):raise ValueError('load halo/driver inventory mismatch')
        if set(hv['prescribed_control_driver_input_nodes'])!=prescribed:raise ValueError('load halo changes programming input cuts')
        expanded_selection=set(hv['expanded_selected_primitives'])
        if not selected<=expanded_selection:raise ValueError('load halo omits selected driver devices')
        selected=expanded_selection
        reset_nets=[n for n in hv['signal_interfaces'].values() if all(e['direction']=='INPUT' for e in n['inside'])]
        if len(reset_nets)!=1:raise ValueError('unique DCO reset input interface required')
        reset_drivers=[e['cell_key'] for e in reset_nets[0]['outside'] if e['direction']=='OUTPUT']
        if len(reset_drivers)!=1:raise ValueError('unique physical reset driver required')
        driver=next(c for c in hv['added_cells'] if c['cell_key']==reset_drivers[0])
        if driver['master']!='sky130_fd_sc_hs__clkbuf_4':raise ValueError('expected physical reset clock buffer')
        reset_input=driver['pins']['A'];prescribed.add(reset_input)
    private,boundary,cards,omitted=passive_cut(terms,passives,selected,prescribed)
    expanded,masters=full_load_cells(selected,omitted,items)
    # Report the next closure layer separately; do not silently grow this bench.
    inputs={str(p):sha(p) for p in [inventory,metadata,model,Path(__file__).resolve(),Path(__file__).with_name('plan_selected_detector_passive_cut.py'),Path(__file__).with_name('extend_selected_detector_loads.py')]}
    if halo is not None:inputs[str(halo)]=sha(halo)
    verify(inputs)
    save(output,dict(input_sha256=inputs,selected_primitives=sorted(selected),private_unknown_nodes=sorted(private),
        prescribed_control_driver_input_nodes=inv['required_control_driver_input_nodes'],
        prescribed_reset_driver_input=reset_input,required_non_supply_boundary_voltage_nodes=sorted(boundary),
        retained_passive_cards=[passives[i][0] for i in sorted(cards)],omitted_primitives_touching_private_nodes=omitted,
        next_load_closure_cell_masters=masters,next_load_closure_additional_primitives=len(expanded-selected),
        fixed_supply_nodes=sorted(RAILS),capacitor_only_unknowns_preserved=True,control_driver_outputs_unclamped=True,
        shared_node_loads_bounded=False,reset_and_output_load_closure_complete=False,boundary_waveforms_bound=False,
        native_model_ready=False,physical_models_qualified=False,release_ready=False))
    print(json.dumps(dict(selected_primitives=len(selected),private_nodes=len(private),boundary_nodes=len(boundary),retained_passives=len(cards),omitted_primitives=len(omitted),next_load_closure_cell_masters=masters)))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['inventory','metadata','model','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--halo',type=Path)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['inventory','metadata','model','output']),halo=a.halo.resolve() if a.halo else None)
