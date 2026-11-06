"""Add complete omitted load cells to the coherent-clock DCO diagnostic."""
import argparse,json,os
from pathlib import Path
from common_v3 import save,sha,verify
from plan_selected_detector_passive_cut import passive_cut


def run(base,inventory,metadata,model,output):
    if output.exists():raise FileExistsError(output)
    b,i=[json.loads(p.read_text()) for p in [base,inventory]]
    for x in [b,i]:verify(x['input_sha256'])
    if i['input_sha256'].get(str(base))!=sha(base) or any(b['input_sha256'].get(str(p))!=sha(p) for p in [metadata,model]):raise ValueError('same physical load inventory required')
    selected=set(b['selected_primitives'])|{p for r in i['records'] for p in r['complete_primitives']};items={r['instance']:r for r in json.loads(metadata.read_text())['physical_instances']};terms={};passives=[];inside=False
    for line in model.open():
        f=line.split()
        if not f:continue
        if f[0].lower()=='.subckt':inside=f[1]=='IntegerPLL_400MHz_PrototypeTop';continue
        if f[0].lower()=='.ends':inside=False;continue
        if not inside:continue
        if f[0].startswith('Xflat'):terms[f[0]]=f[1:1+len(items[f[0]]['local_primitive_signature'][1])]
        elif f[0][0].upper() in ['R','C']:passives.append((f[0],f[1],f[2]))
    if terms.keys()!=items.keys():raise ValueError('complete physical primitive graph required')
    prescribed=set(b['prescribed_control_driver_input_nodes'])|{b['prescribed_reset_driver_input']}
    private,boundary,cards,omitted=passive_cut(terms,passives,selected,prescribed)
    if not set(b['private_unknown_nodes'])<=private or set(b['selected_primitives'])&omitted.keys():raise ValueError('original physical circuit lost')
    pins=dict(b['input_sha256']);pins.update({str(p):sha(p) for p in [base,inventory,metadata,model,Path(__file__).resolve(),Path(__file__).with_name('plan_selected_detector_passive_cut.py')]});verify(pins)
    result=dict(b,input_sha256=pins,selected_primitives=sorted(selected),private_unknown_nodes=sorted(private),required_non_supply_boundary_voltage_nodes=sorted(boundary),retained_passive_cards=[passives[k][0] for k in sorted(cards)],omitted_primitives_touching_private_nodes=omitted,added_load_cells=i['records'],added_load_primitives=sorted(selected-set(b['selected_primitives'])),stateful_loads_retained=True,stateful_boundary_histories_qualified=False,scope='one complete physical load-cell layer; exterior data/reset histories remain conditional')
    save(output,result);print(json.dumps(dict(selected_primitives=len(selected),added_primitives=len(result['added_load_primitives']),private_unknowns=len(private),retained_passives=len(cards),remaining_omitted_primitives=len(omitted),boundary_nodes=len(boundary))))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['base','inventory','metadata','model','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();os.sched_setaffinity(0,{29});run(*(getattr(a,n).resolve() for n in ['base','inventory','metadata','model','output']))
