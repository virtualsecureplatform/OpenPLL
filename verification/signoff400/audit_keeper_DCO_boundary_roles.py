"""Resolve actual exterior primitive terminal roles at the flat DCO boundary."""
import argparse
import json
from collections import Counter,defaultdict
from pathlib import Path
from common_v3 import save,sha,verify
from native_spice_comments import strip_floating_annotation

def run(flat,boundary,output):
    receipt=boundary/'assessment.json'; a=json.loads(receipt.read_text())
    verify(a['input_sha256']); verify(a['artifacts'])
    spice=flat/'capacitance.spice'; detail=boundary/'boundary.json'
    if a['input_sha256'].get(str(spice))!=sha(spice):raise ValueError('same flat source required')
    pins={str(p):sha(p) for p in [receipt,detail,spice,Path(__file__).resolve(),Path(__file__).with_name('native_spice_comments.py')]}
    b=json.loads(detail.read_text()); selected=set(b['selected_primitives']); shared=set(b['shared_primitive_nodes']); rails={'VPWR','VGND'}
    roles=defaultdict(list); devices={}
    for line in spice.open():
        f=strip_floating_annotation(line).split()
        if not f or not f[0].startswith('X') or f[0] in selected:continue
        j=next((i for i,t in enumerate(f) if '=' in t),len(f))-1
        model=f[j];nodes=f[1:j]
        if ('nfet' in model or 'pfet' in model) and len(nodes)!=4:raise ValueError('four terminal MOS required')
        devices[f[0]]=dict(model=model,nodes=nodes,original_card=strip_floating_annotation(line).strip())
        for i,n in enumerate(nodes):
            if n in shared-rails:roles[n].append(dict(device=f[0],model=model,terminal=i,role=['drain','gate','source','body'][i] if 'nfet' in model or 'pfet' in model else 'diode_'+str(i)))
    driver_pattern=Counter({('sky130_fd_pr__nfet_01v8_lvt','drain'):1,('sky130_fd_pr__nfet_01v8_lvt','source'):1,('sky130_fd_pr__pfet_01v8','drain'):1,('sky130_fd_pr__pfet_01v8','source'):1})
    classifications={}; drivers=[]; errors=[]
    for node in sorted(shared-rails):
        entries=roles[node]; pattern=Counter((e['model'],e['role']) for e in entries)
        if pattern==driver_pattern:
            ids=sorted({e['device'] for e in entries}); gates={devices[n]['nodes'][1] for n in ids}
            # Parallel source/drain reversals are native separate cards, retained verbatim.
            if len(gates)!=1 or any(set(devices[n]['nodes'][::2])!={node,'VGND' if 'nfet' in devices[n]['model'] else 'VPWR'} for n in ids):
                errors.append(node); continue
            classifications[node]='exterior_inverter_output';drivers.extend(ids)
        elif node=='PLLOUT' and all(e['role']=='gate' or e['model']=='sky130_fd_pr__diode_pw2nd_05v5' for e in entries):classifications[node]='oscillator_output_with_exterior_gate_and_diode_loads'
        elif node.endswith('_0.RESET_N'):classifications[node]='reset_with_exterior_driver_gate_and_diode_connections'
        else:errors.append(node)
    if errors or len(classifications)!=len(shared-rails):raise ValueError('unresolved boundary roles: '+repr(errors))
    direct={e['device'] for entries in roles.values() for e in entries}
    verify(pins);output.mkdir(parents=True,exist_ok=False)
    save(output/'roles.json',dict(classifications=classifications,terminal_roles=dict(roles),direct_exterior_devices={n:devices[n] for n in sorted(direct)}))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'roles.json'):sha(output/'roles.json')},boundary_class_counts=dict(Counter(classifications.values())),explicit_supply_nodes=sorted(shared & rails),direct_exterior_primitive_count=len(direct),control_driver_card_count=len(set(drivers)),control_drivers_have_single_input_and_only_rail_output_diffusions=True,direct_exterior_devices_form_closed_subcircuit=False,circuit_partitioned=False,boundary_loading_qualified=False,model_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','boundary','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['flat','boundary','output']))
