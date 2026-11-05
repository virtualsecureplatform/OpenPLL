"""Lift the complete hierarchical C network onto routed wire nodes without splitting compensation pairs.

The capacitance lift is a one-hot voltage map (a matrix congruence), not a spatial
capacitance reconstruction. Driver/farthest attachment are diagnostic placement
variants. Neither variant is a qualified distributed-capacitance extraction.
"""
from collections import Counter,defaultdict
from fractions import Fraction as F
import heapq,re
from prepare_prototype_analog_reference import subcircuits
from bind_prototype_spef_pins_v2 import hierarchy,bind
from audit_hierarchical_capacitance import number
from build_prototype_DCO_rc import decimal


class Union:
    def __init__(self):self.parent={}
    def find(self,n):
        self.parent.setdefault(n,n)
        if self.parent[n]!=n:self.parent[n]=self.find(self.parent[n])
        return self.parent[n]
    def join(self,a,b):self.parent[self.find(a)]=self.find(b)


def rows(text):
    result=[]
    for line in text.splitlines():
        if line.startswith('+'):result[-1]+=' '+line[1:]
        elif line.strip() and not line.startswith('*'):result.append(line)
    return result


def expand(blocks,top,overrides=None,omit_root_aliases=False):
    parsed={name:(r[0].split()[2:],r[1:-1]) for name,text in blocks.items() for r in [rows(text)]}
    aliases=Union();caps=[];devices=[];used=set()
    def visit(name,path,bindings,stack):
        if name in stack:raise ValueError('recursive cell hierarchy')
        ports,body=parsed[name]
        if len(ports)!=len(bindings):raise ValueError('cell interface arity mismatch')
        links=dict(zip(ports,bindings))
        def node(n):return '0' if n=='0' else links.get(n,path+'/'+n)
        for row in body:
            fields=row.split();kind=fields[0][0].upper()
            if kind=='C':
                if len(fields)!=4:raise ValueError('constant capacitors required')
                caps.append((node(fields[1]),node(fields[2]),number(fields[3])))
            elif kind=='R':
                if len(fields)!=4 or number(fields[-1])!=0:raise ValueError('capacitance reference must contain only zero-R aliases')
                if not(path==top and omit_root_aliases):aliases.join(node(fields[1]),node(fields[2]))
            elif kind=='X':
                positional=[];params=[]
                for token in fields[1:]:
                    if '=' in token:params.append(token)
                    elif params:raise ValueError('positional token after device parameters')
                    else:positional.append(token)
                model=positional[-1];nodes=[node(n) for n in positional[:-1]]
                if model in parsed:
                    if params:raise ValueError('parameterized hierarchy requires explicit specialization')
                    if path==top and overrides:
                        for i,pin in enumerate(parsed[model][0]):
                            key=(fields[0][1:],pin)
                            if key in overrides:nodes[i]=overrides[key];used.add(key)
                    visit(model,path+'/'+fields[0],nodes,stack+[name])
                elif model.startswith('sky130_fd_pr__'):devices.append((model,nodes,tuple(params)))
                else:raise ValueError('unresolved primitive model: '+model)
            else:raise ValueError('unsupported extracted element: '+row)
    ports=parsed[top][0];visit(top,top,ports,[])
    pairs=defaultdict(F)
    for a,b,c in caps:
        a,b=aliases.find(a),aliases.find(b)
        if a!=b:pairs[tuple(sorted((a,b)))]+=c
    return ports,[(m,tuple(aliases.find(n) for n in ns),p) for m,ns,p in devices],{k:v for k,v in pairs.items() if v},aliases,used


