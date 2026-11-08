"""Bind physical conditional ports to the identical full native model, before waveform replay."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify

def plan(bindings,full_nodes,full_ports):
    external=bindings['externally_driven_ports'];observed=bindings['observation_only_ports']
    if set(observed)!={'PLLOUT'} or 'PLLOUT' in external:raise ValueError('PLLOUT must be observation-only')
    if set(external)&set(observed):raise ValueError('driven and observed roles overlap')
    result={}
    for role,mapping in [('externally_driven',external),('observation_only',observed)]:
        for physical,conditional in mapping.items():
            if physical not in full_nodes:raise ValueError('physical node absent from full model: '+physical)
            native=full_nodes[physical];reference=native if native in full_ports else 'XDUT:'+native
            result[physical]=dict(role=role,conditional_formal_port=conditional,full_native_node=reference,expected_RAW_variable='V('+reference.upper()+')')
    return result

def bind_variables(records,names):
    indices={}
    for i,name in enumerate(names):
        key=name.lower()
        if key in indices:raise ValueError('duplicate RAW variable')
        indices[key]=i
    missing=[];bound={}
    for physical,record in records.items():
        key=record['expected_RAW_variable'].lower()
        if key not in indices:missing.append(physical)
        else:bound[physical]=dict(**record,RAW_index=indices[key])
    if missing:raise ValueError('missing required RAW voltages: '+repr(missing[:10]))
    if any(r['role']=='externally_driven' for n,r in bound.items() if n=='PLLOUT'):raise ValueError('output forcing forbidden')
    return bound

def run(conditional,full,output):
    receipts=[p/'assessment.json' for p in [conditional,full]];c,f=[json.loads(p.read_text()) for p in receipts]
    for r in [c,f]:verify(r['input_sha256']);verify(r['artifacts'])
    if not c['PLLOUT_not_externally_driven'] or not c['reversible_physical_node_mapping']:raise ValueError('checked reversible free-output model required')
    # Both preparations must trace to exactly the same full model file.
    full_model=full/'model.spice'
    if c['input_sha256'].get(str(full_model))!=sha(full_model):raise ValueError('identical full native model provenance required')
    bindings_file=conditional/'bindings.json';nodes_file=full/'nodes.json';bindings=json.loads(bindings_file.read_text());nodes=json.loads(nodes_file.read_text())
    root=[s.split() for s in full_model.read_text().splitlines() if s.startswith('.subckt ') and not s.split()[1].startswith('__openpll_')]
    if len(root)!=1:raise ValueError('one full model root required')
    records=plan(bindings,nodes,set(root[0][2:]));pins={str(p):sha(p) for p in [*receipts,bindings_file,nodes_file,full_model,Path(__file__).resolve()]};verify(pins)
    output.mkdir(parents=True,exist_ok=False);save(output/'ports.json',records)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'ports.json'):sha(output/'ports.json')},all_conditional_physical_ports_present_in_identical_full_model=True,externally_driven_port_count=sum(r['role']=='externally_driven' for r in records.values()),observation_only_ports=['PLLOUT'],PLLOUT_forcing_forbidden=True,reference_instance='XDUT',native_waveform_header_binding_verified=False,completed_boundary_waveforms_available=False,environment_validated=False,replay_executed=False,model_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['conditional','full','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['conditional','full','output']))
