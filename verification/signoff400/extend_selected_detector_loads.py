"""Add one complete physical-cell layer of omitted detector receiver loads.

Recompute the passive cut without grounding floating nodes. Newly exposed
loads and exterior voltage obligations remain explicit and unqualified.
"""
import argparse,json
from collections import defaultdict,Counter
from pathlib import Path
from common_v3 import save,sha,verify
from plan_selected_detector_passive_cut import passive_cut


def full_load_cells(selected,omitted,items):
    if not set(omitted)<=items.keys() or set(omitted)&selected:raise ValueError('invalid omitted primitive identities')
    cells=defaultdict(set);by_name={}
    for name,item in items.items():
        key=json.dumps([item['physical_hierarchy_identity'],item['leaf_master']],sort_keys=True,separators=(',',':'))
        cells[key].add(name);by_name[name]=key
    keys={by_name[n] for n in omitted}
    additions=set().union(*(cells[k] for k in keys)) if keys else set()
    masters=Counter(items[next(iter(cells[k]))]['leaf_master'] for k in keys)
    return selected|additions,dict(masters)


def run(base,stimuli,metadata,model,output):
    if output.exists():raise FileExistsError(output)
    b=json.loads(base.read_text());sv=json.loads(stimuli.read_text())
    verify(b['input_sha256']);verify(sv['input_sha256'])
    for p in [stimuli,metadata,model]:
        if b['input_sha256'].get(str(p))!=sha(p):raise ValueError('base physical/stimulus identity mismatch')
    pins=dict(b['input_sha256']);pins.update({str(p):sha(p) for p in [base,Path(__file__).resolve(),Path(__file__).with_name('plan_selected_detector_passive_cut.py')]})
    items={i['instance']:i for i in json.loads(metadata.read_text())['physical_instances']}
    selected,masters=full_load_cells(set(b['selected_primitives']),b['omitted_primitives_touching_private_nodes'],items)
    terms={};passives=[];inside=False
    for line in model.open():
        f=line.split()
        if not f:continue
        if f[0].lower()=='.subckt':inside=f[1]=='IntegerPLL_400MHz_PrototypeTop';continue
        if f[0].lower()=='.ends':inside=False;continue
        if not inside:continue
        if f[0].startswith('Xflat'):
            if f[0] in terms:raise ValueError('duplicate physical primitive')
            count=len(items[f[0]]['local_primitive_signature'][1]);terms[f[0]]=f[1:count+1]
        elif f[0][0].upper() in ['R','C']:passives.append((f[0],f[1],f[2]))
    if terms.keys()!=items.keys():raise ValueError('incomplete native physical primitive graph')
    private,boundary,cards,omitted=passive_cut(terms,passives,selected,sv['prescribed_voltage_roles'].values())
    if not set(sv['observed_unknown_roles'].values())<=private:raise ValueError('expanded load cut clamps an observed output')
    result=dict(input_sha256=pins,selected_primitives=sorted(selected),private_unknown_nodes=sorted(private),
        required_non_supply_boundary_voltage_nodes=sorted(boundary),retained_passive_cards=[passives[i][0] for i in sorted(cards)],
        added_physical_cell_masters=masters,added_primitives=sorted(selected-set(b['selected_primitives'])),
        capacitor_only_unknowns_preserved=True,omitted_primitives_touching_private_nodes=omitted,
        fixed_supply_nodes=b['fixed_supply_nodes'],boundary_waveforms_bound=False,
        shared_node_loads_bounded=False,native_model_ready=False,physical_models_qualified=False,release_ready=False)
    verify(pins);save(output,result)
    print(json.dumps(dict(selected_primitives=len(selected),private_unknowns=len(private),boundary_nodes=len(boundary),retained_passives=len(cards),added_cells=masters,remaining_primitive_loads=len(omitted))))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['base','stimuli','metadata','model','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['base','stimuli','metadata','model','output']))
