"""Add bound nominal wire RC to the actual receiver; expose every off-network coupling terminal."""
import argparse
from collections import Counter,defaultdict
from fractions import Fraction as F
import json
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from prepare_prototype_BBPD_receiver_v2 import header
from audit_hierarchical_capacitance import number
from build_prototype_DCO_rc import decimal


def build(text,mapping,bound):
    top='prototype_BBPD_receiver';blocks=subcircuits(text);ports=header(blocks[top]);owners={};tokens=set();terminal={};couplings=defaultdict(list);resistors=[];ground=[]
    if '__rxwire_' in text or 'aggressor_' in text:raise ValueError('reserved RC namespace collision')
    def own(token,net):
        if token in owners and owners[token]!=net:raise ValueError('wire-node conductor ownership collision')
        owners[token]=net;tokens.add(token)
    for net in bound['networks']:
        name=net['net']
        for t in net['all_named_terminal_connections']:own(t['node'],name)
        for r in net['resistors']:
            if F(r['ohms'])<=0:raise ValueError('positive conventional wire resistance required')
            for n in r['nodes']:own(n,name)
            resistors.append((tuple(r['nodes']),F(r['ohms'])))
        for t in net['selected_terminals']:
            key=(t['routed_instance'],t['pin'])
            if key in terminal:raise ValueError('duplicate selected cell terminal')
            terminal[key]=t['spef_node']
        for c in net['capacitors']:
            value=F(c['farads'])
            if value<0:raise ValueError('negative conventional wire C')
            if len(c['nodes'])==1:
                own(c['nodes'][0],name)
                if value:ground.append((c['nodes'][0],value))
            elif len(c['nodes'])==2:
                if value:couplings[tuple(sorted(c['nodes']))].append((name,value));tokens.update(c['nodes'])
            else:raise ValueError('one/two-terminal SPEF capacitance required')
    names={};port_map={}
    for p in ports:
        if not p.startswith('n_'):continue
        bit=int(p[2:]);nets=[n for n in bound['networks'] if n['logical_bit']==bit]
        if len(nets)!=1:raise ValueError('one bound network per receiver port required')
        candidates=[t for t in nets[0]['all_named_terminal_connections'] if (t['kind']=='P' and t['direction']=='I') or (t['kind']=='I' and t['direction']=='O')]
        if len(candidates)!=1:raise ValueError('one source terminal per interface conductor required')
        token=candidates[0]['node']
        if token in names:raise ValueError('distinct receiver ports share source terminal')
        names[token]=p;port_map[p]=token
    outside=sorted(tokens-set(owners));aggressors=[]
    for i,token in enumerate(outside):
        names[token]='aggressor_'+str(i);aggressors.append(dict(port=names[token],spef_node=token))
    for token in sorted(tokens):
        if token not in names:names[token]='__rxwire_'+str(len(names))
    coupled=[]
    for pair,entries in sorted(couplings.items()):
        known=[owners.get(n) for n in pair]
        if None not in known:
            if known[0]==known[1] or len(entries)!=2 or entries[0][0]==entries[1][0] or entries[0][1]!=entries[1][1] or {e[0] for e in entries}!=set(known):raise ValueError('invalid internal mirrored coupling records')
        else:
            if known.count(None)!=1 or len(entries)!=1 or entries[0][0] not in known:raise ValueError('invalid off-network coupling ownership')
        coupled.append((pair,entries[0][1]))
    bindings=mapping['physical_bindings'];rows=blocks[top].splitlines();result=['.subckt '+top+'_RC '+' '.join(ports+[a['port'] for a in aggressors])];rewired=set()
    for line in rows[1:-1]:
        if not line.strip():continue
        f=line.split()
        if not f[0].startswith('Xreceiver_'):raise ValueError('unreviewed original receiver top-level element')
        index=int(f[0].split('_')[-1]);row=bindings[index]
        if f[-1]!=row['master']:raise ValueError('receiver instance/master ordering changed')
        interface=header(blocks[row['master']])
        if len(interface)!=len(f)-2:raise ValueError('receiver cell pin arity mismatch')
        for i,p in enumerate(interface,1):
            key=(row['routed_instance'],p)
            if key in terminal:
                if f[i]!=row['functional_pins'][p]:raise ValueError('source receiver logical binding changed')
                f[i]=names[terminal[key]];rewired.add(key)
        result.append(' '.join(f))
    if rewired!=set(terminal):raise ValueError('not every selected receiver pin was rewired')
    expected_R=Counter();expected_C=Counter()
    for i,(pair,value) in enumerate(resistors):
        nodes=tuple(names[n] for n in pair);result.append(f'Rwire{i} {nodes[0]} {nodes[1]} {decimal(value)}');expected_R[(tuple(sorted(nodes)),value)]+=1
    caps=[((names[n],'VGND'),value) for n,value in ground]+[(tuple(names[n] for n in pair),value) for pair,value in coupled]
    for i,(nodes,value) in enumerate(caps):result.append(f'Cwire{i} {nodes[0]} {nodes[1]} {decimal(value)}');expected_C[(tuple(sorted(nodes)),value)]+=1
    result.append('.ends '+top+'_RC');model='* Receiver cell-local C plus bound wire RC; explicit off-network aggressor ports.\n'+''.join(v for k,v in blocks.items() if k!=top)+'\n'.join(result)+'\n'
    actual_R=Counter();actual_C=Counter()
    for line in subcircuits(model)[top+'_RC'].splitlines():
        f=line.split()
        if f and f[0][0] in 'RC':(actual_R if f[0][0]=='R' else actual_C)[(tuple(sorted(f[1:3])),number(f[3]))]+=1
    if actual_R!=expected_R or actual_C!=expected_C:raise ValueError('wire element serialization changed exact topology/values')
    return model,dict(interface=ports+[a['port'] for a in aggressors],original_interface=ports,interface_source_terminals=port_map,off_network_aggressors=aggressors,
        rewired_selected_terminals=len(rewired),wire_resistors=len(resistors),wire_capacitors=len(caps),internal_couplings_deduplicated_once=True,
        exact_wire_element_reparse_pass=True,off_network_terminals_implicitly_grounded=False,omitted_receiver_pin_loads_bounded=False,parent_coupling_included=False)


