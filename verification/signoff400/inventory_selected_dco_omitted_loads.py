"""Inventory complete physical cells behind residual omitted DCO primitive loads."""
import argparse,json
from collections import defaultdict,Counter
from pathlib import Path
from common_v3 import save,sha,verify


def run(plan,metadata,output):
    if output.exists():raise FileExistsError(output)
    b=json.loads(plan.read_text());verify(b['input_sha256'])
    if b['input_sha256'].get(str(metadata))!=sha(metadata):raise ValueError('same physical metadata required')
    items=json.loads(metadata.read_text())['physical_instances'];groups=defaultdict(list);by_name={}
    for item in items:
        key=json.dumps([item['physical_hierarchy_identity'],item['leaf_master']],sort_keys=True,separators=(',',':'));groups[key].append(item);by_name[item['instance']]=key
    selected=set(b['selected_primitives']);omitted=b['omitted_primitives_touching_private_nodes']
    if set(omitted)&selected or not set(omitted)<=by_name.keys():raise ValueError('omitted primitive identity mismatch')
    touched=defaultdict(set)
    for name,nodes in omitted.items():touched[by_name[name]].update(nodes)
    records=[];node_counts=defaultdict(Counter)
    for key,nodes in sorted(touched.items()):
        cells=groups[key];primitives={x['instance'] for x in cells}
        if primitives&selected:raise ValueError('base selection partially retains an omitted physical cell')
        master=cells[0]['leaf_master'];record=dict(cell_key=key,master=master,complete_primitives=sorted(primitives),omitted_incident_primitives=sorted(primitives&omitted.keys()),touching_private_nodes=sorted(nodes));records.append(record)
        for node in nodes:node_counts[node][master]+=1
    result=dict(input_sha256={str(p):sha(p) for p in [plan,metadata,Path(__file__).resolve()]},remaining_omitted_primitive_count=len(omitted),complete_cell_count=len(records),complete_cell_additional_primitives=sum(len(r['complete_primitives']) for r in records),cell_master_counts=dict(Counter(r['master'] for r in records)),private_node_load_cells={n:dict(c) for n,c in sorted(node_counts.items())},records=records,scope='structural load obligations; counts are not capacitance, sensitivity or error bounds',loads_bounded=False,full_boundary_forcing_covered=False,release_ready=False)
    save(output,result);print(json.dumps({k:result[k] for k in ['remaining_omitted_primitive_count','complete_cell_count','complete_cell_additional_primitives','cell_master_counts','private_node_load_cells']}))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['plan','metadata','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['plan','metadata','output']))
