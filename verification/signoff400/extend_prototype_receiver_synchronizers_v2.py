"""Attach the actual first synchronizer D loads at their bound routed wire terminals."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from bind_prototype_BBPD_receiver_wire import identifier
from prepare_prototype_BBPD_receiver_v2 import header
from prepare_prototype_analog_reference import subcircuits
from audit_hierarchical_capacitance import number


def extend(text,metadata,bound,module,physical,event_outputs):
    blocks=subcircuits(text);top='prototype_BBPD_receiver_RC';rows=blocks[top].splitlines()
    if header(blocks[top])!=metadata['interface']:raise ValueError('original receiver interface changed')
    # Independently recover conductor-node names by the serialized positive-R
    # elements, preserving ordered endpoints and exact values.
    actual={f[0]:f for line in rows if (f:=line.split()) and f[0].startswith('Rwire')}
    names={};inverse={};index=0
    for net in bound['networks']:
        for r in net['resistors']:
            f=actual.pop('Rwire'+str(index));index+=1
            if len(f)!=4 or number(f[3])!=Fraction(r['ohms']):raise ValueError('wire resistance differs')
            for token,node in zip(r['nodes'],f[1:3]):
                if names.setdefault(token,node)!=node or inverse.setdefault(node,token)!=token:raise ValueError('ambiguous wire-node serialization')
    if actual:raise ValueError('extra serialized wire resistor')
    physical_cells={identifier(row['routed_instance']):row for row in physical['mapping']}
    if len(physical_cells)!=len(physical['mapping']):raise ValueError('ambiguous extracted instance join')
    event_bits=[]
    for row in event_outputs:
        roles={role for a in row['aliases'] for suffix,role in (('bbpd_dn_event_toggle','DN'),('bbpd_up_event_toggle','UP')) if a['name'].endswith(suffix)}
        if len(roles)!=1:raise ValueError('unambiguous event toggle alias required')
        event_bits.append((row['bit'],next(iter(roles))))
    if len(event_bits)!=2 or {role for bit,role in event_bits}!={'DN','UP'} or len({bit for bit,role in event_bits})!=2:
        raise ValueError('two distinct event toggle conductors required')
    ports=list(metadata['interface']);added=[];instances=[];master='sky130_fd_sc_hs__dfrtp_1'
    interface=header(blocks[master])
    for bit,role in event_bits:
        nets=[n for n in bound['networks'] if n['logical_bit']==bit]
        if len(nets)!=1:raise ValueError('unique event-toggle wire network required')
        sinks=[t for t in nets[0]['outside_terminals'] if t['kind']=='I' and t['direction']=='I']
        if len(sinks)!=1:raise ValueError('one omitted first synchronizer D load required')
        token=sinks[0]['node'];instance,pin=token.rsplit(':',1)
        matching=[(n,c) for n,c in module['cells'].items() if identifier(n)==identifier(instance)]
        if len(matching)!=1:raise ValueError('first synchronizer instance ambiguous')
        name,cell=matching[0]
        if pin!='D' or cell['type']!=master or cell['connections']['D']!=[bit]:raise ValueError('actual first synchronizer D binding differs')
        p=physical_cells[identifier(name)]
        if p['master']!=master:raise ValueError('filled-layout receiver master differs')
        clock='SYNC_CLK_'+role;q='SYNC_'+role+'_Q';reset='SYNC_RESET_N'
        ports.extend([clock,q]);binding=dict(CLK=clock,Q=q,D=names[token],RESET_B=reset,VGND='VGND',VNB='VNB',VPWR='VPWR',VPB='VPB')
        private=[p for p in interface if p not in binding]
        import re
        if any(not re.fullmatch(r'a_\d+_\d+#',p) for p in private):raise ValueError('unreviewed first synchronizer cell port')
        instances.append('Xfirstsync_'+role+' '+' '.join(binding.get(p,'__syncprivate_'+role+'_'+str(i)) for i,p in enumerate(interface))+' '+master)
        added.append(dict(role=role,routed_instance=name,extracted_instance=p['extracted_instance'],master=master,
                          data_bit=bit,data_spef_node=token,data_spice_node=names[token],clock_bit=cell['connections']['CLK'][0],
                          reset_bit=cell['connections']['RESET_B'][0],output_bit=cell['connections']['Q'][0],private_cell_ports=private))
    ports.append('SYNC_RESET_N')
    if len(set(ports))!=len(ports) or '__syncprivate_' in text:raise ValueError('extended receiver namespace collision')
    rows[0]='.subckt prototype_BBPD_receiver_with_sync '+' '.join(ports)
    rows[-1]='.ends prototype_BBPD_receiver_with_sync'
    extended=''.join(b for n,b in blocks.items() if n!=top)+'\n'.join(rows[:-1]+instances+rows[-1:])+'\n'
    return extended,dict(interface=ports,original_interface=metadata['interface'],first_synchronizers=added,
        original_wire_R_and_C_retained=True,first_sync_input_loads_included=True,
        sync_clock_tree_RC_included=False,sync_reset_tree_RC_included=False,sync_Q_fanout_loads_bounded=False)


def run(source,wire,inv,physical,receiver,output):
    output.mkdir(parents=True,exist_ok=False)
    files=[source/'receiver_RC.spice',source/'model.json',wire/'networks.json',inv/'routed.json',physical/'join.json',receiver/'receiver.json']
    receipts=[source/'assessment.json',source/'assessment.json',wire/'assessment.json',inv/'assessment.json',physical/'assessment.json',receiver/'assessment.json']
    sr,wr,rr=[json.loads((p/'assessment.json').read_text()) for p in (source,wire,receiver)]
    if sr['input_sha256'].get(str(receiver/'assessment.json'))!=sha(receiver/'assessment.json') or sr['input_sha256'].get(str(wire/'assessment.json'))!=sha(wire/'assessment.json'):
        raise ValueError('receiver RC lineage mismatch')
    if rr['input_sha256'].get(str(inv/'assessment.json'))!=sha(inv/'assessment.json') or rr['input_sha256'].get(str(physical/'assessment.json'))!=sha(physical/'assessment.json'):
        raise ValueError('routed inventory or physical join lineage mismatch')
    for p,rp in zip(files,receipts):
        r=json.loads(rp.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        if r['artifacts'].get(str(p))!=sha(p):raise ValueError('receiver extension source changed')
    pins={str(p):sha(p) for p in [*files,*receipts,Path(__file__).resolve(),Path(__file__).with_name('prepare_prototype_analog_reference.py')]}
    model,mapping=extend(files[0].read_text(),json.loads(files[1].read_text()),json.loads(files[2].read_text()),json.loads(files[3].read_text())['modules']['IntegerPLL_ProgrammedCore'],json.loads(files[4].read_text()),json.loads(files[5].read_text())['event_outputs'])
    model_path=output/'receiver_with_sync.spice';model_path.write_text(model);detail=output/'model.json';save(detail,mapping);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (model_path,detail)},
         first_sync_input_loads_included=True,first_sync_cells_bound_to_filled_layout=True,
         independent_native_validation_complete=False,full_clock_and_reset_RCs_included=False,
         diagnostic=True,validated_for_prototype=False,release_ready=False))
    print('Added bound first synchronizer loads:',len(mapping['first_synchronizers']))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('source','wire','inventory','joined','receiver','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();run(a.source.resolve(),a.wire.resolve(),a.inventory.resolve(),a.joined.resolve(),a.receiver.resolve(),a.output.resolve())
