"""Bind selected-layout detector identity and characterize its extraction boundary.

Extra hierarchical capacitance ports are inventoried, never driven or grounded.
Parent logical bindings are not asserted to be validated physical wire cuts.
"""
import argparse,json,os,sys
from collections import Counter
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from compare_prototype_physical_primitive_graphs import parsed

LOGICAL_PORTS={'REF','CLKDIVR','RESET_N','BBPD[0]','BBPD[1]','VPWR','VGND','VPB','VNB'}


def detector_names(instances):
    names=set()
    for item in instances:
        identity=item['physical_hierarchy_identity']
        if identity and identity[0][2][0]=='IntegerPLL_BBPD':names.add(item['instance'])
    if not names:raise ValueError('selected detector physical hierarchy missing')
    return names


def logical_port_map(ports, bindings):
    signals=LOGICAL_PORTS-{'VPWR','VGND','VPB','VNB'}
    if not signals<=set(ports):raise ValueError('logical detector signal ports missing')
    result={k:k for k in signals}
    for rail in ['VPWR','VGND','VPB','VNB']:
        if rail in ports and bindings[rail]==rail:
            result[rail]=rail
        else:
            matches=[p for p in ports if bindings[p]==rail]
            if len(matches)!=1:raise ValueError('missing or ambiguous parent supply binding: '+rail)
            result[rail]=matches[0]
    return result


def inventory(model,metadata_path,wire,hierarchy,dco_plan,output):
    if output.exists():raise FileExistsError(output)
    pins={str(p):sha(p) for p in [model,metadata_path,wire,hierarchy,dco_plan,Path(__file__).resolve(),Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py')]}
    metadata=json.loads(metadata_path.read_text());items={i['instance']:i for i in metadata['physical_instances']}
    if len(items)!=len(metadata['physical_instances']):raise ValueError('duplicate physical primitive identifiers')
    selected=detector_names(items.values());terms={};inside=False;definitions={}
    with model.open() as f:
        for line in f:
            fields=line.split()
            if not fields:continue
            if fields[0].lower()=='.subckt':
                inside=fields[1]=='IntegerPLL_400MHz_PrototypeTop'
                if not inside:
                    ports=[]
                    for token in fields[2:]:
                        if '=' in token or token.lower()=='params:':break
                        ports.append(token)
                    definitions[fields[1]]=len(ports)
                continue
            if fields[0].lower()=='.ends':inside=False;continue
            if not inside or not fields[0].startswith('Xflat'):continue
            name=fields[0]
            if name not in items or name in terms:raise ValueError('native primitive inventory differs from physical sidecar')
            count=len(items[name]['local_primitive_signature'][1])
            if definitions.get(fields[count+1])!=count:raise ValueError('native wrapper terminal arity mismatch')
            terms[name]=fields[1:count+1]
    if terms.keys()!=items.keys():raise ValueError('complete physical primitive coverage required')
    source_terms={}
    for line in wire.open():
        fields=line.split()
        if not fields or not fields[0].startswith('Xflat'):continue
        name=fields[0];count=len(items[name]['local_primitive_signature'][1])
        if fields[count+1]!=items[name]['local_primitive_signature'][0]:raise ValueError('physical sidecar primitive model mismatch')
        source_terms[name]=fields[1:count+1]
    if source_terms!=terms:raise ValueError('native model and original wire model terminal graphs differ')
    fixed={'0','VPWR','VPB','VGND','VNB'}
    nodes={n for name in selected for n in terms[name]}-fixed
    outside={n for name in terms.keys()-selected for n in terms[name]}-fixed
    shared=nodes&outside
    counts=Counter();remote=set();crossing_R=[];inside=False
    for line in model.open():
        fields=line.split()
        if not fields:continue
        if fields[0].lower()=='.subckt':inside=fields[1]=='IntegerPLL_400MHz_PrototypeTop';continue
        if fields[0].lower()=='.ends':inside=False;continue
        if not inside or fields[0][0].upper() not in ('R','C'):continue
        endpoints=set(fields[1:3]);kind=fields[0][0].upper()
        if endpoints&nodes:
            counts[kind+'_incident']+=1
            if endpoints-nodes-fixed:
                counts[kind+'_crossing']+=1;remote.update(endpoints-nodes-fixed)
                if kind=='R':crossing_R.append(dict(card=fields[0],nodes=fields[1:3],value=fields[3]))
    models=parsed(hierarchy.read_text());ports,_=models['IntegerPLL_BBPD']
    tops=[k for k in models if k.startswith('IntegerPLL_400MHz_PrototypeTop')]
    if len(tops)!=1:raise ValueError('unique physical parent required')
    calls=[r for r in models[tops[0]][1] if r[0]=='instance' and r[2]=='IntegerPLL_BBPD']
    if len(calls)!=1 or len(calls[0][3])!=len(ports):raise ValueError('unique complete detector instance binding required')
    bindings=dict(zip(ports,calls[0][3]));port_map=logical_port_map(ports,bindings);dco=set(json.loads(dco_plan.read_text())['selected_primitives'])
    verify(pins)
    save(output,dict(input_sha256=pins,selected_detector_primitives=sorted(selected),
        detector_primitive_count=len(selected),detector_signal_nodes=sorted(nodes),
        shared_with_other_primitive_nodes=sorted(shared),incident_wire_and_capacitor_counts=dict(counts),
        remote_RC_nodes=sorted(remote),wire_edges_crossing_detector_node_set=crossing_R,
        logical_port_formals=port_map,logical_parent_bindings={k:bindings[port_map[k]] for k in sorted(LOGICAL_PORTS)},
        all_extracted_formal_parent_bindings=bindings,
        additional_hierarchical_ports=sorted(set(ports)-set(port_map.values())),
        extra_hierarchical_ports_are_not_assumed_external_voltage_inputs=True,
        primitives_also_in_current_DCO_partition=sorted(selected&dco),
        physical_clock_and_reset_wire_cuts_validated=False,receiver_loading_validated=False,
        phase_bench_exported=False,physical_models_qualified=False,release_ready=False))
    return len(selected),len(ports),counts


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['model','metadata','wire','hierarchy','dco-plan','output']:p.add_argument('--'+key,required=True,type=Path)
    a=p.parse_args();os.sched_setaffinity(0,{28})
    print(inventory(*(getattr(a,k).resolve() for k in ['model','metadata','wire','hierarchy','dco_plan','output'])))
