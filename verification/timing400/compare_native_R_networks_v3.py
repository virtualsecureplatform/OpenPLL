#!/usr/bin/env python3
"""Compare native networks under internal-node renaming; no coordinates are merged.

Joint graph-color refinement uses exact node coordinate sets, public ports,
unchanged instance/terminal attachments and resistor adjacency. A unique color
must identify every node before comparing all mapped R/C branches and device
parameters. Numeric comparisons use only printed significant-digit intervals.
Failure or unresolved color collisions are retained, never waived.
"""
from collections import Counter,defaultdict
from decimal import Decimal
import hashlib,json,shlex
from pathlib import Path
from audit_active_dco_rc_capacitance import parse,terminals
from run_dco_qualification import ROOT,sha,save


def load(folder):
    spice=next(folder.glob('*.rcx.spice'));ext=next(folder.glob('*.res.ext'));d=parse(spice)
    coords=defaultdict(set)
    for line in ext.open():
        if line.startswith('rnode '):
            f=shlex.split(line);coords[f[1]].add((int(f[4]),int(f[5])))
    nodes=set(d['ports']);attachments=defaultdict(list);adj=defaultdict(list)
    for p in d['ports']:attachments[p].append(('port',p))
    for name,row in d['X'].items():
        for i,n in enumerate(row[:terminals(row)]):nodes.add(n);attachments[n].append((name,i))
    for a,b,r in d['R']:nodes.update([a,b]);adj[a].append(b);adj[b].append(a)
    for a,b,c in d['C']:nodes.update([a,b])
    assert all(n in coords for n in nodes)
    attrs={n:(tuple(sorted(coords[n])),tuple(sorted(attachments[n]))) for n in nodes}
    return d,nodes,attrs,adj


def colors(attributes):
    keys=sorted(set(attributes.values()),key=repr);ids={v:i for i,v in enumerate(keys)}
    return {k:ids[v] for k,v in attributes.items()}


def numeric_matrix(rows,resolve):
    result=defaultdict(Decimal);rounding=defaultdict(Decimal)
    for a,b,v in rows:
        k=tuple(sorted([resolve(a),resolve(b)]));result[k]+=v
        # Native exporters print six significant digits; both endpoints' rounded
        # values are treated as intervals, without global aggregate tolerances.
        if v:rounding[k]+=Decimal(10)**(v.copy_abs().adjusted()-5)/2
    return dict(result),dict(rounding)


def compare(left,right):
    a,an,aa,ad=load(left);b,bn,ba,bd=load(right)
    assert a['ports']==b['ports'] and a['X'].keys()==b['X'].keys()
    # Unattached internal-node coordinate labels can change when native
    # zero-R junction merges choose a different representative point. Retain
    # those differences; fixed public/device anchors and all common coordinate
    # labels remain mandatory in the electrical graph comparison.
    hist_a,hist_b=Counter(aa.values()),Counter(ba.values())
    common={v for v in hist_a if hist_a[v]==hist_b.get(v)}
    unstable=[(i,n,v) for i,rows in [(0,aa),(1,ba)] for n,v in rows.items() if v not in common]
    assert all(not v[1] for i,n,v in unstable),'device or public terminal coordinate changed'
    attrs={(i,n):(v if v in common else ((),())) for i,rows in [(0,aa),(1,ba)] for n,v in rows.items()}
    c=colors(attrs);iterations=[]
    for iteration in range(30):
        hist=[Counter(c[i,n] for n in ns) for i,ns in [(0,an),(1,bn)]]
        iterations.append(dict(iteration=iteration,colors=len(set(c.values())),maximum_class_multiplicity=max(hist[0].values()),
            equal_class_counts=hist[0]==hist[1]))
        if hist[0]!=hist[1]:return dict(graph_classes_match=False,iterations=iterations)
        if max(hist[0].values())==1:break
        nxt={(i,n):(c[i,n],tuple(sorted(c[i,m] for m in adj[n]))) for i,ns,adj in [(0,an,ad),(1,bn,bd)] for n in ns}
        updated=colors(nxt)
        if len(set(updated.values()))==len(set(c.values())):break
        c=updated
    ha=Counter(c[0,n] for n in an);hb=Counter(c[1,n] for n in bn)
    unique=ha==hb and max(ha.values())==1
    if not unique:return dict(graph_classes_match=ha==hb,unique_mapping=False,iterations=iterations,
        unresolved_class_sizes=dict(Counter(ha.values())))
    right_by_color={c[1,n]:n for n in bn};mapping={n:right_by_color[c[0,n]] for n in an}
    device_differences=[]
    for name,row in a['X'].items():
        other=b['X'][name];count=terminals(row)
        if [mapping[n] for n in row[:count]]!=other[:count] or row[count:]!=other[count:]:device_differences.append(name)
    edge_counts_a=Counter(tuple(sorted([mapping[x],mapping[y]])) for x,y,v in a['R'])
    edge_counts_b=Counter(tuple(sorted([x,y])) for x,y,v in b['R'])
    changes={}
    for kind in ['R','C']:
        ma,pa=numeric_matrix(a[kind],lambda n:mapping[n]);mb,pb=numeric_matrix(b[kind],lambda n:n)
        rows=[]
        for k in ma.keys()|mb.keys():
            delta=mb.get(k,Decimal(0))-ma.get(k,Decimal(0));allow=pa.get(k,Decimal(0))+pb.get(k,Decimal(0))
            if abs(delta)>allow:rows.append(dict(nodes=list(k),delta=str(delta),allowance=str(allow)))
        changes[kind]=rows
    return dict(graph_classes_match=True,unique_mapping=True,iterations=iterations,mapped_nodes=len(mapping),
        renamed_nodes=sum(k!=v for k,v in mapping.items()),unchanged_device_parameters_and_mapped_terminals=not device_differences,
        device_differences=device_differences,exact_mapped_R_branch_multiplicity_preserved=edge_counts_a==edge_counts_b,
        numeric_R_C_within_per_branch_print_intervals=not any(changes.values()),R_C_differences=changes,
        node_mapping=mapping,
        internal_node_coordinate_changes=[dict(left=n,right=mapping[n],left_coordinates=aa[n][0],right_coordinates=ba[mapping[n]][0]) for n in an if aa[n][0]!=ba[mapping[n]][0]])


def main():
    base=ROOT/'build/timing400/release_001';source=base/'DCO_R_node_trace_controls_001'
    out=base/'DCO_R_default_network_renaming_audit_003';out.mkdir(exist_ok=False)
    r=compare(source/'installed',source/'isolated');mapping=r.pop('node_mapping',None)
    save(out/'comparison.json',r)
    if mapping:save(out/'node_mapping.json',mapping)
    paths=[Path(__file__).resolve(),Path(__file__).with_name('audit_active_dco_rc_capacitance.py'),
        *[p for label in ['installed','isolated'] for p in (source/label).glob('*') if p.suffix in ['.spice','.ext']]]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={str(p):sha(p) for p in out.iterdir()},
        exact_internal_node_renaming_proven=r.get('unique_mapping',False),
        complete_electrical_equivalence_within_native_print_intervals=r.get('unique_mapping',False) and not r.get('device_differences',[1]) and r.get('exact_mapped_R_branch_multiplicity_preserved',False) and r.get('numeric_R_C_within_per_branch_print_intervals',False),
        spatial_physical_model_qualified=False,release_qualified=False,adopted=False))
    print({k:v for k,v in r.items() if k not in ['R_C_differences','device_differences','internal_node_coordinate_changes']})


if __name__=='__main__':main()
