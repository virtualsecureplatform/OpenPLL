"""Export the selected analog partition; all boundary sources require native replay.

No native run is eligible until every referenced PWL file is present and verified.
Boundary-only capacitances are omitted only from the prescribed-voltage solve;
this export makes no exterior-current or cross-code loading qualification claim.
"""
import argparse,json
from pathlib import Path
from common_v3 import sha,save


def retain_card(line,selected,private):
    fields=line.split()
    if not fields:return False
    kind=fields[0][0].upper()
    if kind=='X':return fields[0].lower() in selected
    if kind=='R':return True
    if kind=='C':return any(n.lower() in private for n in fields[1:3])
    if kind in ['*','.']:return True
    raise ValueError('unsupported top-level card '+fields[0])


def export(model,plan,coverage,output):
    d=json.loads(plan.read_text());c=json.loads(coverage.read_text())
    if not c['all_bound'] or c['boundary_nodes']!=len(d['required_non_supply_boundary_voltage_nodes']):raise ValueError('complete boundary waveform binding required')
    if c['input_sha256'].get(str(plan))!=sha(plan):raise ValueError('boundary coverage belongs to another plan')
    selected={x.lower() for x in d['selected_primitives']};private={x.lower() for x in d['private_unknown_nodes']}
    known=private|{x.lower() for x in d['required_non_supply_boundary_voltage_nodes']}|{x.lower() for x in d['fixed_supply_nodes']}
    output.mkdir(parents=True,exist_ok=False);counts=dict(X=0,R=0,C=0);discarded=0;seen=set();inside=False;found=False;unknown=set();ports={}
    with model.open() as src,(output/'devices.spice').open('w') as dst:
        for line in src:
            fields=line.split()
            if fields[:2]==['.subckt','IntegerPLL_400MHz_PrototypeTop']:
                if found:raise ValueError('duplicate selected top')
                inside=True;found=True;continue
            if inside and fields and fields[0].lower()=='.ends':inside=False;continue
            if not inside:
                if fields and fields[0].lower()=='.subckt':
                    pins=[]
                    for token in fields[2:]:
                        if '=' in token or token.lower()=='params:':break
                        pins.append(token)
                    ports[fields[1].lower()]=len(pins)
                dst.write(line);continue
            if not retain_card(line,selected,private):
                if fields and fields[0].upper().startswith('C'):discarded+=1
                continue
            dst.write(line)
            if not fields:continue
            kind=fields[0][0].upper()
            if kind not in counts:continue
            counts[kind]+=1
            if kind=='X':
                seen.add(fields[0].lower())
                models=[(i,t.lower()) for i,t in enumerate(fields[1:],1) if t.lower() in ports]
                if len(models)!=1:raise ValueError('unresolved primitive wrapper')
                index,master=models[0]
                if index!=ports[master]+1:raise ValueError('wrapper terminal count mismatch')
                nodes=fields[1:index]
            else:nodes=fields[1:3]
            unknown.update(n for n in nodes if n.lower() not in known)
    if not found or seen!=selected or unknown:raise ValueError(f'incomplete partition: missing {len(selected-seen)}, unknown nodes {sorted(unknown)[:8]}')
    boundaries=d['required_non_supply_boundary_voltage_nodes']
    with (output/'boundary_sources.spice').open('w') as f:
        for i,node in enumerate(boundaries):f.write(f'Vboundary{i} {node} 0 PWL FILE "{output}/boundary_{i}.pwl"\n')
    save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [model,plan,coverage,Path(__file__).resolve()]},artifacts={str(p):sha(p) for p in [output/'devices.spice',output/'boundary_sources.spice']},retained=counts,omitted_boundary_only_capacitors=discarded,required_boundary_files=len(boundaries),boundary_waveform_files_generated=False,native_model_ready=False,diagnostic=True,release_ready=False))
    print(json.dumps(dict(retained=counts,boundary_only_capacitors=discarded,boundary_sources=len(boundaries))))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['model','plan','coverage','output']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();export(a.model.resolve(),a.plan.resolve(),a.coverage.resolve(),a.output.resolve())
