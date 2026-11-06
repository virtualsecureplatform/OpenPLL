"""Count physical state and tri-state cells before making DC initialization assumptions."""
import argparse,json
from collections import defaultdict,Counter
from pathlib import Path
from common_v3 import save,sha,verify


def run(plan,metadata,output):
    if output.exists():raise FileExistsError(output)
    p=json.loads(plan.read_text());verify(p['input_sha256'])
    if p['input_sha256'].get(str(metadata))!=sha(metadata):raise ValueError('same physical metadata required')
    selected=set(p['selected_primitives']);groups=defaultdict(list)
    for item in json.loads(metadata.read_text())['physical_instances']:
        key=json.dumps([item['physical_hierarchy_identity'],item['leaf_master']],sort_keys=True,separators=(',',':'));groups[key].append(item)
    records=[]
    for key,items in groups.items():
        names={i['instance'] for i in items}
        if not names&selected:continue
        if not names<=selected:raise ValueError('partially selected physical cell')
        records.append(dict(cell_key=key,master=items[0]['leaf_master'],primitives=sorted(names)))
    if {n for r in records for n in r['primitives']}!=selected:raise ValueError('selected primitive coverage mismatch')
    counts=dict(Counter(r['master'] for r in records));state=[r for r in records if any(s in r['master'] for s in ['dfrtp','dfstp','dlxtp'])];tri=[r for r in records if any(s in r['master'] for s in ['einvp','einvn'])]
    result=dict(input_sha256={str(p):sha(p) for p in [plan,metadata,Path(__file__).resolve()]},selected_primitives=len(selected),cell_master_counts=counts,stateful_cell_count=len(state),tristate_cell_count=len(tri),stateful_cells=state,scope='structural inventory only; enabled states, floating nodes and unique DC equilibrium are not proven',reset_implies_unique_DC_state_proven=False,DC_failure_cause_identified=False,release_ready=False)
    save(output,result);print(json.dumps({k:result[k] for k in ['selected_primitives','cell_master_counts','stateful_cell_count','tristate_cell_count']}))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['plan','metadata','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['plan','metadata','output']))
