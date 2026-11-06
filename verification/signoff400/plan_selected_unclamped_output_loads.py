"""Retain complete load cells while keeping declared input cuts and output wire unknowns."""
import argparse,json,os
from pathlib import Path
from common_v3 import save,sha,verify
from compare_prototype_physical_primitive_graphs import parsed,Union
from resolve_prototype_loaded_halo_interfaces import local_bindings,library_directions
from protected_passive_cut import passive_cut,RAILS


def run(base,loads,output):
    if output.exists():raise FileExistsError(output)
    b,l=[json.loads(p.read_text()) for p in [base,loads]]
    for value in [b,l]:verify(value['input_sha256'])
    if l['input_sha256'].get(str(base))!=sha(base):raise ValueError('same complete-cell load inventory required')
    driver_path=next(Path(p) for p in b['input_sha256'] if p.endswith('/selected_DCO_control_driver_inventory_243.json'))
    driver=json.loads(driver_path.read_text());verify(driver['input_sha256'])
    if any(k in b['input_sha256'] and b['input_sha256'][k]!=v for k,v in driver['input_sha256'].items()):raise ValueError('conflicting physical input lineage')
    dependencies=dict(b['input_sha256'],**driver['input_sha256'])
    paths=list(map(Path,dependencies));metadata=next(p for p in paths if p.name=='nodes.json');wire=next(p for p in paths if p.name=='context.spice');hierarchy=next(p for p in paths if p.name=='ng47.spice');model=next(p for p in paths if p.name=='model.spice');library=next(p for p in paths if p.parent.name=='selected_detector_library_inputs_185' and p.name=='assessment.json')
    lib=json.loads(library.read_text());verify(lib['artifacts']);directions={}
    for name in lib['artifacts']:directions.update(library_directions(Path(name).read_text()))
    instances=json.loads(metadata.read_text())['physical_instances'];items={i['instance']:i for i in instances};cells={i['instance']:json.dumps([i['physical_hierarchy_identity'],i['leaf_master']],sort_keys=True,separators=(',',':')) for i in instances};reference_terms={}
    for line in wire.open():
        f=line.split()
        if f and f[0].startswith('Xflat'):
            stop=next(i for i,t in enumerate(f) if t.startswith('sky130_fd_pr__'));reference_terms[f[0]]=f[1:stop]
    bound,aliases=local_bindings(instances,reference_terms,cells,parsed(hierarchy.read_text()));by_primitives={frozenset(c['primitives']):(key,c) for key,c in bound.items()}
    terms={};passives=[];union=Union();inside=False
    for line in model.open():
        f=line.split()
        if not f:continue
        if f[0].lower()=='.subckt':inside=f[1]=='IntegerPLL_400MHz_PrototypeTop';continue
        if f[0].lower()=='.ends':inside=False;continue
        if not inside:continue
        if f[0].startswith('Xflat'):terms[f[0]]=f[1:1+len(items[f[0]]['local_primitive_signature'][1])]
        elif f[0][0].upper() in ['R','C']:
            passives.append((f[0],f[1],f[2]))
            if f[0][0].upper()=='R':union.join(f[1],f[2])
    if terms.keys()!=items.keys():raise ValueError('complete actual physical primitive graph required')
    prescribed=set(b['prescribed_control_driver_input_nodes'])|{b['prescribed_reset_driver_input']};input_components={union.find(n) for n in prescribed};rail_components={union.find(n) for n in RAILS}
    def outputs(cell):
        if cell['master'] not in directions:raise ValueError('missing physical pin directions')
        result={}
        for port,direction in directions[cell['master']].items():
            if direction!='OUTPUT':continue
            local=aliases[cell['master']].find(port)
            if local not in cell['nodes']:raise ValueError('output pin lacks physical primitive binding')
            result[port]=cell['nodes'][local]
        return result
    selected=set(b['selected_primitives']);excluded=[];kept=[]
    for record in l['records']:
        key,cell=by_primitives[frozenset(record['complete_primitives'])];pins=outputs(cell);blocked={port:node for port,node in pins.items() if union.find(node) in input_components}
        if blocked:
            if set(cell['primitives'])&selected:raise ValueError('original circuit drives a declared prescribed input')
            excluded.append(dict(cell_key=key,master=cell['master'],primitives=cell['primitives'],output_pins_on_prescribed_input_components=blocked));continue
        selected.update(cell['primitives']);kept.append(record)
    if selected==set(b['selected_primitives']):raise ValueError('load expansion unexpectedly empty')
    output_records=[];protected_roots=set()
    for key,cell in bound.items():
        names=set(cell['primitives'])
        if not names&selected:continue
        if not names<=selected:raise ValueError('partial physical cell selected')
        for port,node in outputs(cell).items():
            root=union.find(node)
            if root in input_components:raise ValueError('selected output drives a declared input source')
            if root in rail_components:
                if '__conb_' not in cell['master']:raise ValueError('non-tie output shorted to a supply component')
                continue
            protected_roots.add(root);output_records.append(dict(cell_key=key,master=cell['master'],pin=port,node=node,component=root))
    protected={n for n in list(union.parent) if union.find(n) in protected_roots}
    private,boundary,cards,omitted=passive_cut(terms,passives,selected,prescribed,protected)
    if not set(b['private_unknown_nodes'])<=private or any(union.find(n) in protected_roots for n in boundary):raise ValueError('original private nodes lost or retained output R component prescribed')
    pins=dict(dependencies);files=[base,loads,Path(__file__).resolve(),Path(__file__).with_name('protected_passive_cut.py'),Path(__file__).with_name('plan_selected_detector_passive_cut.py'),Path(__file__).with_name('resolve_prototype_loaded_halo_interfaces.py'),Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py')];pins.update({str(p):sha(p) for p in files});verify(pins)
    save(output,dict(input_sha256=pins,selected_primitives=sorted(selected),private_unknown_nodes=sorted(private),required_non_supply_boundary_voltage_nodes=sorted(boundary),retained_passive_cards=[passives[i][0] for i in sorted(cards)],omitted_primitives_touching_private_nodes=omitted,prescribed_control_driver_input_nodes=b['prescribed_control_driver_input_nodes'],prescribed_reset_driver_input=b['prescribed_reset_driver_input'],fixed_supply_nodes=b['fixed_supply_nodes'],added_load_cells=kept,excluded_load_cells_driving_prescribed_inputs=excluded,protected_retained_outputs=output_records,protected_output_wire_nodes=sorted(protected),retained_output_R_components_unclamped=True,capacitor_only_unknowns_preserved=True,upstream_interface_drivers_not_silently_retained=True,stateful_boundary_histories_qualified=False,physical_models_qualified=False,release_ready=False))
    print(json.dumps(dict(selected_primitives=len(selected),retained_passives=len(cards),kept_load_cells=len(kept),excluded_load_cells=excluded,protected_output_pins=len(output_records),private_unknowns=len(private),boundary_nodes=len(boundary))))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['base','loads','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();os.sched_setaffinity(0,{29});run(*(getattr(a,n).resolve() for n in ['base','loads','output']))
