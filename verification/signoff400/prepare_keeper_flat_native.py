"""Prepare a conductor-C native reference without spatial endpoint approximation."""
import argparse,json,os,time
from collections import Counter
from pathlib import Path
from common_v3 import save,sha,verify
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
            i=pos[0];devices.append(' '.join(['Xflat'+f[0][1:],*[node(n)for n in f[1:i]],*f[i:]]))
        elif kind in ['R','C']:
            if len(f)!=4:raise ValueError('literal two-terminal card required')
            value=number(f[-1]);a,b=node(f[1]),node(f[2])
            if kind=='R':
                if value!=0:raise ValueError('geometry reference must have no distributed wire R')
                devices.append(' '.join([f[0],a,b,f[-1]]))
            else:
                if value<0:raise ValueError('negative physical flat C requires investigation')
                if value:caps.append(' '.join([f[0],a,b,f[-1]]))
                else:counts['zero_C_omitted']+=1
        else:raise ValueError('unsupported flat statement '+f[0])
    if len(set(v.lower()for v in nodes.values()))!=len(nodes):raise ValueError('generated conductor namespace collision')
    source='\n'.join(['.subckt '+' '.join([top,*ports]),*devices,'.ends '+top])+'\n'
    templated,metrics=factor(source);adapted,poly=translate(templated)
    end='.ends '+top
    if adapted.count(end)!=1:raise ValueError('one root end required')
    model=adapted.replace(end,'\n'.join(caps)+'\n'+end)
    emitted=[s for s in model.splitlines()if s.split()and s.split()[0].startswith('C')]
    if emitted!=caps:raise ValueError('emitted C cards differ')
    inverse={v:k for k,v in nodes.items()};original_caps=[line.split()for line in logical[1:-1]if line.startswith('C')and number(line.split()[-1])!=0]
    for expected,actual in zip(original_caps,emitted):
        f=actual.split()
        if [f[0],inverse[f[1]],inverse[f[2]],f[3]]!=expected:raise ValueError('C endpoints or coefficient changed')
    if len(original_caps)!=len(emitted):raise ValueError('C count differs')
    return model,nodes,dict(source_counts=dict(counts),nonzero_C_preserved=len(caps),literal_templates=metrics,poly_adapter_templates=poly,all_nonzero_C_endpoints_and_literal_values_preserved=True)


def run(flat,lvs,output):
    receipts=[p/'assessment.json'for p in [flat,lvs]];r,l=[json.loads(p.read_text())for p in receipts]
    for a in [r,l]:verify(a['input_sha256']);verify(a['artifacts'])
    if not l['unique_device_LVS_match']or not l['all_records_without_discrepancies']or l['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]):raise ValueError('matching device LVS required')
    source=flat/'capacitance.spice';folder=Path(__file__).resolve().parent;files=[*receipts,source,Path(__file__).resolve(),*[folder/n for n in ['prototype_native_literal_templates.py','prototype_xyce_resistor_translation.py','native_spice_comments.py','audit_hierarchical_capacitance.py']]];pins={str(p):sha(p)for p in files};output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{24})
    with lease(1,12,time.clock_gettime(time.CLOCK_BOOTTIME)+600):model,nodes,metrics=normalize(source.read_text())
    if metrics['source_counts']['X']!=62338:raise ValueError('checked keeper primitive inventory differs')
    model_file=output/'model.spice';model_file.write_text(model);mapping=output/'nodes.json';save(mapping,nodes);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [model_file,mapping]},**metrics,constant_C_nonnegative=True,constant_C_PSD_by_nonnegative_branch_energy=True,distributed_wire_R_included=False,spatial_endpoint_attachment_applied=False,only_zero_C_cards_omitted=True,native_backend_correlation_complete=False,model_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','lvs','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['flat','lvs','output']))
