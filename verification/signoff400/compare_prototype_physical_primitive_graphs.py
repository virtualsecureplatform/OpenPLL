"""Compare active primitive graphs through native placement identities.

Instance counters and conductor representatives may change during extraction.
Pair retained cells by master and exact native transform, require unchanged
local primitive cards, and prove a bijection of all primitive terminal nets
with named top ports fixed. Capacitor-only nodes are outside this comparison.
"""
from collections import Counter,defaultdict
from pathlib import Path
import shlex
from prepare_prototype_analog_reference import subcircuits
from audit_hierarchical_capacitance import number


class Union:
    def __init__(self):self.parent={}
    def find(self,n):
        self.parent.setdefault(n,n)
        while self.parent[n]!=n:
            self.parent[n]=self.parent[self.parent[n]];n=self.parent[n]
        return n
    def join(self,a,b):self.parent[self.find(a)]=self.find(b)


def parsed(text):
    result={}
    for model,block in subcircuits(text).items():
        rows=[]
        for line in block.splitlines():
            if line.startswith('+'):rows[-1]+=' '+line[1:]
            elif line.strip() and not line.startswith('*'):rows.append(line)
        ports=rows[0].split()[2:];body=[]
        for line in rows[1:-1]:
            if not line.startswith(('X','x','R','r')):continue
            f=line.split()
            if f[0][0].upper()=='R':
                if len(f)!=4 or number(f[3])!=0:raise ValueError('only exact zero-R aliases supported')
                body.append(('alias',f[1],f[2]));continue
            positional=[];parameters=[]
            for token in f[1:]:
                if '=' in token:
                    k,v=token.split('=',1);parameters.append((k.lower(),str(number(v))))
                elif parameters:raise ValueError('positional token after primitive parameters')
                else:positional.append(token)
            kind=positional[-1];nodes=tuple(positional[:-1])
            body.append(('instance',f[0],kind,nodes,tuple(sorted(parameters))))
        result[model]=(ports,body)
    return result


def use_table(folder,model):
    path=folder/(model+'.ext');uses={};scale=None
    with path.open() as stream:
        for line in stream:
            if line.startswith('scale '):scale=line.strip()
            if not line.startswith('use '):continue
            f=shlex.split(line)
            if len(f)!=9:raise ValueError('scalar native instance transform required')
            if f[2] in uses:raise ValueError('duplicate native instance identifier')
            uses[f[2]]=(f[1],*map(int,f[3:]))
    if scale is None:raise ValueError('native extraction scale missing')
    return scale,uses


def expand(models,top,folder):
    alias=Union();table={};primitives={};used_geometry={};master_cards={}
    for master,(_,body) in models.items():
        master_cards[master]=Counter((r[2],r[3],r[4]) for r in body if r[0]=='instance' and r[2].startswith('sky130_fd_pr__'))
    def visit(master,rawpath,identity,bindings,stack):
        if master in stack:raise ValueError('recursive hierarchy')
        ports,body=models[master]
        if len(ports)!=len(bindings):raise ValueError('hierarchical port count mismatch')
        links=dict(zip(ports,bindings));ordinals=defaultdict(int)
        def node(n):return '0' if n=='0' else links.get(n,rawpath+'/'+n)
        for r in body:
            if r[0]=='alias':alias.join(node(r[1]),node(r[2]));continue
            _,name,kind,ns,params=r
            if kind in models:
                if params:raise ValueError('parameterized hierarchy requires specialization')
                if master not in table:table[master]=use_table(folder,master)
                scale,uses=table[master];instance=name[1:]
                if instance not in uses:raise ValueError('SPICE instance absent from native geometry: '+name)
                placement=uses[instance]
                if placement[0]!=kind:raise ValueError('native master and SPICE hierarchy differ')
                child=identity+((master,scale,placement),)
                if child in used_geometry:raise ValueError('ambiguous coincident retained instances')
                used_geometry[child]=rawpath+'/'+name
                visit(kind,rawpath+'/'+name,child,[node(n) for n in ns],stack+[master])
            elif kind.startswith('sky130_fd_pr__'):
                signature=(kind,ns,params);ordinal=ordinals[signature];ordinals[signature]+=1
                key=(identity,master,signature,ordinal)
                if key in primitives:raise ValueError('duplicate physical primitive identity')
                primitives[key]=(kind,tuple(node(n) for n in ns),params)
            else:raise ValueError('unresolved primitive model')
    visit(top,top,(),models[top][0],[])
    return models[top][0],primitives,alias,master_cards,used_geometry


def compare(before,after,before_folder,after_folder,top):
    a,b=parsed(before),parsed(after)
    pa,da,ua,ca,ga=expand(a,top,before_folder)
    pb,db,ub,cb,gb=expand(b,top,after_folder)
    active_a={m:c for m,c in ca.items() if c};active_b={m:c for m,c in cb.items() if c}
    if active_a!=active_b:raise ValueError('local primitive cards or geometry parameters changed')
    if set(pa)!=set(pb):raise ValueError('named physical top ports differ')
    if da.keys()!=db.keys():raise ValueError('physical primitive instance coverage differs')
    forward={};reverse={}
    def pair(x,y):
        x,y=ua.find(x),ub.find(y)
        if (x in forward and forward[x]!=y) or (y in reverse and reverse[y]!=x):
            raise ValueError('physical primitive terminal connectivity is not bijective')
        forward[x]=y;reverse[y]=x
    for port in pa:pair(port,port)
    pair('0','0')
    for key,(model,ns,params) in da.items():
        other,nn,pp=db[key]
        if model!=other or params!=pp or len(ns)!=len(nn):raise ValueError('paired primitive cards differ')
        for x,y in zip(ns,nn):pair(x,y)
    return dict(physical_primitives=len(da),primitive_masters=len(active_a),previous_retained_cell_instances=len(ga),current_retained_cell_instances=len(gb),
        primitive_terminal_conductors=len(forward),named_top_ports=len(set(pa)),
        all_local_primitive_cards_identical=True,all_physical_primitives_paired=True,
        primitive_terminal_conductor_bijection_verified=True,named_top_port_bindings_preserved=True,
        native_placement_identity_used=True,instance_counter_identity_assumed=False,
        capacitor_only_conductor_identity_claimed=False),forward
