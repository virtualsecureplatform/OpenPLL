import pya,json
src=pya.Layout();src.read('/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_keeper_contact_corrected_C_1573/flat.gds');top=src.top_cell()
dst=pya.Layout();dst.dbu=src.dbu;cell=dst.create_cell("RC_Area_Crop")
# Magic internal grid=0.005um; preserve original physical coordinates.
factor=0.005/src.dbu
boxes=[pya.Box(*(round(x*factor) for x in coords)) for coords in [[11000,35600,13500,38100],[97400,80000,100700,83200]]]
clip=pya.Region()
for box in boxes:clip.insert(box)
counts={}
for layer in src.layer_indices():
    region=pya.Region(top.begin_shapes_rec(layer)) & clip
    if region.is_empty():continue
    target=dst.layer(src.get_info(layer));cell.shapes(target).insert(region)
    counts[str(src.get_info(layer))]=region.count()
dst.write('/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_zero_junction_crop_1660/crop.gds')
open('/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_zero_junction_crop_1660/crop_metadata.json','w').write(json.dumps(dict(dbu=src.dbu,clip_boxes_dbu=[str(box) for box in boxes],layers=counts),indent=2))
