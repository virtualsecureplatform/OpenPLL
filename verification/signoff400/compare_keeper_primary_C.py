"""Compare primary-port C restrictions with all other conductor voltages fixed."""
import argparse,json,os,time
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from build_prototype_full_C_wire_R_v11 import rows,Union
from audit_hierarchical_capacitance import number
from native_spice_comments import strip_floating_annotation
from project_prototype_fixed_rail_C_v2 import RAILS
from resources import lease


def groups(ports,canonical):
    fixed={canonical(p)for p in RAILS};result=defaultdict(list)
    for p in ports:
        if canonical(p)not in fixed:result[canonical(p)].append(p)
    return {n:tuple(sorted(names))for n,names in result.items()}


def stamp(matrix,a,b,value,mapping):
    if a==b or not value:return
    x,y=mapping.get(a),mapping.get(b)
    if x is not None:matrix[(x,x)]+=value
    if y is not None:matrix[(y,y)]+=value
    if x is not None and y is not None:matrix[tuple(sorted((x,y)))]-=value


def hierarchy_aliases(text,top):
    parsed={name:(r[0].split()[2:],r[1:-1])for name,block in subcircuits(text).items()for r in [rows(block)]};aliases=Union()
    def visit(name,path,bindings):
        ports,body=parsed[name];links=dict(zip(ports,bindings))
        if len(ports)!=len(bindings):raise ValueError('hierarchical arity mismatch')
        def node(n):return '0'if n=='0'else links.get(n,path+'/'+n)
        for line in body:
            f=line.split()
            if f[0].startswith('R'):
                if len(f)!=4 or number(f[-1])!=0:raise ValueError('source must have zero-R aliases only')
                aliases.join(node(f[1]),node(f[2]))
            elif f[0].startswith('X'):
                positional=[t for t in f[1:]if '='not in t];model=positional[-1]
                if model in parsed:visit(model,path+'/'+f[0],[node(n)for n in positional[:-1]])
    ports=parsed[top][0];visit(top,top,ports);return ports,aliases.find


def run(projected,native,output):
    receipts=[p/'assessment.json'for p in [projected,native]];h,n=[json.loads(p.read_text())for p in receipts]
    for r in [h,n]:verify(r['input_sha256']);verify(r['artifacts'])
    sources=[Path(p)for p in h['input_sha256']if p.endswith('/capacitance.spice')]
    if len(sources)!=1:raise ValueError('one original hierarchical source required')
    source=sources[0];pairs=projected/'dynamic.pairs.jsonl';exports=[Path(p)for p in n['artifacts']if p.endswith('/signed_threshold.spice')]
    if len(exports)!=1:raise ValueError('one native signed export required')
    flat=exports[0];output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{24});folder=Path(__file__).resolve().parent;files=[*receipts,source,pairs,flat,Path(__file__).resolve(),folder/'build_prototype_full_C_wire_R_v11.py',folder/'native_spice_comments.py'];pins={str(p):sha(p)for p in files}
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        ports,canonical=hierarchy_aliases(source.read_text(),source.parent.name);hg=groups(ports,canonical);hm=defaultdict(F)
        for line in pairs.open():
            r=json.loads(line);stamp(hm,*r['nodes'],F(r['farads']),hg)
        aliases=Union();flat_ports=[];reading=False
        for line in flat.open():
            f=strip_floating_annotation(line).split()
            if not f:continue
            if f[0].lower()=='.subckt':flat_ports=f[2:];reading=True
            elif reading and f[0]=='+':flat_ports.extend(f[1:])
            else:reading=False
            if f[0].startswith('R'):
                if len(f)!=4 or number(f[-1])!=0:raise ValueError('native reference must contain zero-R aliases only')
                aliases.join(f[1],f[2])
        if flat_ports!=ports:raise ValueError('primary port order differs')
        ng=groups(flat_ports,aliases.find);nm=defaultdict(F)
        for line in flat.open():
            f=strip_floating_annotation(line).split()
            if f and f[0].startswith('C'):
                if len(f)!=4:raise ValueError('unreviewed native capacitor syntax')
                if f[3]=='0':continue
                stamp(nm,aliases.find(f[1]),aliases.find(f[2]),number(f[3]),ng)
    hm={k:v for k,v in hm.items()if v};nm={k:v for k,v in nm.items()if v};diff=[]
    for key in sorted(hm.keys()|nm.keys()):
        a,b=hm.get(key,F()),nm.get(key,F())
        if a!=b:diff.append(dict(row_ports=list(key[0]),column_ports=list(key[1]),hierarchical_F=str(a),native_flat_F=str(b),difference_F=str(b-a)))
    detail=output/'differences.json';save(detail,diff);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},primary_ports=len(ports),alias_group_partitions_equal=set(hg.values())==set(ng.values()),differing_matrix_entries=len(diff),primary_restricted_operators_exactly_equal=not diff,hierarchical_primary_groups=len(hg),native_primary_groups=len(ng),all_other_conductor_voltages_fixed=True,intrinsic_device_C_included=False,physical_error_bound_claimed=False,models_modified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['projected','native','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.projected.resolve(),a.native.resolve(),a.output.resolve())
