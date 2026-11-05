"""Bind physical consumers after the already measured first synchronizer stage."""
import argparse,json
from collections import defaultdict
from pathlib import Path
from common_v3 import save,sha,verify
from compare_prototype_physical_primitive_graphs import parsed,Union
from resolve_prototype_loaded_halo_interfaces import local_bindings,library_directions


def run(receivers,output):
    if output.exists():raise FileExistsError(output)
    r=json.loads(receivers.read_text());verify(r['input_sha256'])
    def unique(suffix):
        paths=[Path(p) for p in r['input_sha256'] if p.endswith(suffix)]
        if len(paths)!=1:raise ValueError('unique physical source required: '+suffix)
        return paths[0]
    metadata=unique('/nodes.json');wire=unique('/context.spice');hierarchy=unique('/ng47.spice')
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
    directions={}
    for path in r['input_sha256']:
        if path.endswith('.lef'):
            for master,pins in library_directions(Path(path).read_text()).items():
                if master in directions and directions[master]!=pins:raise ValueError('conflicting pin directions')
                directions[master]=pins
    cp={};consumers=defaultdict(list)
    for key,entry in bound.items():
        cp[key]={}
        for pin,direction in directions.get(entry['master'],{}).items():
            node=entry['nodes'].get(aliases[entry['master']].find(pin))
            if node is None:continue
            cp[key][pin]=node
            if direction=='INPUT':consumers[u.find(node)].append((key,pin))
    def describe(key):return dict(cell_key=key,master=bound[key]['master'],primitives=bound[key]['primitives'],pins=cp[key])
    records=[]
    def continuation(start):
        pending=[u.find(start)];seen=set();combinational={};endpoints={}
        while pending:
            component=pending.pop()
            if component in seen:continue
            seen.add(component)
            if len(seen)>64:raise ValueError("unexpectedly large receiver continuation")
            for key,pin in consumers[component]:
                cell=describe(key)
                if "D" in cp[key] and any(p in cp[key] for p in ["CLK","CLK_N","CLKN"]):
                    endpoints[key,pin]=dict(input_pin=pin,cell=cell);continue
                combinational[key]=cell
                for output,direction in directions[cell["master"]].items():
                    if direction=="OUTPUT" and output in cp[key]:pending.append(u.find(cp[key][output]))
        if not endpoints:raise ValueError("next sequential stage missing")
        return dict(combinational_cells=list(combinational.values()),sequential_endpoints=list(endpoints.values()))
    for port in ['BBPD[0]','BBPD[1]']:
        event=r['roles'][port]['event_clock_receiver'];first=r['downstream_sequential_output_cells'][event]
        if len(first)!=1:raise ValueError('unique measured first stage required')
        first=first[0];sinks=consumers[u.find(first['pins']['Q'])]
        if not sinks:raise ValueError('first stage consumers missing')
        records.append(dict(port=port,first_stage=first,consumers=[dict(input_pin=pin,cell=describe(key)) for key,pin in sorted(sinks)],continuation=continuation(first['pins']['Q'])))
    pins=dict(r['input_sha256']);pins.update({str(p):sha(p) for p in [receivers,Path(__file__).resolve()]});verify(pins)
    save(output,dict(input_sha256=pins,records=records,physical_consumer_pins_bound=True,
        later_stage_native_timing_measured=False,full_controller_timing_qualified=False,release_ready=False))
    print(json.dumps([dict(port=x['port'],combinational_cells=len(x['continuation']['combinational_cells']),endpoints=[dict(input_pin=y['input_pin'],master=y['cell']['master'],pins=y['cell']['pins']) for y in x['continuation']['sequential_endpoints']]) for x in records]))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['receivers','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.receivers.resolve(),a.output.resolve())
