"""Resolve retained state-cell reset pins and their held native exterior biases."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from compare_prototype_physical_primitive_graphs import parsed,Union
from resolve_prototype_loaded_halo_interfaces import local_bindings
from check_selected_boundary_waveforms import bind
from audit_selected_dco_history_inputs import sources


def run(drivers,loads,snapshot,target,output):
    if output.exists():raise FileExistsError(output)
    d,l,s=[json.loads(p.read_text()) for p in [drivers,loads,snapshot/'assessment.json']]
    for x in [d,l]:verify(x['input_sha256'])
    verify(s['artifacts']);verify({p:v for p,v in s['input_sha256'].items() if not p.endswith('/profile.raw')})
    paths=list(map(Path,d['input_sha256']));metadata=next(p for p in paths if p.name=='nodes.json');wire=next(p for p in paths if p.name=='context.spice');hierarchy=next(p for p in paths if p.name=='ng47.spice')
    instances=json.loads(metadata.read_text())['physical_instances'];cells={i['instance']:json.dumps([i['physical_hierarchy_identity'],i['leaf_master']],separators=(',',':')) for i in instances};terms={};union=Union()
    for line in wire.open():
        f=line.split()
        if not f:continue
        if f[0].startswith('Xflat'):
            stop=next(i for i,t in enumerate(f) if t.startswith('sky130_fd_pr__'));terms[f[0]]=f[1:stop]
        elif f[0].startswith('R'):union.join(f[1],f[2])
    manifest=target/'manifest.json';native_manifest=json.loads(manifest.read_text());verify(native_manifest['input_sha256'])
    models=[Path(p) for p in native_manifest['input_sha256'] if p.endswith('/model.spice')]
    if len(models)!=1:raise ValueError('unique actual native model required')
    for line in models[0].open():
        fields=line.split()
        if fields and fields[0][0].upper()=='R':union.join(fields[1],fields[2])
    bound,aliases=local_bindings(instances,terms,cells,parsed(hierarchy.read_text()));selected={r['cell_key']:r for r in l['records']};by_primitives={frozenset(r['primitives']):r for r in bound.values()};exterior=sources(target/'sources.spice');v=json.loads((snapshot/'initial_voltage_vector.json').read_text());records=[]
    for cell in selected.values():
        physical=by_primitives[frozenset(cell['complete_primitives'])];master=physical['master']
        if not any(x in master for x in ['dfrtp','dfstp']):continue
        pins={}
        for port in ['CLK','RESET_B','SET_B','D','Q']:
            local=aliases[master].find(port)
            if local in physical['nodes']:pins[port]=physical['nodes'][local]
        reset='RESET_B' if 'RESET_B' in pins else 'SET_B'
        if reset not in pins:raise ValueError('stateful reset/set pin unresolved')
        node=pins[reset];cuts=[n for n in exterior if union.find(n)==union.find(node)]
        initial=bind([node,*cuts],v['variable_names'])
        if not initial['all_bound']:raise ValueError('state pin absent from recorded initial vector')
        records.append(dict(master=master,primitives=cell['complete_primitives'],pins=pins,reset_or_set_pin=reset,held_exterior_cuts=[dict(node=n,source_expression=exterior[n][1],recorded_initial_voltage=v['values'][initial['bindings'][n]['index']]) for n in cuts],recorded_initial_pin_voltage=v['values'][initial['bindings'][node]['index']]))
    files=[models[0],drivers,loads,snapshot/'assessment.json',snapshot/'initial_voltage_vector.json',target/'manifest.json',target/'sources.spice',Path(__file__).resolve(),Path(__file__).with_name('resolve_prototype_loaded_halo_interfaces.py'),Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py')]
    save(output,dict(input_sha256={str(p):sha(p) for p in files},records=records,stateful_cells=len(records),scope='structural reset/set bias mapping; not a DC failure causal proof',release_ready=False));print(json.dumps(dict(stateful_cells=len(records),held_reset_set_cells=sum(bool(r['held_exterior_cuts']) for r in records),examples=records[:2])))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['drivers','loads','snapshot','target','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['drivers','loads','snapshot','target','output']))