def build(text,top,spef,mapping,attachment='driver'):
    if attachment not in ('driver','farthest'):raise ValueError('explicit attachment variant required')
    checked=bind(spef,text,top,mapping)
    if not checked['all_RC_terminals_bound_and_connected']:raise ValueError('all wire terminals must bind to the extracted conductor')
    blocks=subcircuits(text);ports,original,capacitance,old_aliases,_=expand(blocks,top)
    _,instances,canonical=hierarchy(text,top)
    tokens={t['node'] for n in spef['nets'] for t in n['connections']}
    tokens.update(v for n in spef['nets'] for r in n['resistors'] for v in r['nodes'])
    primary={t['node'] for n in spef['nets'] for t in n['connections'] if t['kind']=='P'}
    if not primary.issubset(ports):raise ValueError('SPEF primary ports differ from extracted interface')
    wire_names={t:t if t in primary else top+'/__wire_'+str(i) for i,t in enumerate(sorted(tokens))}
    if any('/__wire_' in n for pair in capacitance for n in pair):raise ValueError('reserved wire namespace collision')
    overrides={};anchors={};wire=[];reverse_seeds=[]
    for net,network in zip(spef['nets'],checked['networks']):
        if net['name']!=network['net']:raise ValueError('binding order changed')
        logical=network['logical_nodes']
        if len(logical)!=1:raise ValueError('one original conductor per routed wire network required')
        old=old_aliases.find(logical[0] if logical[0] in ports or logical[0]=='0' else top+'/'+logical[0])
        drivers=[t['node'] for t in net['connections'] if (t['kind']=='I' and t['direction']=='O') or (t['kind']=='P' and t['direction']=='I')]
        if len(drivers)!=1:raise ValueError('one routed driver required: '+net['name'])
        graph=defaultdict(list)
        for r in net['resistors']:
            value=F(r['ohms']);a,b=r['nodes']
            if value<=0:raise ValueError('positive wire resistance required')
            graph[a].append((b,value));graph[b].append((a,value));wire.append((wire_names[a],wire_names[b],value))
        distance={drivers[0]:F()};queue=[(F(),drivers[0])]
        while queue:
            d,a=heapq.heappop(queue)
            if distance[a]!=d:continue
            for b,value in graph[a]:
                candidate=d+value
                if b not in distance or candidate<distance[b]:distance[b]=candidate;heapq.heappush(queue,(candidate,b))
        local={t['node'] for t in net['connections']}|set(graph)
        if not local.issubset(distance):raise ValueError('disconnected resistor component')
        chosen=drivers[0] if attachment=='driver' else max(distance,key=lambda n:(distance[n],n))
        if old in anchors:raise ValueError('one original conductor mapped to multiple wire networks')
        anchors[old]=wire_names[chosen]
        reverse_seeds.extend((wire_names[n],old) for n in local)
        for t in net['connections']:
            if t['kind']=='I':
                inst,pin=t['node'].rsplit(':',1);inst=re.sub(r'\\(.)',r'\1',inst);key=(mapping[inst],pin)
                if key in overrides:raise ValueError('terminal occurs in multiple wire networks')
                overrides[key]=wire_names[t['node']]
    _,rewired,_,new_aliases,used=expand(blocks,top,overrides,True)
    if used!=overrides.keys():raise ValueError('not every routed terminal was applied')
    lift={n:new_aliases.find(anchors.get(n,n)) for pair in capacitance for n in pair}
    lifted=defaultdict(F)
    for (a,b),value in capacitance.items():
        a,b=lift[a],lift[b]
        if a!=b:lifted[tuple(sorted((a,b)))]+=value
    lifted={k:v for k,v in lifted.items() if v}
    # Independently contract all routed resistors and check the original exact
    # primitive cards and C operator, including signed compensation terms.
    contract=Union()
    for a,b,_ in wire:contract.join(new_aliases.find(a),new_aliases.find(b))
    labels={}
    def label(n,old):
        n=contract.find(n)
        if n in labels and labels[n]!=old:raise ValueError('wire contraction shorts original conductors')
        labels[n]=old
    for n,old in reverse_seeds:label(new_aliases.find(n),old)
    for before,after in zip(original,rewired):
        if before[0]!=after[0] or before[2]!=after[2] or len(before[1])!=len(after[1]):raise ValueError('primitive geometry changed')
        for old,n in zip(before[1],after[1]):label(n,old)
    if len(original)!=len(rewired):raise ValueError('primitive inventory changed')
    for old,n in lift.items():label(n,old)
    projected=defaultdict(F)
    for (a,b),value in lifted.items():
        a,b=labels[contract.find(a)],labels[contract.find(b)]
        if a!=b:projected[tuple(sorted((a,b)))]+=value
    if {k:v for k,v in projected.items() if v}!=capacitance:raise ValueError('zero-wire-R capacitance operator differs')
    recovered=[(m,tuple(labels[contract.find(n)] for n in ns),p) for m,ns,p in rewired]
    if Counter(original)!=Counter(recovered):raise ValueError('zero-wire-R device topology differs')
    nodes=set(ports)
    nodes.update(n for _,ns,_ in rewired for n in ns);nodes.update(n for pair in lifted for n in pair);nodes.update(n for a,b,_ in wire for n in (new_aliases.find(a),new_aliases.find(b)))
    names={n:n if n in ports or n=='0' else '__flat_'+str(i) for i,n in enumerate(sorted(nodes))}
    result=['* Diagnostic complete hierarchical C with distributed wire R; C placement uncertainty remains open.','.subckt '+top+' '+' '.join(ports)]
    result.extend('Xflat'+str(i)+' '+' '.join(names[n] for n in ns)+' '+m+(' '+' '.join(p) if p else '') for i,(m,ns,p) in enumerate(rewired))
    result.extend('Cflat'+str(i)+' '+names[a]+' '+names[b]+' '+decimal(v) for i,((a,b),v) in enumerate(sorted(lifted.items())))
    result.extend('Rwire'+str(i)+' '+names[new_aliases.find(a)]+' '+names[new_aliases.find(b)]+' '+decimal(v) for i,(a,b,v) in enumerate(wire))
    result.append('.ends '+top)
    return '\n'.join(result)+'\n',dict(attachment=attachment,primitive_instances=len(original),original_aggregated_capacitors=len(capacitance),lifted_aggregated_capacitors=len(lifted),wire_resistors=len(wire),rewired_cell_pins=len(used),one_hot_capacitance_voltage_map=True,zero_wire_R_exact_device_topology_and_C_operator_match=True,wire_capacitance_from_SPEF_added=False,spatial_capacitance_placement_qualified=False),lift
