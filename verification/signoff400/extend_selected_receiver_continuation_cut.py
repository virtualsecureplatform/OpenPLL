"""Retain the physical next-stage synchronizers and intervening buffers."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from plan_selected_detector_passive_cut import passive_cut


def run(base,stimuli,continuation,metadata,model,output):
    output.mkdir(parents=True,exist_ok=False)
    b,s,c=[json.loads(p.read_text()) for p in [base,stimuli,continuation]]
    for v in [b,s,c]:verify(v['input_sha256'])
    for p in [stimuli,metadata,model]:
        if b['input_sha256'].get(str(p))!=sha(p):raise ValueError('same base physical model/stimulus required')
    if c['input_sha256'].get(str(metadata))!=sha(metadata):raise ValueError('same continuation geometry required')
    selected=set(b['selected_primitives']);observed=dict(s['observed_unknown_roles']);drives=dict(s['prescribed_voltage_roles']);clocks=set()
    for row in c['records']:
        role='dn' if row['port']=='BBPD[0]' else 'up'
        if row['port'] not in ['BBPD[0]','BBPD[1]']:raise ValueError('known BBPD role required')
        part=row['continuation'];ends=part['sequential_endpoints']
        if len(ends)!=1 or ends[0]['input_pin']!='D':raise ValueError('unique next data stage required')
        endpoint=ends[0]['cell']
        if endpoint['pins']['RESET_B']!=drives['synchronizer_reset_n']:raise ValueError('unsupported new reset domain')
        clocks.add(endpoint['pins']['CLK'])
        for cell in part['combinational_cells']+[endpoint]:selected.update(cell['primitives'])
        observed['second_sync_'+role]=endpoint['pins']['Q'];observed['second_data_'+role]=endpoint['pins']['D']
    if len(clocks)!=1:raise ValueError('one next clock domain required')
    drives['second_synchronizer_clock']=next(iter(clocks))
    if set(drives.values())&set(observed.values()):raise ValueError('output clamp forbidden')
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
    if terms.keys()!=items.keys():raise ValueError('complete physical primitive graph required')
    private,boundary,cards,omitted=passive_cut(terms,passives,selected,drives.values())
    if not set(observed.values())<=private:raise ValueError('all observed voltages must remain unknown')
    pins=dict(b['input_sha256']);pins.update(c['input_sha256']);pins.update({str(p):sha(p) for p in [base,stimuli,continuation,Path(__file__).resolve(),Path(__file__).with_name('plan_selected_detector_passive_cut.py')]});verify(pins)
    sv=dict(s,input_sha256=pins,prescribed_voltage_roles=drives,observed_unknown_roles=observed);save(output/'stimulus_ports.json',sv)
    pp=dict(pins,**{str(output/'stimulus_ports.json'):sha(output/'stimulus_ports.json')})
    result=dict(input_sha256=pp,selected_primitives=sorted(selected),private_unknown_nodes=sorted(private),required_non_supply_boundary_voltage_nodes=sorted(boundary),retained_passive_cards=[passives[i][0] for i in sorted(cards)],omitted_primitives_touching_private_nodes=omitted,fixed_supply_nodes=b['fixed_supply_nodes'],added_primitives=sorted(selected-set(b['selected_primitives'])),capacitor_only_unknowns_preserved=True,second_stage_clock_prescribed_at_physical_pin=True,downstream_loading_bounded=False,physical_models_qualified=False,release_ready=False)
    save(output/'plan.json',result)
    print(json.dumps(dict(selected_primitives=len(selected),added_primitives=len(result['added_primitives']),retained_passives=len(cards),omitted_primitive_loads=len(omitted))))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['base','stimuli','continuation','metadata','model','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['base','stimuli','continuation','metadata','model','output']))
