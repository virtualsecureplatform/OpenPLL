"""Find prescribed voltage boundaries resistively connected to retained state outputs."""
import argparse,json
from collections import defaultdict
from pathlib import Path
from common_v3 import save,sha,verify
from compare_prototype_physical_primitive_graphs import Union
from audit_selected_dco_history_inputs import sources


def run(inventory,plan,model,case,output):
    if output.exists():raise FileExistsError(output)
    i,p,m=[json.loads(x.read_text()) for x in [inventory,plan,case/'manifest.json']]
    for x in [i,p,m]:verify(x['input_sha256'])
    if any(x['input_sha256'].get(str(model))!=sha(model) for x in [i,p,m]) or m['input_sha256'].get(str(plan))!=sha(plan):raise ValueError('same actual native physical model and plan required')
    selected=set(p['selected_primitives']);union=Union()
    for line in model.open():
        f=line.split()
        if f and f[0][0].upper()=='R':union.join(f[1],f[2])
    by_component=defaultdict(list)
    for node,(name,value) in sources(case/'sources.spice').items():by_component[union.find(node)].append(dict(node=node,source=name,value=value))
    records=[]
    for cell in i['records']:
        if not set(cell['primitives'])<=selected:continue
        node=cell['pins']['Q'];cuts=by_component[union.find(node)]
        records.append(dict(master=cell['master'],primitives=cell['primitives'],output_node=node,resistive_component=union.find(node),prescribed_voltage_cuts=cuts))
    files=[inventory,plan,model,case/'manifest.json',case/'sources.spice',Path(__file__).resolve(),Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py'),Path(__file__).with_name('audit_selected_dco_history_inputs.py')]
    affected=[r for r in records if r['prescribed_voltage_cuts']]
    save(output,dict(input_sha256={str(x):sha(x) for x in files},records=records,state_outputs_checked=len(records),state_outputs_with_prescribed_R_boundaries=len(affected),scope='retained output boundary audit; no assertion that the prescribed levels caused DC failure',DC_failure_cause_identified=False,driver_loading_qualified=False,release_ready=False));print(json.dumps(affected))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['inventory','plan','model','case','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['inventory','plan','model','case','output']))
