"""Make a diagnostic analog extraction view with native poly/metal fill conductors.

The manufacturing GDS is untouched. Entire floating fill polygons in the
selected neighborhood are retained, without truncation. FOM and exterior
active-circuit coverage remain explicit open model obligations.
"""
import argparse
import json
from pathlib import Path
from common_v3 import save,sha,verify


def run(layout,frame,role,margin_um,output):
    import pya
    if role not in ('oscillator','detector') or margin_um<0:raise ValueError('supported analog neighborhood required')
    lr,fr=[p/'assessment.json' for p in (layout,frame)]
    l,f=[json.loads(p.read_text()) for p in (lr,fr)]
    for record in (l,f):verify(record['input_sha256']);verify(record['artifacts'])
    if not l['assembled_drc_pass'] or l['input_sha256'].get(str(fr))!=sha(fr):raise ValueError('same checked parent frame required')
    gds=layout/'assembly.gds';view=f['macro_sources'][role];name=view['master']
    before=pya.Layout();before.read(str(gds))
    if before.dbu!=.001:raise ValueError('native nanometer geometry required')
    macro=before.cell(name);parent=before.cell('IntegerPLL_400MHz_PrototypeTop')
    if macro is None or parent is None:raise ValueError('exact analog and parent masters required')
    x,y,x2,y2=f['macro_bboxes_dbu'][role]
    margin=int(round(margin_um*1000));window=pya.Region(pya.Box(x-margin,y-margin,x2+margin,y2+margin))
    def region(stream,cell,key):
        index=stream.find_layer(*key)
        return pya.Region(cell.begin_shapes_rec(index)).merged() if index is not None else pya.Region()
    original={(before.get_info(i).layer,before.get_info(i).datatype):region(before,macro,(before.get_info(i).layer,before.get_info(i).datatype)) for i in before.layer_indices()}
    if any(not original.get((n,99),pya.Region()).is_empty() for n in range(65,73)):
        raise ValueError('analog master already contains fill; separate provenance required')
    after=pya.Layout();after.dbu=before.dbu;target=after.create_cell(name);target.copy_tree(macro)
    additions={};details=[]
    for number in range(65,73):
        fill=region(before,parent,(number,99)).interacting(window)
        local=fill.transformed(pya.Trans(-x,-y));purpose=99 if number==65 else 20
        # Native PDK has distinct fill types. This view maps only the materials
        # covered by the existing floating-conductor extraction controls.
        if purpose==20:
            existing=original.get((number,20),pya.Region())
            if not (local & existing.sized(1)).is_empty():raise ValueError('fill touches original conductor')
        if number==66:
            for key in ((65,20),(65,44),(66,44),(66,13),(66,15)):
                if not (local & original.get(key,pya.Region()).sized(1)).is_empty():
                    raise ValueError('mapped poly fill adds gate/contact/resistor interaction')
        target.shapes(after.layer(number,purpose)).insert(local)
        additions[number,purpose]=local
        details.append(dict(layer=number,source_purpose=99,extraction_purpose=purpose,
            polygons=local.count(),area_um2=local.area()*1e-6,entire_polygons_preserved=True))
    keys=set(original)|set(additions)
    for key in keys:
        expected=original.get(key,pya.Region())|additions.get(key,pya.Region())
        if not (region(after,target,key)^expected).is_empty():raise ValueError('unreviewed mask change')
    gate_before=original.get((66,20),pya.Region())&original.get((65,20),pya.Region())
    gate_after=region(after,target,(66,20))&region(after,target,(65,20))
    if not (gate_before^gate_after).is_empty():raise ValueError('analog MOS gate geometry changed')
    inputs={str(p):sha(p) for p in (lr,fr,gds,Path(__file__).resolve())};verify(inputs)
    output.mkdir(parents=True,exist_ok=False);target_file=output/'capacitance_view.gds';after.write(str(target_file))
    save(output/'fill_geometry.json',details)
    save(output/'assessment.json',dict(input_sha256=inputs,
        artifacts={str(p):sha(p) for p in (target_file,output/'fill_geometry.json')},
        top=name,role=role,margin_um=margin_um,source_manufacturing_GDS=str(gds),
        source_manufacturing_GDS_sha256=sha(gds),extraction_only_view=True,
        original_analog_drawing_geometry_preserved=True,original_MOS_gate_regions_preserved=True,
        source_manufacturing_GDS_unchanged=True,selected_floating_fill_polygons_not_truncated=True,
        poly_and_LI_M1_M5_fill_mapped_to_conductor_purpose=True,
        FOM_fill_electrical_coverage_complete=False,exterior_active_circuit_loading_complete=False,
        neighborhood_convergence_verified=False,physical_model_qualified=False,release_ready=False))
    print(json.dumps(dict(top=name,margin_um=margin_um,mapped_fill_polygons=sum(r['polygons'] for r in details if r['layer']!=65))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('layout','frame','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--role',choices=('oscillator','detector'),required=True)
    parser.add_argument('--margin-um',type=float,required=True)
    args=parser.parse_args();run(args.layout.resolve(),args.frame.resolve(),args.role,args.margin_um,args.output.resolve())
