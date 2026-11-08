"""Audit flat DCO resistor ownership and exact capacitor cut boundaries; no model reduction."""
import argparse
import json
import shlex
from collections import Counter, defaultdict
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save, sha, verify
from audit_keeper_flat_MOS_region_join import Aliases
from native_spice_comments import strip_floating_annotation

def run(flat, regions, mos, output):
    receipts=[p/'assessment.json' for p in [flat,regions,mos]]
    a,r,m=[json.loads(p.read_text()) for p in receipts]
    for value in [a,r,m]:
        verify(value['input_sha256']); verify(value.get('artifacts',{}))
    if not m['all_MOS_region_ownership_verified']:
        raise ValueError('unambiguous MOS region ownership required')
    ext=flat/'IntegerPLL_400MHz_KeeperFlatC.ext'; spice=flat/'capacitance.spice'
    mapping=mos/'MOS_regions.json'
    if m['input_sha256'].get(str(ext))!=sha(ext) or m['input_sha256'].get(str(spice))!=sha(spice):
        raise ValueError('same flat sources required')
    files=[*receipts,ext,spice,mapping,Path(__file__).resolve(),Path(__file__).with_name('audit_keeper_flat_MOS_region_join.py'),Path(__file__).with_name('native_spice_comments.py')]
    pins={str(p):sha(p) for p in files}; aliases=Aliases()
    for line in ext.open():
        if line.startswith('equiv '):
            f=shlex.split(line); aliases.union(f[1],f[2])
    grid=F(r['EXT_coordinate_unit_um']); unit=F(r['GDS_coordinate_unit_um'])
    boxes={n:[F(v)*unit/grid for v in p['bbox_dbu']] for n,p in r['physical_macro_placements'].items()}
    def key(model,l,w,nodes):
        return model,F(l),F(w),tuple(sorted(aliases.find(n) for n in nodes))
    physical=defaultdict(Counter)
    for line in ext.open():
        if not line.startswith('device rsubckt '): continue
        f=shlex.split(line); i=7; params={}
        while '=' in f[i]:
            n,v=f[i].split('=',1); params[n]=v; i+=1
        if f[2]!='sky130_fd_pr__res_generic_po' or len(f[i:])!=10:
            raise ValueError('unsupported resistor encoding')
        x0,y0,x1,y1=map(int,f[3:7]); inside=[n for n,(a,b,c,d) in boxes.items() if a<=x0 and b<=y0 and x1<=c and y1<=d]
        if len(inside)>1: raise ValueError('overlapping physical regions')
        physical[key(f[2],F(params['l'])*grid,F(params['w'])*grid,[f[i+4],f[i+7]])][inside[0] if inside else 'parent']+=1
    owned=json.loads(mapping.read_text()); emitted=defaultdict(list); primitives=[]; caps=[]; ports=[]
    in_header=False
    for line in spice.open():
        f=strip_floating_annotation(line).split()
        if not f: continue
        if f[0].lower()=='.subckt': ports.extend(f[2:]); in_header=True; continue
        if f[0]=='+':
            if not in_header: raise ValueError('unexpected continuation')
            ports.extend(f[1:]); continue
        in_header=False
        if f[0].startswith('X'):
            j=next((i for i,t in enumerate(f) if '=' in t),len(f))-1
            model=f[j]; nodes=f[1:j]; primitives.append((f[0],nodes))
            if model=='sky130_fd_pr__res_generic_po':
                params=dict(t.split('=',1) for t in f[j+1:]); emitted[key(model,params['l'],params['w'],nodes)].append(f[0])
        elif f[0].startswith('C'):
            value=f[3]
            numeric=F(value[:-1]) if value[-1].lower() in 'fpnumk' else F(value)
            if numeric!=0: caps.append(f[:4])
    errors=[]
    for k in physical.keys() | emitted.keys():
        counts=physical.get(k,{}); names=emitted.get(k,[])
        if len(counts)!=1 or sum(counts.values())!=len(names):
            errors.append(dict(signature=repr(k),physical=dict(counts),emitted=names))
        else:
            owned.update({name:next(iter(counts)) for name in names})
    if sum(map(len,emitted.values()))!=20: raise ValueError('expected 20 poly resistors')
    if errors: raise ValueError('resistor correspondence unresolved: '+repr(errors))
    inside=set(); outside=set(); selected=[]
    for name,nodes in primitives:
        if owned.get(name)=='oscillator': inside.update(nodes); selected.append(name)
        else: outside.update(nodes)
    shared=inside & (outside | set(ports)); private=inside-shared
    counts=Counter(); crossing=[]; touching=[]
    for name,n1,n2,value in caps:
        if n1 not in inside and n2 not in inside: counts['exterior_only']+=1; continue
        touching.append(name)
        if n1 in inside and n2 in inside: counts['both_endpoints_on_DCO']+=1
        else:
            counts['one_endpoint_on_DCO']+=1
            crossing.append(dict(name=name,DCO_node=n1 if n1 in inside else n2,exterior_node=n2 if n1 in inside else n1,value=value))
    verify(pins); output.mkdir(parents=True,exist_ok=False)
    save(output/'boundary.json',dict(selected_primitives=sorted(selected),shared_primitive_nodes=sorted(shared),private_primitive_nodes=sorted(private),touching_capacitors=touching,crossing_capacitors=crossing))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'boundary.json'):sha(output/'boundary.json')},all_20_poly_resistor_regions_verified=True,DCO_primitive_count=len(selected),DCO_MOS_count=sum(owned.get(n)=='oscillator' for n in json.loads(mapping.read_text())),DCO_poly_resistor_count=len(selected)-sum(owned.get(n)=='oscillator' for n in json.loads(mapping.read_text())),DCO_primitive_node_count=len(inside),shared_primitive_node_count=len(shared),private_primitive_node_count=len(private),nonzero_capacitor_counts=dict(counts),crossing_external_node_count=len({c['exterior_node'] for c in crossing}),circuit_partitioned=False,exterior_nodes_clamped=False,boundary_loading_qualified=False,model_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','regions','mos','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['flat','regions','mos','output']))
