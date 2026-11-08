"""Inventory electrical anchors relevant to legacy extresist driver selection; no R qualification."""
import argparse,json,shlex
from collections import Counter,defaultdict
from pathlib import Path
from common_v3 import save,sha,verify
from audit_keeper_flat_MOS_region_join import Aliases
from audit_keeper_DCO_driver_C_cut import capacitance
from native_spice_comments import strip_floating_annotation

def run(flat,output):
    receipt=flat/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    ext=flat/'IntegerPLL_400MHz_KeeperFlatC.ext';spice=flat/'capacitance.spice';folder=Path(__file__).resolve().parent
    pins={str(p):sha(p) for p in [receipt,ext,spice,Path(__file__).resolve(),*[folder/n for n in ['audit_keeper_flat_MOS_region_join.py','audit_keeper_DCO_driver_C_cut.py','native_spice_comments.py']]]}
    aliases=Aliases()
    for line in ext.open():
        if line.startswith('equiv '):
            f=shlex.split(line);aliases.union(f[1],f[2])
    anchors=defaultdict(Counter);labels=defaultdict(set);cap_nodes=set();ports=set();header=False
    for raw in spice.open():
        f=strip_floating_annotation(raw).split()
        if not f:continue
        if f[0].lower()=='.subckt':ports.update(aliases.find(n) for n in f[2:]);header=True;continue
        if f[0]=='+':
            if not header:raise ValueError('only header continuations supported')
            ports.update(aliases.find(n) for n in f[1:]);continue
        header=False
        if f[0].startswith('X'):
            j=next((i for i,t in enumerate(f) if '=' in t),len(f))-1;model=f[j];nodes=f[1:j]
            if 'nfet' in model or 'pfet' in model:
                if len(nodes)!=4:raise ValueError('four-terminal MOS required')
                roles=['MOS_diffusion','MOS_gate','MOS_diffusion','MOS_body']
            elif model=='sky130_fd_pr__res_generic_po':roles=['poly_resistor_terminal']*2
            elif model=='sky130_fd_pr__diode_pw2nd_05v5':roles=['diode_terminal']*2
            else:raise ValueError('unrecognized primitive '+model)
            if len(roles)!=len(nodes):raise ValueError('terminal count differs')
            for n,role in zip(nodes,roles):
                key=aliases.find(n);anchors[key][role]+=1;labels[key].add(n)
        elif f[0].startswith('C') and capacitance(f[3]):
            for n in f[1:3]:
                key=aliases.find(n);cap_nodes.add(key);labels[key].add(n)
    records=[];patterns=Counter()
    for node in sorted(cap_nodes):
        if anchors[node]['MOS_diffusion']:continue
        roles=anchors[node];pattern=','.join(sorted(roles)) or 'no_primitive_terminal';patterns[(pattern,node in ports)]+=1
        records.append(dict(canonical_node=node,native_labels=sorted(labels[node]),top_formal_port=node in ports,primitive_terminal_counts=dict(roles)))
    verify(pins);output.mkdir(parents=True,exist_ok=False);save(output/'without_MOS_diffusion.json',records)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'without_MOS_diffusion.json'):sha(output/'without_MOS_diffusion.json')},nonzero_C_conductor_nodes=len(cap_nodes),nodes_with_MOS_diffusion=sum(bool(anchors[n]['MOS_diffusion']) for n in cap_nodes),nodes_without_MOS_diffusion=len(records),without_diffusion_top_formal_ports=sum(r['top_formal_port'] for r in records),without_diffusion_internal_nodes=sum(not r['top_formal_port'] for r in records),patterns=[dict(roles=p,top_formal_port=port,count=n) for (p,port),n in sorted(patterns.items())],predicts_exact_native_extresist_skip_set=False,drive_location_and_device_resistance_still_require_native_coverage_audit=True,distributed_wire_R_qualified=False,model_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.flat.resolve(),a.output.resolve())
