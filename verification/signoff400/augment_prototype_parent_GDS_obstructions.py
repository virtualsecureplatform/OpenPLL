"""Add missing macro GDS routing/cut geometry as parent routing obstructions."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from common_v3 import ROOT,save,sha,verify
from extend_prototype_macro_obstructions import rectangles
from resources import lease
from compiled_charge import execute
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import OPENROAD


def run(frame,power,output):
    import pya
    fr,pr=[p/'assessment.json' for p in (frame,power)]
    f,p=[json.loads(path.read_text()) for path in (fr,pr)]
    for record in (f,p):verify(record['input_sha256']);verify(record['artifacts'])
    if (not f['assembly_frame_pass'] or not p['main_rail_database_connectivity_pass']
            or not p['control_buffer_composition_proved']
            or f['candidate_source_sha256']!=p['candidate_source_sha256']):
        raise ValueError('matched checked buffered parent and frame required')
    mapping=ROOT/'build/timing450/pdk/sky130A/libs.tech/klayout/tech/sky130A.map'
    layers={}
    for line in mapping.read_text().splitlines():
        fields=line.split()
        if len(fields)==4 and re.fullmatch(r'(li1|met[1-5]|mcon|via[234]?)',fields[0]) and 'VIA' in fields[1].split(','):
            pair=tuple(map(int,fields[2:]))
            if fields[0] in layers and layers[fields[0]]!=pair:raise ValueError('ambiguous layer map')
            layers[fields[0]]=pair
    if len(layers)!=11:raise ValueError('complete routing/cut mapping required')
    paths=[fr,pr,power/'power.odb',mapping,Path(__file__).resolve(),
           Path(__file__).with_name('extend_prototype_macro_obstructions.py'),Path(OPENROAD)]
    additions=[];coverage=[]
    def region(boxes):
        result=pya.Region()
        for box in boxes:result.insert(pya.Box(*box))
        return result
    for role,view in sorted(f['macro_sources'].items()):
        lef,gds=[Path(view[k]) for k in ('lef','gds')];paths.extend((lef,gds))
        pins,obs=rectangles(lef.read_text());layout=pya.Layout();layout.read(str(gds))
        cell=layout.cell(view['master'])
        if layout.dbu!=.001 or cell is None:raise ValueError('exact physical master and grid required')
        x,y,_,_=f['macro_bboxes_dbu'][role]
        for layer,pair in sorted(layers.items()):
            index=layout.find_layer(*pair)
            actual=pya.Region(cell.begin_shapes_rec(index)) if index is not None else pya.Region()
            missing=(actual-region(pins.get(layer,[]))-region(obs.get(layer,[]))).merged()
            pieces=list(missing.decompose_trapezoids_to_region().each())
            if any(poly.num_points()!=4 or poly.area()!=poly.bbox().area() for poly in pieces):
                raise ValueError('nonrectangular missing routing geometry requires explicit support')
            for poly in pieces:
                b=poly.bbox();additions.append(dict(macro=role,layer=layer,
                    bbox_nm=[b.left+x,b.bottom+y,b.right+x,b.top+y]))
            coverage.append(dict(macro=role,layer=layer,added_rectangles=len(pieces),
                                 added_area_um2=missing.area()*1e-6))
    if not additions:raise ValueError('no missing geometry to repair')
    output.mkdir(parents=True,exist_ok=False)
    for name in ('composition.json','placement_plan.json','diode_placement_plan.json'):
        if (power/name).exists():
            paths.append(power/name);(output/name).write_bytes((power/name).read_bytes())
    detail=output/'obstructions.json';save(detail,dict(additions=additions,coverage=coverage))
    tcl=[f'read_db {{{power/"power.odb"}}}','set_thread_count 4',
         'set block [ord::get_db_block]','set tech [ord::get_db_tech]']
    for role,box in sorted(f['macro_bboxes_dbu'].items()):
        tcl.extend((f'set inst [$block findInst {role}]',
                    f'if {{[$inst getOrigin] ne {{{box[0]} {box[1]}}}}} {{error "macro origin differs"}}',
                    'if {[$inst getOrient] ne {R0}} {error "macro orientation differs"}'))
    for row in additions:
        coordinates=' '.join(map(str,row['bbox_nm']))
        tcl.append(f'odb::dbObstruction_create $block [$tech findLayer {row["layer"]}] {coordinates}')
    tcl.extend((f'write_db {{{output/"power.odb"}}}',f'write_def {{{output/"power.def"}}}',
                f'write_verilog -include_pwr_gnd {{{output/"powered.v"}}}'))
    for rail in ('VPWR','VGND'):
        tcl.append(f'check_power_grid -net {rail} -error_file {{{output/(rail+"_errors.rpt")}}}')
    script=output/'augment.tcl';script.write_text('\n'.join(tcl)+'\n');paths.extend((detail,script))
    inputs=dict(p['input_sha256']);inputs.update({str(path):sha(path) for path in paths})
    save(output/'input_manifest.json',dict(input_sha256=inputs))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1')
    with lease(4,8,deadline):execute([OPENROAD,'-no_init','-exit',script],output/'augment.log',deadline,8)
    log=(output/'augment.log').read_text()
    if '[ERROR' in log or not all(f'All shapes on net {rail} are connected.' in log for rail in ('VPWR','VGND')):
        raise ValueError('obstruction annotation or main-rail check failed')
    verify(inputs);result=dict(p)
    result.update(input_sha256=inputs,artifacts={str(path):sha(path) for path in output.iterdir() if path.is_file()},
        added_macro_GDS_obstruction_rectangles=len(additions),
        missing_routing_and_cut_geometry_covered=True,macro_GDS_and_abstract_pin_shapes_unchanged=True,
        original_parent_connections_and_placements_retained=True,new_native_DRC_LVS_required=True,
        antenna_qualified=False,release_ready=False)
    save(output/'assessment.json',result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('frame','power','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(args.frame.resolve(),args.power.resolve(),args.output.resolve())
