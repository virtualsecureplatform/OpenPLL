"""Exactly partition a reconstructed negative-energy witness by hierarchy scope."""
import argparse,json,re
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from build_prototype_full_C_wire_R_v11 import expand
from prepare_prototype_analog_reference import subcircuits
from audit_hierarchical_capacitance import number


def run(models,wire,binding,energy,attachment,output):
    receipts=[p/'assessment.json'for p in [models,wire,binding,energy]];m,r,b,e=[json.loads(p.read_text())for p in receipts]
    for a in [m,r,b,e]:verify(a['input_sha256']);verify(a['artifacts'])
    if not e['result']['indefiniteness_proved']or 'voltage_vector'not in e['result']:raise ValueError('exact sparse voltage witness required')
    source=models/(attachment+'.hierarchy.spice');nf=models/(attachment+'.nodes.json');model=models/(attachment+'.spice');jf=[Path(p)for p in b['input_sha256']if p.endswith('/join.json')]
    if len(jf)!=1 or any(m['artifacts'].get(str(p))!=sha(p)for p in [source,nf,model]):raise ValueError('exact model artifacts required')
    if e['input_sha256'].get(str(model))!=sha(model):raise ValueError('witness refers to another model')
    mapping={re.sub(r'\\(.)',r'\1',row['routed_instance']):row['extracted_instance']for row in json.loads(jf[0].read_text())['mapping']}
    parsed=wire/'nom.json';spef=json.loads(parsed.read_text());tokens={t['node']for n in spef['nets']for t in n['connections']};tokens.update(v for n in spef['nets']for resistor in n['resistors']for v in resistor['nodes']);primary={t['node']for n in spef['nets']for t in n['connections']if t['kind']=='P'}
    text=source.read_text();blocks=subcircuits(text);top=next(line.split()[1]for line in model.read_text().splitlines()if line.startswith('.subckt '));wire_names={t:t if t in primary else top+'/__wire_'+str(i)for i,t in enumerate(sorted(tokens))};overrides={}
    for net in spef['nets']:
        for t in net['connections']:
            if t['kind']=='I':
                inst,pin=t['node'].rsplit(':',1);overrides[(mapping[re.sub(r'\\(.)',r'\1',inst)],pin)]=wire_names[t['node']]
    _,_,child,_,_=expand(blocks,top,overrides,True,cap_scope='children',native_resistors=[])
    _,_,root,_,_=expand(blocks,top,cap_scope='root',alias_scope='root',native_resistors=[])
    node_map=json.loads(nf.read_text());names=node_map['emitted_node_map'];lift=node_map['root_C_voltage_map'];combined=defaultdict(F);details=[];voltage={n:F(v)for n,v in e['result']['voltage_vector'].items()};scope_energy={}
    for scope,pairs in [('child_local',child),('parent_interaction',root)]:
        total=F()
        for (a,b),c in pairs.items():
            x,y=(names[lift[n]]for n in (a,b))if scope=='parent_interaction'else(names[n]for n in (a,b))
            if x==y:continue
            combined[tuple(sorted((x,y)))]+=c
            delta=voltage.get(x,F())-voltage.get(y,F());contribution=c*delta*delta;total+=contribution
            if contribution:details.append(dict(scope=scope,original_nodes=[a,b],emitted_nodes=[x,y],farads=str(c),exact_twice_energy_J=str(contribution)))
        scope_energy[scope]=total
    emitted={}
    for line in model.read_text().splitlines():
        f=line.split()
        if f and f[0].startswith('Cflat'):emitted[tuple(sorted(f[1:3]))]=number(f[3])
    if {k:v for k,v in combined.items()if v}!=emitted:raise ValueError('scope reconstruction does not reproduce complete emitted C operator')
    total=sum(scope_energy.values(),F())
    if total!=F(e['result']['exact_twice_energy_J']):raise ValueError('independent scope energies do not reproduce exact witness')
    output.mkdir(parents=True,exist_ok=False);detail=output/'incident_terms.json';save(detail,details)
    folder=Path(__file__).resolve().parent;files=[*receipts,source,nf,model,jf[0],parsed,Path(__file__).resolve(),folder/'build_prototype_full_C_wire_R_v11.py'];pins={str(p):sha(p)for p in files};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},attachment=attachment,scope_twice_energy_J={k:str(v)for k,v in scope_energy.items()},exact_total_twice_energy_J=str(total),entire_emitted_operator_independently_reconstructed=True,exact_witness_energy_reproduced=True,coefficients_modified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['models','wire','binding','energy','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--attachment',choices=['driver','farthest'],required=True);a=p.parse_args();run(a.models.resolve(),a.wire.resolve(),a.binding.resolve(),a.energy.resolve(),a.attachment,a.output.resolve())
