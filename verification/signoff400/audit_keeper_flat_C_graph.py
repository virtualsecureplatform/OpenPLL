"""Count capacitor-only nodes and dangling branches without changing the circuit."""
import argparse,json,time
from collections import defaultdict,deque
from pathlib import Path
from common_v3 import save,sha,verify
from native_spice_comments import strip_floating_annotation
from audit_hierarchical_capacitance import number


def run(flat,output):
    receipt=flat/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts']);source=flat/'capacitance.spice';pins={str(p):sha(p)for p in [receipt,source,Path(__file__).resolve(),Path(__file__).with_name('native_spice_comments.py'),Path(__file__).with_name('audit_hierarchical_capacitance.py')]};anchors={'0'};graph=defaultdict(set);counts=defaultdict(int);header=False
    for raw in source.open():
        f=strip_floating_annotation(raw).split()
        if not f:continue
        if f[0].lower()=='.subckt':anchors.update(f[2:]);header=True
        elif f[0]=='+':
            if not header:raise ValueError('unexpected continuation')
            anchors.update(f[1:])
        else:header=False
        if f[0].startswith('X'):
            pos=[i for i,t in enumerate(f)if t.startswith('sky130_fd_pr__')]
            if len(pos)!=1:raise ValueError('one primitive required')
            anchors.update(f[1:pos[0]])
        elif f[0].startswith('R'):anchors.update(f[1:3])
        elif f[0].startswith('C'):
            c=number(f[-1]);counts['C_cards']+=1
            if c<0:raise ValueError('positive physical C graph required')
            if not c:counts['zero_C']+=1;continue
            a,b=f[1:3];counts['nonzero_C']+=1
            if a==b:counts['same_node_C']+=1;continue
            if b in graph[a]:counts['duplicate_parallel_C']+=1
            graph[a].add(b);graph[b].add(a)
    original_nodes=len(graph);floating=set(graph)-anchors;queue=deque(n for n in floating if len(graph[n])<=1);removed=0
    while queue:
        n=queue.popleft()
        if n not in graph or n in anchors or len(graph[n])>1:continue
        for other in graph[n]:
            graph[other].remove(n)
            if other not in anchors and len(graph[other])<=1:queue.append(other)
        del graph[n];removed+=1
    histogram=defaultdict(int)
    for n in set(graph)-anchors:histogram[str(len(graph[n]))]+=1
    output.mkdir(parents=True,exist_ok=False);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,counts=dict(counts),capacitor_graph_nodes=original_nodes,primitive_and_port_anchor_nodes=len(anchors),capacitor_only_nodes=len(floating),capacitor_only_leaf_peeling_nodes=removed,remaining_capacitor_only_degree_histogram=dict(histogram),leaf_peeling_is_graph_diagnostic_only=True,initial_charge_constraints_not_qualified=True,models_modified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--flat',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.flat.resolve(),a.output.resolve())
