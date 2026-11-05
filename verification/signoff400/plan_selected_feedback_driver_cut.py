"""Retain the real feedback flip-flop in the loaded detector partition.

Move prescribed feedback voltage from Q to its physical CLK/D/RESET_B inputs.
Keep all incident passives and floating capacitor-only unknowns; expose every
new exterior voltage and omitted primitive load as an unqualified obligation.
"""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from plan_selected_detector_passive_cut import passive_cut
from compare_prototype_physical_primitive_graphs import Union
from extend_selected_detector_loads import full_load_cells


def stimulus_roles(original,driver):
    result=dict(original);q=driver['pins']['Q']
    if result.pop('feedback')!=q:raise ValueError('original prescribed feedback must be the selected driver Q')
    for role,pin in [('feedback_ff_clock','CLK'),('feedback_ff_data','D'),('feedback_ff_reset','RESET_B')]:result[role]=driver['pins'][pin]
    if q in result.values() or len(set(result.values()))!=len(result):raise ValueError('driver Q cannot be prescribed; independent physical input cuts required')
    return result


def run(base,stimuli,driver_inputs,metadata,model,output):
    if output.exists():raise FileExistsError(output)
    bv,sv,dv=[json.loads(p.read_text()) for p in [base,stimuli,driver_inputs]]
    for v in [bv,sv,dv]:verify(v['input_sha256'])
    for p in [stimuli,metadata,model]:
        if bv['input_sha256'].get(str(p))!=sha(p):raise ValueError('base partition physical/stimulus identity mismatch')
    if dv['input_sha256'].get(str(metadata))!=sha(metadata):raise ValueError('feedback driver physical identity mismatch')
    driver=dv['feedback_driver'];selected=set(bv['selected_primitives'])
    if selected&set(driver['primitives']):raise ValueError('driver must be an independent newly retained complete cell')
    selected.update(driver['primitives']);drives=stimulus_roles(sv['prescribed_voltage_roles'],driver)
    observed=dict(sv['observed_unknown_roles'],feedback_driver_Q=driver['pins']['Q'])
    if set(drives.values())&set(observed.values()):raise ValueError('observed output voltage clamp forbidden')
    items={i['instance']:i for i in json.loads(metadata.read_text())['physical_instances']};terms={};passives=[];inside=False
    for line in model.open():
        f=line.split()
        if not f:continue
        if f[0].lower()=='.subckt':inside=f[1]=='IntegerPLL_400MHz_PrototypeTop';continue
        if f[0].lower()=='.ends':inside=False;continue
        if not inside:continue
        if f[0].startswith('Xflat'):
            count=len(items[f[0]]['local_primitive_signature'][1]);terms[f[0]]=f[1:count+1]
        elif f[0][0].upper() in ['R','C']:passives.append((f[0],f[1],f[2]))
    if terms.keys()!=items.keys():raise ValueError('complete native primitive graph required')
    private,boundary,cards,omitted=passive_cut(terms,passives,selected,drives.values())
    wires=Union()
    for name,a,b in passives:
        if name.startswith('R'):wires.join(a,b)
    q=driver['pins']['Q'];q_loads={name:nodes for name,nodes in omitted.items() if any(wires.find(n)==wires.find(q) for n in nodes)}
    selected,load_masters=full_load_cells(selected,q_loads,items)
    private,boundary,cards,omitted=passive_cut(terms,passives,selected,drives.values())
    if any(wires.find(n)==wires.find(q) for n in boundary):raise ValueError('feedback driver output must not be resistively clamped by an exterior voltage')
    if not set(observed.values())<=private:raise ValueError('all observations must remain circuit unknowns')
    pins=dict(bv['input_sha256']);pins.update({str(p):sha(p) for p in [base,driver_inputs,Path(__file__).resolve(),Path(__file__).with_name('plan_selected_detector_passive_cut.py')]})
    output.mkdir(parents=True);ports=output/'stimulus_ports.json';spins=dict(sv['input_sha256'],**{str(driver_inputs):sha(driver_inputs),str(Path(__file__).resolve()):sha(Path(__file__))})
    save(ports,dict(input_sha256=spins,prescribed_voltage_roles=drives,observed_unknown_roles=observed,
        physical_feedback_driver_retained=True,driver_output_voltage_prescribed=False,
        driver_input_stimuli_qualified=False,release_ready=False));pins[str(ports)]=sha(ports);verify(pins)
    save(output/'plan.json',dict(input_sha256=pins,selected_primitives=sorted(selected),private_unknown_nodes=sorted(private),
        required_non_supply_boundary_voltage_nodes=sorted(boundary),retained_passive_cards=[passives[i][0] for i in sorted(cards)],
        omitted_primitives_touching_private_nodes=omitted,fixed_supply_nodes=bv['fixed_supply_nodes'],
        added_feedback_driver_primitives=driver['primitives'],added_feedback_driver_output_load_masters=load_masters,
        feedback_Q_resistive_component_has_no_voltage_boundary=True,capacitor_only_unknowns_preserved=True,
        physical_feedback_driver_output_unclamped=True,feedback_driver_input_waveforms_supplied=False,
        boundary_waveforms_bound=False,shared_node_loads_bounded=False,native_model_ready=False,
        physical_models_qualified=False,release_ready=False))
    print(json.dumps(dict(selected_primitives=len(selected),private_unknowns=len(private),boundary_nodes=len(boundary),retained_passives=len(cards),omitted_primitive_loads=len(omitted),driver_output_load_masters=load_masters)))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['base','stimuli','driver-inputs','metadata','model','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n.replace('-','_')).resolve() for n in ['base','stimuli','driver-inputs','metadata','model','output']))
