import pya,json
layout=pya.Layout();layout.read('/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_keeper_contact_corrected_C_1573/flat.gds');top=layout.top_cell();factor=0.005/layout.dbu
x,y=[round(v*factor) for v in (39000,11840)]
points={'NE':pya.Box(x,y,x+1,y+1),'NW':pya.Box(x-1,y,x,y+1),'SE':pya.Box(x,y-1,x+1,y),'SW':pya.Box(x-1,y-1,x,y)}
clip=pya.Region()
for box in [(36000,8840,44000,15160),(6383,48680,10383,52680)]:clip.insert(pya.Box(*(round(v*factor) for v in box)))
dest=pya.Layout();dest.dbu=layout.dbu;cell=dest.create_cell('GroundDriverRegions');layers={};point_layers={}
for layer in layout.layer_indices():
 info=layout.get_info(layer);region=pya.Region(top.begin_shapes_rec(layer));local=region & clip
 if not local.is_empty():
  cell.shapes(dest.layer(info)).insert(local);layers[str(info)]=local.count()
 if info.layer in [68,69,70,71,72]:
  hits={name:(region & pya.Region(box)).area() for name,box in points.items()}
  if any(hits.values()):point_layers[str(info)]={'quadrant_areas_dbu2':hits,'nearby_polygon_boxes':[str(p.bbox()) for p in local.each()][:20]}
dest.write('/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_ground_driver_geometry_1722/regions.gds')
open('/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_ground_driver_geometry_1722/geometry.json','w').write(json.dumps(dict(dbu=layout.dbu,Magic_grid_um=0.005,point_Magic=[39000,11840],point_dbu=[x,y],point_layers=point_layers,cropped_layer_counts=layers),indent=2))
