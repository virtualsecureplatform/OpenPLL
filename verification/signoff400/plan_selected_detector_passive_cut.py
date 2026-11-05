"""Plan a conditional detector solve while preserving capacitor-only unknowns.

The result is not a runnable or qualified bench. External active terminals
require explicit waveforms; omitted primitive loads touching private nodes
remain open obligations. Floating capacitor nodes are never grounded.
"""
import argparse
from collections import defaultdict,deque
import json
from pathlib import Path
from common_v3 import save,sha,verify

RAILS={'0','VPWR','VGND','VPB','VNB'}


def passive_cut(terms,passives,selected):
    if not selected or not selected<=terms.keys():raise ValueError('unknown selected primitive')
    seeds={n for name in selected for n in terms[name]}-RAILS
    external={n for name in terms.keys()-selected for n in terms[name]}-seeds-RAILS
    adjacency=defaultdict(list)
    for index,(_,a,b) in enumerate(passives):
        adjacency[a].append(index);adjacency[b].append(index)
    private=set(seeds);boundary=set();cards=set();queue=deque(sorted(seeds))
    while queue:
        node=queue.popleft()
        for index in adjacency[node]:
            cards.add(index)
            _,a,b=passives[index]
            for other in [a,b]:
                if other in RAILS or other in private:continue
                if other in external:boundary.add(other)
                else:private.add(other);queue.append(other)
    omitted={name:sorted(set(nodes)&private) for name,nodes in terms.items()
             if name not in selected and set(nodes)&private}
    return private,boundary,cards,omitted


def run(detector,receivers,roles,metadata,model,output):
    if output.exists():raise FileExistsError(output)
    dv,rv,cv=[json.loads(p.read_text()) for p in [detector,receivers,roles]]
    for v in [dv,rv,cv]:verify(v['input_sha256'])
    if rv['input_sha256'].get(str(detector))!=sha(detector):raise ValueError('detector identity mismatch')
    if cv['input_sha256'].get(str(receivers))!=sha(receivers):raise ValueError('receiver identity mismatch')
    for p in [metadata,model]:
        if dv['input_sha256'].get(str(p))!=sha(p):raise ValueError('physical identity mismatch')
    pins={str(p):sha(p) for p in [detector,receivers,roles,metadata,model,Path(__file__).resolve()]}
    items={i['instance']:i for i in json.loads(metadata.read_text())['physical_instances']}
    selected=set(dv['selected_detector_primitives'])|set(rv['selected_receiver_primitives'])
    for cells in rv['downstream_sequential_output_cells'].values():
        for cell in cells:selected.update(cell['primitives'])
    diode_cells={k for k,c in cv['cells'].items() if c['master']=='sky130_fd_sc_hs__diode_2'}
    for key in diode_cells:selected.update(cv['cells'][key]['primitives'])
    terms={};passives=[];inside=False
    for line in model.open():
        f=line.split()
        if not f:continue
        if f[0].lower()=='.subckt':inside=f[1]=='IntegerPLL_400MHz_PrototypeTop';continue
        if f[0].lower()=='.ends':inside=False;continue
        if not inside:continue
        if f[0].startswith('Xflat'):
            count=len(items[f[0]]['local_primitive_signature'][1]);terms[f[0]]=f[1:count+1]
        elif f[0][0].upper() in ['R','C']:passives.append((f[0],f[1],f[2]))
    if terms.keys()!=items.keys():raise ValueError('native primitive coverage mismatch')
    private,boundary,cards,omitted=passive_cut(terms,passives,selected)
    result=dict(input_sha256=pins,selected_primitives=sorted(selected),private_unknown_nodes=sorted(private),
                required_non_supply_boundary_voltage_nodes=sorted(boundary),
                retained_passive_cards=[passives[i][0] for i in sorted(cards)],
                capacitor_only_unknowns_preserved=True,omitted_primitives_touching_private_nodes=omitted,
                fixed_supply_nodes=sorted(RAILS),boundary_waveforms_bound=False,
                shared_node_loads_bounded=False,native_model_ready=False,
                physical_models_qualified=False,release_ready=False)
    verify(pins);save(output,result)
    print(json.dumps(dict(selected_primitives=len(selected),private_unknowns=len(private),
                         prescribed_boundary_nodes=len(boundary),retained_passives=len(cards),
                         omitted_primitive_load_obligations=len(omitted))))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['detector','receivers','roles','metadata','model','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['detector','receivers','roles','metadata','model','output']))
