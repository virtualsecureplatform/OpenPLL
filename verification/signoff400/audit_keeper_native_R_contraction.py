"""Compare native flat RC against flat C after ideal contraction of every wire R."""
import argparse,json,re
from collections import Counter,defaultdict
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from native_spice_comments import strip_floating_annotation

SCALE={'':F(1),'k':F(1000),'m':F(1,1000),'u':F(1,10**6),'n':F(1,10**9),'p':F(1,10**12),'f':F(1,10**15),'a':F(1,10**18)}
def number(value):
    match=re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)([kmunpfa]?)',value.lower())
    if not match:raise ValueError('literal numeric parameter required: '+value)
    return F(match[1])*SCALE[match[2]]

def parse(text):
    devices=[];caps=[];resistors=[];ports=[];header=False;names=set()
    for raw in text.splitlines():
        f=strip_floating_annotation(raw).split()
        if not f or f[0].startswith('*'):continue
        if f[0].lower()=='.subckt':ports.extend(f[2:]);header=True;continue
        if f[0]=='+':
            if not header:raise ValueError('only header continuations supported')
            ports.extend(f[1:]);continue
        header=False
        if f[0].lower()=='.ends':continue
        if f[0].lower() in names:raise ValueError('duplicate card')
        names.add(f[0].lower());kind=f[0][0].upper()
        if kind=='X':
            j=next((i for i,t in enumerate(f) if '=' in t),len(f))-1
            if not f[j].startswith('sky130_fd_pr__'):raise ValueError('flat native primitive required')
            params={}
            for t in f[j+1:]:
                k,v=t.split('=',1)
                if k.lower() in params:raise ValueError('duplicate parameter')
                params[k.lower()]=number(v)
            devices.append((f[j].lower(),tuple(n.lower() for n in f[1:j]),params))
        elif kind in ['C','R']:
            if len(f)!=4:raise ValueError('literal two-terminal card required')
            (caps if kind=='C' else resistors).append((f[1].lower(),f[2].lower(),number(f[3])))
        else:raise ValueError('unsupported statement '+f[0])
    return dict(devices=devices,caps=caps,resistors=resistors,ports=[p.lower() for p in ports])

def compare(base_text,rc_text):
    base=parse(base_text);rc=parse(rc_text)
    if base['resistors']:raise ValueError('reference must have no explicit wire R')
    known=set(base['ports'])
    for _,nodes,_ in base['devices']:known.update(nodes)
    for a,b,_ in base['caps']:known.update([a,b])
    parent={}
    def find(n):
        parent.setdefault(n,n)
        while parent[n]!=n:parent[n]=parent[parent[n]];n=parent[n]
        return n
    for a,b,value in rc['resistors']:
        if value<0:raise ValueError('negative wire resistance')
        parent[find(a)]=find(b)
    groups=defaultdict(set)
    for n in list(parent):groups[find(n)].add(n)
    mapping={};collisions=[]
    for members in groups.values():
        original=members & known
        if len(original)>1:collisions.append(sorted(original))
        representative=min(original or members)
        mapping.update({n:representative for n in members})
    def inventory(data,contract):
        result=Counter()
        for model,nodes,params in data['devices']:
            nodes=tuple(contract.get(n,n) for n in nodes);options=[(nodes,tuple(sorted(params.items())))]
            if 'nfet' in model or 'pfet' in model:
                if len(nodes)!=4:raise ValueError('four-terminal MOS required')
                swapped=dict(params)
                for a,b in [('ad','as'),('pd','ps'),('nrd','nrs')]:
                    if (a in params)!=(b in params):raise ValueError('paired diffusion parameters required')
                    if a in params:swapped[a],swapped[b]=params[b],params[a]
                options.append(((nodes[2],nodes[1],nodes[0],nodes[3]),tuple(sorted(swapped.items()))))
            elif model=='sky130_fd_pr__res_generic_po':options.append((tuple(reversed(nodes)),tuple(sorted(params.items()))))
            result[(model,*min(options))]+=1
        return result
    def capacitors(data,contract):
        result=defaultdict(F)
        for a,b,value in data['caps']:
            a,b=contract.get(a,a),contract.get(b,b)
            if a!=b:result[tuple(sorted((a,b)))]+=value
        return {k:v for k,v in result.items() if v}
    before=inventory(base,{});after=inventory(rc,mapping);cb=capacitors(base,{});ca=capacitors(rc,mapping)
    differences=[dict(nodes=list(k),reference_F_exact=str(cb.get(k,F(0))),contracted_F_exact=str(ca.get(k,F(0)))) for k in sorted(cb.keys()|ca.keys()) if cb.get(k,F(0))!=ca.get(k,F(0))]
    return dict(reference_primitives=sum(before.values()),candidate_primitives=sum(after.values()),primitive_multisets_match=before==after,missing_primitive_count=sum((before-after).values()),extra_primitive_count=sum((after-before).values()),wire_R_cards=len(rc['resistors']),positive_wire_R_cards=sum(v>0 for _,_,v in rc['resistors']),wire_R_components=len(groups),components_joining_distinct_reference_nodes=collisions,ordered_formal_ports_match=base['ports']==rc['ports'],reference_nonzero_C_pairs=len(cb),contracted_nonzero_C_pairs=len(ca),C_pair_differences=differences,exact_aggregated_C_match=not differences,negative_candidate_C_cards=sum(v<0 for _,_,v in rc['caps']),exact_device_and_C_contraction_verified=before==after and not differences and not collisions and base['ports']==rc['ports'])

def run(flat,pilot,output):
    receipts=[p/'assessment.json' for p in [flat,pilot]];a,b=[json.loads(p.read_text()) for p in receipts]
    for r in [a,b]:verify(r['input_sha256']);verify(r['artifacts'])
    if not b['native_process_completed']:raise ValueError('completed pilot required')
    if b['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]):raise ValueError('same checked flat source required')
    source=flat/'capacitance.spice';candidate=pilot/'pilot.spice';files=[*receipts,source,candidate,Path(__file__).resolve(),Path(__file__).with_name('native_spice_comments.py')];pins={str(p):sha(p) for p in files};metrics=compare(source.read_text(),candidate.read_text());verify(pins);output.mkdir(parents=True,exist_ok=False)
    save(output/'assessment.json',dict(input_sha256=pins,**metrics,exact_requested_network_coverage_verified=False,distributed_wire_R_qualified=False,native_simulation_allowed=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','pilot','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['flat','pilot','output']))
