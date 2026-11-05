"""Recover the routed BBPD event receiver with actual extracted cell-local capacitance."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import time
from common_v3 import ROOT,save,sha,verify
from compare_mapped_routed_CDC import clock_roots


def identifier(name):
    return name.lstrip("\\")
from bind_prototype_spef_pins_v2 import hierarchy
from prepare_prototype_analog_reference import subcircuits
from resources import lease


def select(module,states):
    cells=module['cells'];normalized={identifier(n):n for n in cells}
    if len(normalized)!=len(cells):raise ValueError('ambiguous routed identifier normalization')
    drivers=defaultdict(list);loads=defaultdict(list)
    for name,cell in cells.items():
        for pin,bits in cell['connections'].items():
            direction=cell['port_directions'][pin]
            if direction not in ('input','output'):raise ValueError('unexpected logic pin direction')
            for bit in bits:(drivers if direction=='output' else loads)[bit].append((name,pin))
    root=clock_roots(module)
    selected_states=[s for s in states if tuple(root(s['clock_bit'])) in (('primary','BBPD',0,0),('primary','BBPD',1,0))]
    if len(selected_states)!=2:raise ValueError('exactly two BBPD event flops required')
    endpoints={normalized[identifier(s['cell'])] for s in selected_states}
    sequential={normalized[identifier(s['cell'])] for s in states}
    primary={b for p in module['ports'].values() if p['direction']=='input' for b in p['bits']}
    selected=set(endpoints);pending=[]
    for name in endpoints:
        c=cells[name]
        pending.extend(b for p,bs in c['connections'].items() if c['port_directions'][p]=='input' for b in bs)
    visited=set();boundaries={}
    while pending:
        bit=pending.pop()
        if bit in visited:continue
        visited.add(bit)
        if isinstance(bit,str):boundaries[bit]='constant';continue
        if bit in primary:boundaries[bit]='primary_input';continue
        source=drivers[bit]
        if len(source)!=1:raise ValueError('missing/multiple routed drivers at bit '+str(bit))
        name,pin=source[0]
        if name in endpoints:continue
        if name in sequential:boundaries[bit]='other_sequential_output';continue
        if name in selected:continue
        selected.add(name);c=cells[name]
        pending.extend(b for p,bs in c['connections'].items() if c['port_directions'][p]=='input' for b in bs)
    outputs={b for n in endpoints for p,bs in cells[n]['connections'].items() if cells[n]['port_directions'][p]=='output' for b in bs}
    incident={b for n in selected for bs in cells[n]['connections'].values() for b in bs}
    omitted=[dict(bit=b,receiver=n,pin=p) for b in sorted(incident,key=str) for n,p in loads[b] if n not in selected]
    aliases={}
    for name,net in module['netnames'].items():
        for i,b in enumerate(net['bits']):
            if b in boundaries or b in outputs:aliases.setdefault(str(b),[]).append(dict(name=name,index=i))
    return dict(cells=sorted(selected),event_flops=sorted(endpoints),
        boundaries=[dict(bit=b,source=kind,aliases=aliases.get(str(b),[])) for b,kind in sorted(boundaries.items(),key=lambda x:str(x[0]))],
        event_outputs=[dict(bit=b,aliases=aliases.get(str(b),[])) for b in sorted(outputs)],omitted_receiver_terminals=omitted)


def header(block):
    result=[]
    for line in block.splitlines():
        if not result:result=line.split()[2:]
        elif line.startswith('+'):result+=line.split()[1:]
        else:break
    return result


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    inv=ROOT/'build/signoff400/startup_timing_routed_CDC_inventory_001';joined=ROOT/'build/signoff400/prototype_v3_digital_instance_join_001'
    layout=ROOT/'build/signoff400/startup_timing_filled_layout_002';extraction=ROOT/'build/signoff400/prototype_v3_assembly_capacitance_001'
    routed=inv/'routed.json';state=inv/'inventory.json';mapping=joined/'join.json';lvs=layout/'assembly.spice'
    model=extraction/'IntegerPLL_400MHz_PrototypeTop/capacitance.spice'
    receipts=[inv/'assessment.json',joined/'assessment.json',layout/'assessment.json',extraction/'native_assessment.json']
    rr=[json.loads(p.read_text()) for p in receipts]
    for path,receipt in ((routed,rr[0]),(state,rr[0]),(mapping,rr[1]),(lvs,rr[2]),(model,rr[3])):
        if receipt['artifacts'].get(str(path))!=sha(path):raise ValueError('receiver source changed: '+str(path))
    paths=[*receipts,routed,state,mapping,lvs,model,Path(__file__).resolve(),Path(__file__).with_name('compare_mapped_routed_CDC.py'),Path(__file__).with_name('bind_prototype_spef_pins_v2.py'),Path(__file__).with_name('prepare_prototype_analog_reference.py')]
    pins={str(p):sha(p) for p in paths}
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        module=json.loads(routed.read_text())['modules']['IntegerPLL_ProgrammedCore']
        result=select(module,json.loads(state.read_text())['sequential_state'])
        join_rows=json.loads(mapping.read_text())['mapping']
        join={identifier(r['routed_instance']):r for r in join_rows}
        if len(join)!=len(join_rows):raise ValueError('ambiguous physical join identifier normalization')
        _,physical,canonical=hierarchy(lvs.read_text(),'IntegerPLL_ProgrammedCore')
        blocks=subcircuits(model.read_text());definitions={};instances=[];net_to_physical={};physical_to_net={};bindings=[]
        for i,name in enumerate(result['cells']):
            cell=module['cells'][name];row=join[identifier(name)];p=physical[row['extracted_instance']]
            if row['master']!=cell['type'] or p['model']!=cell['type']:raise ValueError('receiver physical master mismatch')
            pinmap={}
            for pin,bits in cell['connections'].items():
                if len(bits)!=1:raise ValueError('scalar physical cell pins required')
                bit=bits[0];node=canonical(p['pins'][pin])
                if net_to_physical.setdefault(bit,node)!=node or physical_to_net.setdefault(node,bit)!=bit:raise ValueError('receiver physical conductor split/short')
                pinmap[pin]='n_'+str(bit)
            pinmap.update(VPWR='VPWR',VGND='VGND',VPB='VPB',VNB='VNB')
            block=blocks[cell['type']];ports=header(block);private=[p for p in ports if p not in pinmap]
            import re
            if any(not re.fullmatch(r'a_\d+_\d+#',p) for p in private):raise ValueError('unreviewed exposed local cell port')
            definitions[cell['type']]=block
            instances.append('Xreceiver_'+str(i)+' '+' '.join(pinmap.get(p,'private_'+str(i)+'_'+str(k)) for k,p in enumerate(ports))+' '+cell['type'])
            bindings.append(dict(routed_instance=name,extracted_instance=row['extracted_instance'],master=cell['type'],functional_pins=pinmap,private_extracted_ports=private))
        boundary=[x['bit'] for x in result['boundaries']];outputs=[x['bit'] for x in result['event_outputs']]
        interface=['n_'+str(b) for b in [*boundary,*outputs]]+['VGND','VNB','VPB','VPWR']
        if len(interface)!=len(set(interface)):raise ValueError('duplicate receiver interface port')
        receiver=output/'receiver.spice'
        receiver.write_text('* Actual routed BBPD receiver; cell-local C only, omitted loads recorded.\n'+''.join(definitions.values())+'\n.subckt prototype_BBPD_receiver '+' '.join(interface)+'\n'+'\n'.join(instances)+'\n.ends prototype_BBPD_receiver\n')
        result.update(physical_bindings=bindings,interface=interface)
    detail=output/'receiver.json';save(detail,result);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail),str(receiver):sha(receiver)},
        selected_cells=len(result['cells']),event_flops=len(result['event_flops']),boundary_inputs=len(result['boundaries']),
        omitted_receiver_terminals=len(result['omitted_receiver_terminals']),physical_cell_and_conductor_binding_pass=True,
        all_boundary_stimuli_justified=False,intercell_wire_RC_included=False,parent_coupling_included=False,
        receiver_native_validation_complete=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    print('Receiver cells:',len(result['cells']),'boundary inputs:',len(result['boundaries']))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output.resolve())
