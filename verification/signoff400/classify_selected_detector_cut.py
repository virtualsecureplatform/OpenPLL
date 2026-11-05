"""Attribute every omitted primitive attachment to a physical detector-cut role.

Counts primitive terminals and physical cells separately. Role attribution is a
load obligation inventory, never permission to omit or voltage-clamp a load.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from common_v3 import save,sha,verify
from compare_prototype_physical_primitive_graphs import Union


def classify(loads,items,roles):
    cells={}
    for name,terminals in loads.items():
        item=items[name]
        identity=json.dumps([item['physical_hierarchy_identity'],item['leaf_master']],sort_keys=True,separators=(',',':'))
        key=hashlib.sha256(identity.encode()).hexdigest()
        entry=cells.setdefault(key,dict(master=item['leaf_master'],primitives=[],attachments=[]))
        entry['primitives'].append(name)
        for terminal in terminals:
            entry['attachments'].append(dict(primitive=name,**terminal,
                roles=sorted(roles.get(terminal['component'],[]))))
    for entry in cells.values():
        entry['roles']=sorted({r for t in entry['attachments'] for r in t['roles']})
        entry['has_unattributed_terminal']=any(not t['roles'] for t in entry['attachments'])
        entry['primitives'].sort()
    return cells


def run(cut,ports,receivers,metadata,model,output):
    if output.exists():raise FileExistsError(output)
    values=[json.loads(p.read_text()) for p in [cut,ports,receivers]]
    cv,pv,rv=values
    for value in values:verify(value['input_sha256'])
    for p in [metadata,model]:
        if cv['input_sha256'].get(str(p))!=sha(p):raise ValueError('cut physical identity mismatch')
    if cv['input_sha256'].get(str(receivers))!=sha(receivers):raise ValueError('cut receiver identity mismatch')
    if rv['input_sha256'].get(str(ports))!=sha(ports):raise ValueError('receiver port identity mismatch')
    pins={str(p):sha(p) for p in [cut,ports,receivers,metadata,model,Path(__file__).resolve(),Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py')]}
    u=Union();inside=False
    for line in model.open():
        f=line.split()
        if not f:continue
        if f[0].lower()=='.subckt':inside=f[1]=='IntegerPLL_400MHz_PrototypeTop';continue
        if f[0].lower()=='.ends':inside=False;continue
        if inside and f[0][0].upper()=='R':u.join(f[1],f[2])
    roles=defaultdict(set)
    for role,entry in pv['ports'].items():roles[u.find(entry['detector_wire_endpoint'])].add(role)
    event_cells=[c for c in rv['selected_cells'] if 'D' in c['pins'] and 'CLK' in c['pins']]
    for index,cell in enumerate(event_cells):
        for pin,node in cell['pins'].items():
            if pin not in ['VPWR','VGND','VPB','VNB']:roles[u.find(node)].add(f'event{index}.{pin}')
    for cells in rv['downstream_sequential_output_cells'].values():
        for cell in cells:
            for pin,node in cell['pins'].items():
                if pin not in ['VPWR','VGND','VPB','VNB']:roles[u.find(node)].add('synchronizer.'+pin)
    items={i['instance']:i for i in json.loads(metadata.read_text())['physical_instances']}
    cells=classify(cv['external_primitive_terminals'],items,roles)
    summary=Counter((tuple(c['roles']),c['master']) for c in cells.values())
    result=dict(input_sha256=pins,cells=cells,
                role_cell_counts=[dict(roles=list(roles),master=master,cells=count) for (roles,master),count in sorted(summary.items())],
                external_primitive_count=len(cv['external_primitive_terminals']),external_physical_cell_count=len(cells),
                all_external_terminals_attributed=all(not c['has_unattributed_terminal'] for c in cells.values()),
                role_attribution_qualifies_loading=False,receiver_loading_bounded=False,
                physical_models_qualified=False,release_ready=False)
    verify(pins);save(output,result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['cut','ports','receivers','metadata','model','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=run(*(getattr(a,n).resolve() for n in ['cut','ports','receivers','metadata','model','output']))
    print(json.dumps({k:r[k] for k in ['external_primitive_count','external_physical_cell_count','role_cell_counts','all_external_terminals_attributed']}))
