"""Prepare a literal native RC model without changing wire or capacitance branches."""
import argparse,json,os,time,re
from decimal import Decimal
from collections import Counter
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from native_spice_comments import strip_floating_annotation
from audit_hierarchical_capacitance import number
from prototype_native_literal_templates import factor
from prototype_xyce_resistor_translation import translate


def normalize(text):
    logical=[]
    for raw in text.splitlines():
        line=strip_floating_annotation(raw).strip()
        if not line or line.startswith('*'):continue
        if line.startswith('+'):
            if not logical or not logical[-1].lower().startswith('.subckt '):raise ValueError('only header continuations supported')
            logical[-1]+=' '+line[1:].strip()
        else:logical.append(line)
    if not logical or not logical[0].lower().startswith('.subckt ')or logical[-1].lower()not in ['.ends','.ends '+logical[0].split()[1].lower()]:raise ValueError('one explicit flat scope required')
    top=logical[0].split()[1];ports=logical[0].split()[2:]
    if len(set(p.lower()for p in ports))!=len(ports):raise ValueError('case-colliding formal ports')
    nodes={};folded={};names=set();counts=Counter();devices=[];caps=[]
    def node(n):
        if n.lower()in folded and folded[n.lower()]!=n:raise ValueError('case-colliding conductor names')
        folded[n.lower()]=n
        if n not in nodes:nodes[n]=n if n in ports or n=='0'else '__geometry_node_'+str(len(nodes))
        return nodes[n]
    for p in ports:node(p)
    for line in logical[1:-1]:
        f=line.split();kind=f[0][0]
        if f[0].lower()in names:raise ValueError('duplicate element name')
        names.add(f[0].lower());counts[kind]+=1
        if kind=='X':
            pos=[i for i,x in enumerate(f)if x.startswith('sky130_fd_pr__')]
            if len(pos)!=1:raise ValueError('one native primitive required')
            i=pos[0]
            for j in range(i+1,len(f)):
                name,value=f[j].split('=',1)
                if re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?[kK]',value):
                    f[j]=name+'='+str(Decimal(value[:-1])*1000);counts['k_suffix_literals_expanded']+=1
            devices.append(' '.join(['Xflat'+f[0][1:],*[node(n)for n in f[1:i]],*f[i:]]))
        elif kind in ['R','C']:
            if len(f)!=4:raise ValueError('literal two-terminal card required')
            value=number(f[-1]);a,b=node(f[1]),node(f[2])
            if kind=='R' and value<0:raise ValueError('negative native wire resistance')
            caps.append(' '.join([f[0],a,b,f[-1]]))
        else:raise ValueError('unsupported flat statement '+f[0])
    if len(set(v.lower()for v in nodes.values()))!=len(nodes):raise ValueError('generated conductor namespace collision')
    source='\n'.join(['.subckt '+' '.join([top,*ports]),*devices,'.ends '+top])+'\n'
    templated,metrics=factor(source)
    if 'sky130_fd_pr__res_generic_po' in templated:
        adapted,poly=translate(templated)
    else:
        adapted,poly=templated,0
    end='.ends '+top
    if adapted.count(end)!=1:raise ValueError('one root end required')
    model=adapted.replace(end,'\n'.join(caps)+'\n'+end)
    literal_names={s.split()[0] for s in caps}
    emitted=[s for s in model.splitlines()if s.split()and s.split()[0] in literal_names]
    if emitted!=caps:raise ValueError('emitted RC branch cards differ')
    inverse={v:k for k,v in nodes.items()};original_caps=[line.split()for line in logical[1:-1]if line.startswith(('C','R'))]
    for expected,actual in zip(original_caps,emitted):
        f=actual.split()
        if [f[0],inverse[f[1]],inverse[f[2]],f[3]]!=expected:raise ValueError('RC branch endpoints or coefficient changed')
    if len(original_caps)!=len(emitted):raise ValueError('RC branch count differs')
    return model,nodes,dict(source_counts=dict(counts),literal_RC_branches_preserved=len(caps),literal_templates=metrics,poly_adapter_templates=poly,all_RC_endpoints_and_literal_values_preserved=True)



def run():
    base=ROOT/'build/signoff400'
    review=base/'selected_reference_alias_full_RC_audit_1766/assessment.json'
    record=json.loads(review.read_text())
    verify(record['input_sha256']);verify(record['artifacts'])
    if not record.get('all_full_RC_checks_pass'):
        raise ValueError('all completed full RC review checks required')
    source=base/'selected_reference_alias_full_RC_1764/after.spice'
    if record['input_sha256'].get(str(source))!=sha(source):
        raise ValueError('review must bind this final RC netlist')
    out=base/'selected_reference_alias_native_RC_model_1768'
    out.mkdir(exist_ok=False)
    folder=Path(__file__).resolve().parent
    paths=[review,source,Path(__file__).resolve(),*[folder/n for n in
        ['prototype_native_literal_templates.py','prototype_xyce_resistor_translation.py',
         'native_spice_comments.py','audit_hierarchical_capacitance.py']]]
    pins={str(p):sha(p) for p in paths}
    with lease(1,12,time.clock_gettime(time.CLOCK_BOOTTIME)+1800):
        model,nodes,metrics=normalize(source.read_text())
        if metrics['source_counts']['X']!=62338:
            raise ValueError('full physical primitive population required')
        if metrics['source_counts'].get('R',0)<=0:
            raise ValueError('distributed resistance required')
        model_file=out/'model.spice';model_file.write_text(model)
        mapping=out/'nodes.json';save(mapping,nodes);verify(pins)
        save(out/'assessment.json',dict(input_sha256=pins,
            artifacts={str(p):sha(p) for p in [model_file,mapping]},**metrics,
            distributed_wire_R_included=True,signed_C_unchanged=True,
            zero_RC_branches_preserved=True,spatial_endpoint_attachment_applied=False,
            native_backend_correlation_complete=False,model_qualified=False,release_ready=False))

if __name__=='__main__':run()
