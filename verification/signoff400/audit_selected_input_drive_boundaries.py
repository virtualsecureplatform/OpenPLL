"""Classify every retained cell input by its actual physical wire-R driver boundary."""
import argparse,json,os
from pathlib import Path
from common_v3 import save,sha,verify
from compare_prototype_physical_primitive_graphs import parsed,Union
from resolve_prototype_loaded_halo_interfaces import local_bindings,library_directions
from protected_passive_cut import RAILS


def run(plan,output):
    if output.exists():raise FileExistsError(output)
    p=json.loads(plan.read_text());verify(p['input_sha256']);paths=list(map(Path,p['input_sha256']))
    metadata=next(x for x in paths if x.name=='nodes.json');wire=next(x for x in paths if x.name=='context.spice');hierarchy=next(x for x in paths if x.name=='ng47.spice');model=next(x for x in paths if x.name=='model.spice');library=next(x for x in paths if x.parent.name=='selected_detector_library_inputs_185' and x.name=='assessment.json')
    lib=json.loads(library.read_text());verify(lib['artifacts']);directions={}
    for name in lib['artifacts']:directions.update(library_directions(Path(name).read_text()))
    instances=json.loads(metadata.read_text())['physical_instances'];cells={i['instance']:json.dumps([i['physical_hierarchy_identity'],i['leaf_master']],sort_keys=True,separators=(',',':')) for i in instances};terms={}
    for line in wire.open():
        f=line.split()
        if f and f[0].startswith('Xflat'):
            stop=next(i for i,t in enumerate(f) if t.startswith('sky130_fd_pr__'));terms[f[0]]=f[1:stop]
    bound,aliases=local_bindings(instances,terms,cells,parsed(hierarchy.read_text()));u=Union()
    for line in model.open():
        f=line.split()
        if f and f[0][0].upper()=='R':u.join(f[1],f[2])
    selected=set(p['selected_primitives']);retained=[];drivers={}
    for key,cell in bound.items():
        names=set(cell['primitives'])
        if names&selected:
            if not names<=selected:raise ValueError('partial retained cell')
            retained.append((key,cell))
        for port,direction in directions[cell['master']].items():
            if direction!='OUTPUT':continue
            local=aliases[cell['master']].find(port)
            if local not in cell['nodes']:raise ValueError('unbound output port')
            node=cell['nodes'][local];drivers.setdefault(u.find(node),[]).append(dict(cell_key=key,master=cell['master'],pin=port,node=node,retained=names<=selected))
    boundaries={u.find(n) for n in p['required_non_supply_boundary_voltage_nodes']};rails={u.find(n) for n in RAILS};records=[]
    for key,cell in retained:
        for port,direction in directions[cell['master']].items():
            if direction!='INPUT':continue
            local=aliases[cell['master']].find(port)
            if local not in cell['nodes']:raise ValueError('unbound input port')
            node=cell['nodes'][local];root=u.find(node);drive=drivers.get(root,[])
            kind='supply' if root in rails else 'retained_output' if any(d['retained'] for d in drive) else 'prescribed_exterior' if root in boundaries else 'unprescribed_without_retained_output'
            records.append(dict(cell_key=key,master=cell['master'],pin=port,node=node,component=root,drive_class=kind,physical_output_drivers=drive))
    files=[plan,Path(__file__).resolve(),Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py'),Path(__file__).with_name('resolve_prototype_loaded_halo_interfaces.py')]
    pins=dict(p['input_sha256']);pins.update({str(x):sha(x) for x in files})
    missing=[r for r in records if r['drive_class']=='unprescribed_without_retained_output']
    save(output,dict(input_sha256=pins,retained_cells=len(retained),input_pins_checked=len(records),unprescribed_input_pins_without_retained_output=missing,unprescribed_components=sorted({r['component'] for r in missing}),records=records,DC_failure_cause_identified=False,release_ready=False))
    print('input pins',len(records),'unprescribed pins',len(missing),'components',len({r['component'] for r in missing}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();os.sched_setaffinity(0,{29});run(a.plan.resolve(),a.output.resolve())
