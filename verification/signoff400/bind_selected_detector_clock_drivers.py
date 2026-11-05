"""Resolve unique physical output drivers of the detector clock resistor nets."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from compare_prototype_physical_primitive_graphs import parsed,Union
from resolve_prototype_loaded_halo_interfaces import local_bindings,library_directions


def run(ports,receivers,metadata,wire,hierarchy,libraries,output):
    if output.exists():raise FileExistsError(output)
    pv,rv=[json.loads(p.read_text()) for p in [ports,receivers]]
    verify(pv['input_sha256']);verify(rv['input_sha256'])
    if rv['input_sha256'].get(str(ports))!=sha(ports):raise ValueError('receiver/port mismatch')
    for p in [metadata,wire,hierarchy]:
        if rv['input_sha256'].get(str(p))!=sha(p):raise ValueError('physical source mismatch')
    pins={str(p):sha(p) for p in [ports,receivers,metadata,wire,hierarchy,libraries,Path(__file__).resolve(),Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py'),Path(__file__).with_name('resolve_prototype_loaded_halo_interfaces.py')]}
    lr=json.loads(libraries.read_text());verify(lr['artifacts']);pins.update(lr['artifacts'])
    directions={}
    for p in lr['artifacts']:directions.update(library_directions(Path(p).read_text()))
    instances=json.loads(metadata.read_text())['physical_instances']
    cells={i['instance']:json.dumps([i['physical_hierarchy_identity'],i['leaf_master']],separators=(',',':')) for i in instances}
    terms={};u=Union()
    for line in wire.open():
        f=line.split()
        if not f:continue
        if f[0].startswith('Xflat'):
            stop=next(i for i,t in enumerate(f) if t.startswith('sky130_fd_pr__'));terms[f[0]]=f[1:stop]
        elif f[0].startswith('R'):u.join(f[1],f[2])
    bound,aliases=local_bindings(instances,terms,cells,parsed(hierarchy.read_text()))
    result={}
    wire_top=next(line.split()[2:] for line in wire.open() if line.startswith('.subckt IntegerPLL_400MHz_PrototypeTop '))
    for role in ['REF','CLKDIVR']:
        component=u.find(pv['ports'][role]['detector_wire_endpoint']);drivers=[]
        for cell in bound.values():
            master=cell['master']
            for pin,direction in directions.get(master,{}).items():
                node=cell['nodes'].get(aliases[master].find(pin))
                if direction=='OUTPUT' and node is not None and u.find(node)==component:
                    drivers.append(dict(master=master,pin=pin,node=node,primitives=cell['primitives']))
        if role=='REF' and not drivers:
            node=pv['ports'][role]['parent_logical_node']
            if node not in wire_top or u.find(node)!=component:raise ValueError('reference primary port conductor mismatch')
            drivers.append(dict(kind='declared_reference_primary_input',node=node))
        if len(drivers)!=1:raise ValueError('unique native output driver required for '+role+': '+json.dumps([{k:v for k,v in d.items() if k!="primitives"} for d in drivers]))
        result[role]=drivers[0]
    verify(pins);save(output,dict(input_sha256=pins,clock_drivers=result,
                                 physical_driver_pins_bound=True,driver_waveforms_qualified=False,release_ready=False))
    print(json.dumps({k:{p:v for p,v in d.items() if p!='primitives'} for k,d in result.items()}))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['ports','receivers','metadata','wire','hierarchy','libraries','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['ports','receivers','metadata','wire','hierarchy','libraries','output']))
