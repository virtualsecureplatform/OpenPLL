"""Contract routed wire R exactly to compare capacitance models at equal zero R."""
import argparse
from collections import defaultdict
from fractions import Fraction as F
import json
from pathlib import Path
from common_v3 import save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from build_prototype_full_C_wire_R_v3 import rows
from audit_hierarchical_capacitance import number
from build_prototype_DCO_rc import decimal

def contract(text,top):
    blocks=subcircuits(text);body=rows(blocks[top]);ports=body[0].split()[2:];parent={}
    def find(n):
        parent.setdefault(n,n)
        if parent[n]!=n:parent[n]=find(parent[n])
        return parent[n]
    count=0
    for row in body[1:-1]:
        f=row.split()
        if f[0][0].upper()=='R':
            if len(f)!=4 or number(f[3])<0:raise ValueError('constant nonnegative wire resistors required')
            parent[find(f[1])]=find(f[2]);count+=1
    labels={}
    for port in ports:
        root=find(port)
        if root in labels:raise ValueError('wire contraction shorts distinct top ports')
        labels[root]=port
    def node(n):return labels.get(find(n),find(n))
    result=[body[0]];caps=defaultdict(F);instances=0
    for row in body[1:-1]:
        f=row.split();kind=f[0][0].upper()
        if kind=='R':continue
        if kind=='C':
            if len(f)!=4:raise ValueError('constant capacitors required')
            a,b=node(f[1]),node(f[2])
            if a!=b:caps[tuple(sorted((a,b)))]+=number(f[3])
        elif kind=='X':
            boundary=next((i for i,t in enumerate(f) if '=' in t),len(f))-1
            if f[boundary] not in blocks and not f[boundary].startswith('sky130_fd_pr__'):raise ValueError('unknown instance model')
            result.append(' '.join([f[0],*[node(n) for n in f[1:boundary]],*f[boundary:]]));instances+=1
        else:raise ValueError('unexpected root element')
    result += [f'Czero{i} {a} {b} {decimal(v)}' for i,((a,b),v) in enumerate(sorted(caps.items())) if v]
    result.append(body[-1]);replacement='\n'.join(result)+'\n'
    output=text.replace(blocks[top],replacement)
    if any(subcircuits(output)[name]!=block for name,block in blocks.items() if name!=top):raise ValueError('cell model changed')
    return output,dict(contracted_wire_resistors=count,retained_top_instances=instances,aggregated_top_capacitors=sum(bool(v) for v in caps.values()),distinct_top_ports_preserved=True,cell_subcircuits_byte_identical=True)

def run(rc,output):
    receipt=rc/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    source=rc/'nom.spice';blocks=subcircuits(source.read_text());tops=[n for n in blocks if n.startswith('IntegerPLL_DCO_')]
    if len(tops)!=1:raise ValueError('unique DCO top')
    model,metrics=contract(source.read_text(),tops[0]);output.mkdir(parents=True,exist_ok=False);target=output/'nom.spice';target.write_text(model)
    inputs={**a['input_sha256'],str(receipt):sha(receipt),str(source):sha(source),str(Path(__file__).resolve()):sha(Path(__file__).resolve())}
    for name in ('prepare_prototype_analog_reference.py','build_prototype_full_C_wire_R_v3.py','audit_hierarchical_capacitance.py','build_prototype_DCO_rc.py'):
        p=Path(__file__).with_name(name);inputs[str(p)]=sha(p)
    verify(inputs);save(output/'assessment.json',dict(input_sha256=inputs,artifacts={str(target):sha(target)},metrics=metrics,cell_internal_and_wire_capacitance_scopes_separated=True,mirrored_couplings_counted_once=True,wire_R_intentionally_zero_for_C_model_correlation=True,positive_wire_resistors_replaced_by_exact_node_identification=True,physical_finite_R_behavior_qualified=False,parent_loading_complete=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('rc','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.rc.resolve(),a.output.resolve())
