"""Keep full parent context while mapping selected analog-neighborhood fill.

The manufacturing GDS is untouched. Entire floating fill polygons in the
selected physical-domain neighborhood are retained, without truncation. FOM and exterior
active-circuit coverage remain explicit open model obligations.
"""
import argparse
import json
from pathlib import Path
from common_v3 import save,sha,verify


def run(layout,frame,role,margin_um,output,reference,domain,placement_binding,wire_geometry):
    import pya
    if role not in ('oscillator','detector') or margin_um<0:raise ValueError('supported analog neighborhood required')
    lr,fr=[p/'assessment.json' for p in (layout,frame)]
    l,f=[json.loads(p.read_text()) for p in (lr,fr)]
    for record in (l,f):verify(record['input_sha256']);verify(record['artifacts'])
    if not l['assembled_drc_pass'] or l['input_sha256'].get(str(fr))!=sha(fr):raise ValueError('same checked parent frame required')
    gds=layout/'assembly.gds';view=f['macro_sources'][role];name='IntegerPLL_400MHz_PrototypeTop';analog_name=view['master']
    before=pya.Layout();before.read(str(gds))
    if before.dbu!=.001:raise ValueError('native nanometer geometry required')
    macro=before.cell(analog_name);parent=before.cell('IntegerPLL_400MHz_PrototypeTop')
    if macro is None or parent is None:raise ValueError('exact analog and parent masters required')
    x,y,x2,y2=f['macro_bboxes_dbu'][role]
    margin=int(round(margin_um*1000));window=pya.Region(pya.Box(x-margin,y-margin,x2+margin,y2+margin))
    from fractions import Fraction as F
    from prototype_physical_domain_windows import resolve_windows
    extra_receipts=[p/'assessment.json' for p in (reference,domain,placement_binding)]
    rr,dr,br=[json.loads(p.read_text()) for p in extra_receipts]
    for record in (rr,dr,br):verify(record['input_sha256']);verify(record['artifacts'])
    if dr['input_sha256'].get(str(extra_receipts[0]))!=sha(extra_receipts[0]):raise ValueError('domain and physical reference differ')
    if rr['assembled_candidate_gds_sha256']!={str(gds):sha(gds)}:raise ValueError('physical reference manufacturing GDS differs')
    if not br['all_placed_instances_matched'] or not br['exact_primitive_dimension_grid_verified']:raise ValueError('controlled native placement grid required')
    join_path=placement_binding/'join.json';join=json.loads(join_path.read_text())
    if br['artifacts'].get(str(join_path))!=sha(join_path):raise ValueError('placement grid receipt differs')
    if br['input_sha256'].get(str(lr))!=sha(lr):raise ValueError('placement proof manufacturing layout differs')
    grid=F(join['magic_grid_um'])*1000
    if grid.denominator!=1:raise ValueError('native grid is not integral nanometers')
    node_path=reference/'nodes.json';contract_path=domain/'interface_contract.json'
    metadata=json.loads(node_path.read_text());contract=json.loads(contract_path.read_text())
    if rr['artifacts'].get(str(node_path))!=sha(node_path) or dr['artifacts'].get(str(contract_path))!=sha(contract_path):raise ValueError('physical selection artifacts differ')
    selected_window,selected_boxes=resolve_windows(before,parent,metadata,contract['selected_primitives'],int(grid),margin,pya)
    window=(window|selected_window).merged()
    from bound_prototype_wire_region_v2 import region_boxes
    wire_receipt=wire_geometry/'assessment.json';wr=json.loads(wire_receipt.read_text())
    verify(wr['input_sha256']);verify(wr['artifacts'])
    if wr['input_sha256'].get(str(fr))!=sha(fr):raise ValueError('wire geometry belongs to another parent frame')
    wire_file=wire_geometry/'wire_regions.json'
    if wr['artifacts'].get(str(wire_file))!=sha(wire_file):raise ValueError('native wire regions changed')
    routes=json.loads(wire_file.read_text())
    if {r['role'] for r in routes}!={'parent','digital'} or len(routes)!=2:raise ValueError('both routed PLLOUT geometry sources required')
    authorities=[]
    for path in wr['input_sha256']:
        if path.endswith('/assessment.json'):authorities.append((Path(path),json.loads(Path(path).read_text())))
    selected_wire_boxes=[];wire_window=pya.Region();wire_authority_receipts=[]
    for route in routes:
        if route['net']!='PLLOUT':raise ValueError('only explicitly reviewed PLLOUT routes supported')
        db=Path(route['database']);matches=[r for _,r in authorities if r.get('input_sha256',{}).get(str(db))==sha(db) or r.get('artifacts',{}).get(str(db))==sha(db)]
        if len(matches)!=1:raise ValueError('wire route database lacks one pinned native authority')
        authority=matches[0]
        if route['role']=='parent':
            if authority['input_sha256'].get(str(lr))!=sha(lr):raise ValueError('parent wire authority uses another checked layout')
        else:
            digital_gds=Path(f['macro_sources']['digital']['gds'])
            # GDS generation is certified by the legacy signoff report, whose
            # hashes are under sha256 rather than the route producer artifacts.
            signoff_receipt=digital_gds.parent/'assessment.json'
            signoff=json.loads(signoff_receipt.read_text());verify(signoff['sha256'])
            if signoff['sha256'].get(str(db))!=sha(db) or signoff['sha256'].get(str(digital_gds))!=sha(digital_gds):raise ValueError('paired digital ODB/GDS signoff identity differs')
            if f['input_sha256'].get(str(digital_gds))!=sha(digital_gds):raise ValueError('assembled digital GDS differs from frame')
            wire_authority_receipts.append(signoff_receipt)
        boxes=region_boxes(route['decoded_route_geometry'],route['global_offset_nm'],margin)
        for box in boxes:wire_window.insert(pya.Box(*box))
        selected_wire_boxes.append(dict(role=route['role'],net=route['net'],boxes_nm=boxes))
    window=(window|wire_window).merged()

    def region(stream,cell,key):
        index=stream.find_layer(*key)
        return pya.Region(cell.begin_shapes_rec(index)).merged() if index is not None else pya.Region()
    original={(before.get_info(i).layer,before.get_info(i).datatype):region(before,parent,(before.get_info(i).layer,before.get_info(i).datatype)) for i in before.layer_indices()}
    after=pya.Layout();after.dbu=before.dbu;target=after.create_cell(name);target.copy_tree(parent)
    additions={};removed={};details=[]
    for number in range(65,73):
        fill=region(before,parent,(number,99)).interacting(window)
        local=fill;purpose=99 if number==65 else 20
        # Native PDK has distinct fill types. This view maps only the materials
        # covered by the existing floating-conductor extraction controls.
        if purpose==20:
            existing=original.get((number,20),pya.Region())
            if not (local & existing.sized(1)).is_empty():raise ValueError('fill touches original conductor')
        if number==66:
            for key in ((65,20),(65,44),(66,44),(66,13),(66,15)):
                if not (local & original.get(key,pya.Region()).sized(1)).is_empty():
                    raise ValueError('mapped poly fill adds gate/contact/resistor interaction')
        if purpose==20:
            # The stock paint control shows retained 99 can erase drawing 20.
            # Reconstruct only this fill layer, leaving selected polygons solely
            # on conductor purpose and all unselected polygons on purpose 99.
            index=after.find_layer(number,99)
            if index is not None:
                for cell in after.each_cell():
                    shapes=cell.shapes(index)
                    if any(shape.is_text() for shape in shapes.each()):
                        raise ValueError('fill-purpose labels require explicit preservation')
                    shapes.clear()
            remaining=original.get((number,99),pya.Region())-local
            target.shapes(after.layer(number,99)).insert(remaining)
            removed[number,99]=local
            target.shapes(after.layer(number,purpose)).insert(local)
            additions[number,purpose]=local
        details.append(dict(layer=number,source_purpose=99,extraction_purpose=purpose,
            polygons=local.count(),area_um2=local.area()*1e-6,entire_polygons_preserved=True))
    keys=set(original)|set(additions)|set(removed)
    for key in keys:
        expected=(original.get(key,pya.Region())-removed.get(key,pya.Region()))|additions.get(key,pya.Region())
        if not (region(after,target,key)^expected).is_empty():raise ValueError('unreviewed mask change')
    gate_before=original.get((66,20),pya.Region())&original.get((65,20),pya.Region())
    gate_after=region(after,target,(66,20))&region(after,target,(65,20))
    if not (gate_before^gate_after).is_empty():raise ValueError('parent MOS gate geometry changed')
    inputs={str(p):sha(p) for p in (lr,fr,gds,Path(__file__).resolve(),*extra_receipts,join_path,node_path,contract_path,Path(__file__).with_name('prototype_physical_domain_windows.py'),wire_receipt,wire_file,Path(__file__).with_name('bound_prototype_wire_region_v2.py'),*wire_authority_receipts)};verify(inputs)
    output.mkdir(parents=True,exist_ok=False);target_file=output/'capacitance_view.gds';after.write(str(target_file))
    save(output/'fill_geometry.json',details)
    save(output/'selected_physical_cells.json',selected_boxes)
    save(output/'selected_wire_corridors.json',selected_wire_boxes)
    save(output/'assessment.json',dict(input_sha256=inputs,
        artifacts={str(p):sha(p) for p in (target_file,output/'fill_geometry.json',output/'selected_physical_cells.json',output/'selected_wire_corridors.json')},
        top=name,analog_target=analog_name,role=role,margin_um=margin_um,
        actual_loaded_domain_cells_included=True,routed_parent_and_digital_PLLOUT_corridors_included=True,
        conservative_native_wire_enclosures_used=True,wire_corridor_rectangles=sum(len(r["boxes_nm"]) for r in selected_wire_boxes),selected_physical_cells=len(selected_boxes),
        selected_physical_cell_placements_verified_against_GDS=True,source_manufacturing_GDS=str(gds),
        source_manufacturing_GDS_sha256=sha(gds),extraction_only_view=True,
        original_parent_drawing_geometry_preserved=True,
        original_parent_hierarchy_copied=True,complete_parent_context_preserved=True,original_MOS_gate_regions_preserved=True,
        source_manufacturing_GDS_unchanged=True,selected_floating_fill_polygons_not_truncated=True,
        poly_and_LI_M1_M5_fill_mapped_to_conductor_purpose=True,
        selected_fill_purpose_removed_after_conductor_mapping=True,
        unselected_fill_purpose_geometry_preserved=True,
        FOM_fill_electrical_coverage_complete=False,exterior_active_geometry_preserved=True,
        exterior_fill_outside_selected_neighborhood_electrically_mapped=False,
        exterior_active_circuit_loading_complete=False,
        neighborhood_convergence_verified=False,physical_model_qualified=False,release_ready=False))
    print(json.dumps(dict(top=name,margin_um=margin_um,mapped_fill_polygons=sum(r['polygons'] for r in details if r['layer']!=65))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('layout','frame','output','reference','domain','placement-binding','wire-geometry'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--role',choices=('oscillator','detector'),required=True)
    parser.add_argument('--margin-um',type=float,required=True)
    args=parser.parse_args();run(args.layout.resolve(),args.frame.resolve(),args.role,args.margin_um,args.output.resolve(),args.reference.resolve(),args.domain.resolve(),args.placement_binding.resolve(),args.wire_geometry.resolve())
