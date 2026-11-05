"""Bind whole-node junction geometry to exact final R tiles and owned boundaries."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import time
from common import save,sha
from resources import lease


def boundary(rectangles):
    lines=defaultdict(lambda:defaultdict(list))
    for serial,box in rectangles:
        x,y,u,v=box
        if x>=u or y>=v:
            raise ValueError('positive junction support rectangles required')
        for axis,coord,lo,hi,normal in ((0,x,y,v,-1),(0,u,y,v,1),(1,y,x,u,-1),(1,v,x,u,1)):
            lines[axis,coord][lo].append((normal,serial,1))
            lines[axis,coord][hi].append((normal,serial,-1))
    for (axis,coord),events in sorted(lines.items()):
        active={-1:set(),1:set()}
        prior=None
        for position,changes in sorted(events.items()):
            if prior is not None and position>prior:
                if any(len(v)>1 for v in active.values()):
                    raise ValueError('overlapping same-side native tile boundary intervals')
                if bool(active[-1])!=bool(active[1]):
                    normal=-1 if active[-1] else 1
                    yield [next(iter(active[normal])),axis,coord,prior,position,normal]
            for normal,serial,delta in changes:
                if delta==1:
                    if serial in active[normal]:
                        raise ValueError('duplicate active boundary interval')
                    active[normal].add(serial)
                else:
                    if serial not in active[normal]:
                        raise ValueError('unmatched boundary interval end')
                    active[normal].remove(serial)
            prior=position
        if any(active.values()):
            raise ValueError('unclosed native junction boundary')


def controls():
    # Nonconforming shared edge: one rectangle meets two along subintervals.
    rectangles=[(1,[0,0,2,2]),(2,[2,0,3,1]),(3,[2,1,3,2])]
    actual=list(boundary(rectangles))
    assert sum(r[4]-r[3] for r in actual)==10
    assert not any(r[1]==0 and r[2]==2 for r in actual)
    assert all(r[0] in (1,2,3) for r in actual)
    # A one-unit interior hole must retain its own outward normals/perimeter.
    ring=[(1,[0,0,3,1]),(2,[0,2,3,3]),(3,[0,1,1,2]),(4,[2,1,3,2])]
    assert sum(r[4]-r[3] for r in boundary(ring))==16
    try:
        list(boundary([(1,[0,0,2,2]),(2,[0,0,2,2])]))
    except ValueError:
        pass
    else:
        raise ValueError('duplicate native junction geometry accepted')


def run(catalog,fallback,output):
    catalog,fallback,out=(p.resolve() for p in (catalog,fallback,output))
    out.mkdir(parents=True,exist_ok=False)
    receipts=[p/'assessment.json' for p in (catalog,fallback)]
    cat,original=[json.loads(p.read_text()) for p in receipts]
    cases_file=fallback/'whole_node_fallback_cases.json'
    cases=json.loads(cases_file.read_text())
    if not original['all_changed_native_parameter_devices_traced_to_whole_node_fallback']:
        raise ValueError('complete native node fallback geometry audit required')
    data=catalog/'native/tile_catalog.jsonl'
    paths=[*receipts,data,cases_file,Path(__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    with lease(2,8,deadline):
        pins={str(p):sha(p) for p in paths}
        if pins[str(data)]!=cat['artifacts'][str(data)] or pins[str(cases_file)]!=original['artifacts'][str(cases_file)]:
            raise ValueError('junction support source changed')
        controls()
        wanted={(c['original_source_and_bulk_node'],'ndiff' if '__nfet_' in c['model'] else 'pdiff'):c for c in cases}
        selected={k:[] for k in wanted}
        tiles=out/'junction_support_tiles.jsonl'
        with data.open('rb') as source,tiles.open('w') as target:
            while True:
                offset=source.tell()
                line=source.readline()
                if not line:
                    break
                if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
                    raise TimeoutError('junction support deadline')
                row=json.loads(line)
                key=(row['original_conductor'],row['raw_material'])
                if key not in wanted:
                    continue
                if row['split']!=0:
                    raise ValueError('explicit split junction support needs polygon basis')
                selected[key].append((row['tile_serial'],row['box_internal']))
                target.write(json.dumps(dict(native_group_id=row['native_group_id'],
                     original_conductor=key[0],raw_material=key[1],raw_type_id=row['raw_type_id'],
                     tile_serial=row['tile_serial'],box_internal=row['box_internal'],
                     source_catalog_byte_offset=offset,private_voltage_nodes=row['private_voltage_nodes']))+'\n')
        edges=out/'junction_support_boundary.jsonl'
        results=[]
        with edges.open('w') as target:
            for key,rectangles in selected.items():
                case=wanted[key]
                area=sum((b[2]-b[0])*(b[3]-b[1]) for _,b in rectangles)
                perim=0
                segments=0
                for edge in boundary(rectangles):
                    perim+=edge[4]-edge[3]
                    segments+=1
                    target.write(json.dumps([*key,*edge])+'\n')
                if [area,perim]!=case['native_node_area_perimeter']:
                    raise ValueError('final R support does not reproduce whole-node junction area/perimeter')
                polarity='n' if key[1]=='ndiff' else 'p'
                explicit=original['explicit_terminal_attribute_area_perimeter_by_node_and_polarity'][key[0]+':'+polarity]
                results.append(dict(original_conductor=key[0],raw_material=key[1],
                     native_resistance_class=case['matching_native_resistance_class'],
                     support_tiles=len(rectangles),exact_area_internal_squared=area,
                     exact_perimeter_internal=perim,owned_boundary_segments=segments,
                     explicit_MOS_attribute_area_perimeter=explicit,
                     node_minus_explicit_attribute_bookkeeping=[area-explicit[0],perim-explicit[1]],
                     bookkeeping_difference_is_not_a_spatial_residual_partition=True))
        if any(sha(Path(p))!=h for p,h in pins.items()):
            raise ValueError('junction support input changed')
        save(out/'assessment.json',dict(input_sha256=pins,
             artifacts={str(p):sha(p) for p in (tiles,edges)},
             native_node_junction_area_and_perimeter_exactly_supported_by_final_R_tiles=True,
             nonconforming_edge_hole_and_duplicate_controls_pass=True,results=results,
             private_node_and_catalog_offsets_retained=True,
             support_is_not_additive_to_existing_MOS_junction_geometry=True,
             explicit_MOS_and_remaining_junction_spatial_partition_qualified=False,
             nonlinear_junction_law_qualified=False,finite_R_bulk_support_binding_qualified=False,
             physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
        print(json.dumps(results))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('catalog','fallback','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args()
    run(a.catalog,a.fallback,a.output)