def run(output):
    output.mkdir(parents=True,exist_ok=False);base=ROOT/'build/signoff400';source=base/'prototype_v3_BBPD_receiver_002';wire=base/'prototype_v3_BBPD_receiver_wire_binding_001'
    sr=source/'assessment.json';wr=wire/'assessment.json';s,w=[json.loads(p.read_text()) for p in (sr,wr)]
    model=source/'receiver.spice';mapping=source/'receiver.json';networks=wire/'networks.json'
    for p,r in ((model,s),(mapping,s),(networks,w)):
        if r['artifacts'].get(str(p))!=sha(p):raise ValueError('bound receiver input changed')
    paths=[sr,wr,model,mapping,networks,Path(__file__).resolve(),Path(__file__).with_name('prepare_prototype_BBPD_receiver_v2.py'),Path(__file__).with_name('build_prototype_DCO_rc.py'),Path(__file__).with_name('audit_hierarchical_capacitance.py')]
    pins={str(p):sha(p) for p in paths};text,detail=build(model.read_text(),json.loads(mapping.read_text()),json.loads(networks.read_text()))
    target=output/'receiver_RC.spice';target.write_text(text);report=output/'model.json';save(report,detail);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(target):sha(target),str(report):sha(report)},
        rewired_selected_terminals=detail['rewired_selected_terminals'],wire_resistors=detail['wire_resistors'],wire_capacitors=detail['wire_capacitors'],
        off_network_aggressor_ports=len(detail['off_network_aggressors']),exact_wire_element_reparse_pass=True,
        outside_receiver_pin_capacitance_bounded=False,parent_coupling_included=False,native_waveform_validation_complete=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False))
    print('Receiver wire RC:',detail['wire_resistors'],'R,',detail['wire_capacitors'],'C; aggressor ports:',len(detail['off_network_aggressors']))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);run(p.parse_args().output.resolve())
