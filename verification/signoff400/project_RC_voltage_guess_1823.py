"""Project completed ideal-wire voltages along exact native wire components only."""
import json,math,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity

def project(edges,active,anchors):
    parent={}
    def root(a):
        parent.setdefault(a,a)
        while parent[a]!=a:parent[a]=parent[parent[a]];a=parent[a]
        return a
    for a,b in edges:parent[root(a)]=root(b)
    values={}
    for node,value in anchors.items():
        if not math.isfinite(value):raise ValueError('nonfinite voltage anchor')
        r=root(node)
        if r in values and values[r]!=value:raise ValueError('conflicting exact ideal-conductor anchors')
        values[r]=value
    missing=[node for node in active if root(node) not in values]
    if missing:raise ValueError('unanchored active nodes: '+str(len(missing))+' '+repr(missing[:8]))
    return {node:values[root(node)]for node in active}

def run():
    os.sched_setaffinity(0,{23});base=ROOT/'build/signoff400';coarse=base/'selected_RC_coarse_guess_DC_1822';receipt=coarse/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    p=json.loads((coarse/'native.process.json').read_text())
    if identity(p['pid'])==p['birth'] or not r['normal_native_exit']:raise ValueError('normally completed ideal-wire voltage source required')
    full=base/'selected_zero_C_backend_model_1810';fr=json.loads((full/'assessment.json').read_text());verify(fr['input_sha256']);verify(fr['artifacts'])
    coarse_map=base/'selected_RC_coarse_guess_model_1821/nodes.json';full_map=base/'selected_reference_alias_native_RC_model_1768/nodes.json'
    paths=[receipt,full/'assessment.json',coarse_map,full_map,Path(__file__).resolve()];pins={str(p):sha(p)for p in paths}
    out=base/'selected_RC_voltage_guess_1823';out.mkdir(exist_ok=False)
    with lease(1,12,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        voltage=r['finite_reset_DC_point'];cv={k.lower():v for k,v in voltage.items()};cm=json.loads(coarse_map.read_text());fm=json.loads(full_map.read_text());anchors={}
        for original,coarse_node in cm.items():
            if original not in fm:continue
            candidates=[cv[k]for k in ['v('+coarse_node.lower()+')','v(xdut:'+coarse_node.lower()+')']if k in cv]
            if candidates:
                if len(set(candidates))!=1:raise ValueError('ambiguous native voltage name')
                anchors[fm[original].lower()]=candidates[0]
        edges=[];active=set();scope=False
        for line in (full/'model.spice').read_text().splitlines():
            f=line.lower().split()
            if not f or f[0].startswith('*'):continue
            if f[0]=='.subckt':scope=not f[1].startswith('__openpll_');continue
            if f[0]=='.ends':scope=False;continue
            if not scope:continue
            if f[0].startswith('r'):edges.append(tuple(f[1:3]));active.update(f[1:3])
            elif f[0].startswith('c'):active.update(f[1:3])
            elif f[0].startswith('xflat'):active.update(f[1:-1])
        guess=project(edges,active,anchors);ports={line.split()[i].lower()for line in (full/'model.spice').read_text().splitlines()if line.startswith('.subckt ')and not line.split()[1].startswith('__openpll_')for i in range(2,len(line.split()))}
        file=out/'nodeset.spice'
        file.write_text('* Newton starting guess only; full wire RC equations remain unchanged.\n'+''.join('.nodeset v('+(''if node in ports or node=='0'else'xdut:')+node+')='+format(v,'.17g')+'\n'for node,v in sorted(guess.items())if node!='0'))
        verify(pins);save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(file):sha(file)},active_nodes_seeded=len(guess),wire_edges_used=len(edges),anchors=len(anchors),projection='exact native wire components; ideal-wire voltages used only as initial guesses',physical_connections_added=False,full_RC_qualified=False,release_ready=False))
if __name__=='__main__':run()
