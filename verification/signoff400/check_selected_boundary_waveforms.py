"""Match every conditional analog boundary to a unique saved native voltage.

Coverage is a prerequisite for replay, not validation of the boundary assumptions.
"""
import argparse,json
from pathlib import Path
from common_v3 import sha,save


def bind(boundaries,names):
    normalized={}
    for i,name in enumerate(names):
        key=name.lower()
        if key in normalized:raise ValueError('duplicate waveform variable')
        normalized[key]=i
    result={};missing=[];ambiguous=[]
    if len(set(boundaries))!=len(boundaries):raise ValueError('duplicate boundary node')
    for node in boundaries:
        keys=[f'v({node})'.lower(),f'v(xpll:{node})'.lower()]
        found=[k for k in keys if k in normalized]
        if len(found)==1:result[node]=dict(variable=found[0],index=normalized[found[0]])
        elif found:ambiguous.append(node)
        else:missing.append(node)
    return dict(bindings=result,missing=missing,ambiguous=ambiguous,all_bound=not missing and not ambiguous)


def run(plan,raw,output):
    names=[];declared=None
    with raw.open() as f:
        for line in f:
            if line.startswith('No. Variables:'):declared=int(line.split(':',1)[1])
            if line.strip()=='Variables:':break
        for line in f:
            if line.strip()=='Values:':break
            ix,name,kind=line.split()
            if int(ix)!=len(names):raise ValueError('invalid waveform variable order')
            names.append(name)
    if len(names)!=declared:raise ValueError('incomplete waveform variable header')
    nodes=json.loads(plan.read_text())['required_non_supply_boundary_voltage_nodes']
    result=bind(nodes,names);result.update(input_sha256={str(plan):sha(plan)},waveform=str(raw),waveform_header_variables=len(names),boundary_nodes=len(nodes),boundary_waveforms_validated=False,loaded_model_qualified=False,release_ready=False)
    if output.exists():raise FileExistsError(output)
    save(output,result);print(json.dumps({k:v for k,v in result.items() if k not in ['bindings','input_sha256']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--raw',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.plan.resolve(),a.raw.resolve(),a.output.resolve())
