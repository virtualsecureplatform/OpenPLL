"""Prepare exact filler slots for a same-route, buffer-only electrical repair."""
import argparse
import json
from pathlib import Path
import re
from common_v3 import save,sha,verify
from prototype_filler_buffer_slots import allocate,render


def run(plan,inventory,namespace,output,max_distance_um=20):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',namespace):raise ValueError('safe namespace required')
    if not 1<=max_distance_um<=100:raise ValueError('buffer search bound outside reviewed macro region')
    p=json.loads(plan.read_text());receipt=inventory/'assessment.json';r=json.loads(receipt.read_text())
    verify(p['input_sha256']);verify(r['input_sha256']);verify(r['artifacts'])
    if p['targets'] or p['branches'] or not p.get('all_existing_logic_fixed'):
        raise ValueError('fixed-logic buffer-only proposal required')
    native_receipts=[Path(n) for n in r['input_sha256'] if n.endswith('/assessment.json')]
    if len(native_receipts)!=1:raise ValueError('unique native inventory lineage required')
    native=json.loads(native_receipts[0].read_text());verify(native['input_sha256']);verify(native['artifacts'])
    databases=[h for n,h in native['input_sha256'].items() if n.endswith('/route.odb')]
    if databases!=[p['route_sha256']]:raise ValueError('slot inventory belongs to another route')
    cells=json.loads((inventory/'instances.json').read_text());masters=json.loads((inventory/'masters.json').read_text())
    protected=set(p['protected_first_stage_cells']);requests=[]
    def request(name,master,anchor):
        size=masters[master.removeprefix('sky130_fd_sc_hs__')]
        requests.append(dict(name=name,master=master,anchor=anchor,width=size['width'],height=size['height']))
    for index,row in enumerate(p.get('source_buffers',[])):
        d=row['driver'];cell=cells[d['cell']]
        if d['cell'] in protected or cell['master']!=d['master'] or row['buffer_master']!='sky130_fd_sc_hs__clkbuf_8':
            raise ValueError('source driver or characterized buffer differs')
        request(f'{namespace}_source_{index}',row['buffer_master'],cell['location'])
    for index,row in enumerate(p.get('short_data_targets',[])):
        cell=cells[row['capture_cell']]
        if row['capture_cell'] in protected or cell['master']!=row['capture_master'] or row['capture_pin']!='D' or row['buffers'] not in (1,2):
            raise ValueError('bounded ordinary D-pin repair required')
        for stage in range(row['buffers']):
            request(f'{namespace}_hold_{index}_{stage}','sky130_fd_sc_hs__clkbuf_2',cell['location'])
    if not requests:raise ValueError('nonempty repair required')
    allocations=allocate(cells,requests,site=masters['fill_1']['width'],max_distance=round(max_distance_um*1000))
    setup,placements=render(allocations)
    inputs={str(f):sha(f) for f in (plan,receipt,*native_receipts,inventory/'instances.json',inventory/'masters.json',
            Path(__file__).resolve(),Path(__file__).with_name('prototype_filler_buffer_slots.py'))}
    verify(inputs);output.mkdir(parents=True,exist_ok=False)
    save(output/'allocations.json',allocations)
    (output/'allocation.tcl').write_text(setup);(output/'placements.tcl').write_text(placements)
    save(output/'assessment.json',dict(input_sha256=inputs,
         artifacts={str(output/n):sha(output/n) for n in ('allocations.json','allocation.tcl','placements.tcl')},
         namespace=namespace,route_sha256=p['route_sha256'],buffer_slots=len(allocations),
         max_buffer_distance_um=max(a['distance_dbu'] for a in allocations)/1000,
         max_allowed_buffer_distance_um=max_distance_um,
         existing_logic_movement_permitted=False,exact_donor_footprint_tiling=True,
         native_placement_validation_required=True,release_ready=False))
    print(json.dumps(dict(buffer_slots=len(allocations),max_distance_um=max(a['distance_dbu'] for a in allocations)/1000)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','inventory','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--namespace',required=True)
    parser.add_argument('--max-distance-um',type=float,default=20);a=parser.parse_args()
    run(a.plan.resolve(),a.inventory.resolve(),a.namespace,a.output.resolve(),a.max_distance_um)
