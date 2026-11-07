"""Add keeper GDS conductors/cuts to the protected parent routing database."""
import argparse,json,re,time
from pathlib import Path
import klayout.db as k
from common_v3 import ROOT,save,sha,verify
from extend_prototype_macro_obstructions import rectangles
from resources import lease
from compiled_charge import execute

OPENROAD='/nix/store/qqz49dx8dpx4q9i5wriif091n7iaa0ld-openroad-2026-02-17/bin/openroad'


def run(frame,power,physical,interface_receipt,assembly,output):
    output.mkdir(parents=True,exist_ok=False)
    receipts=[p/'assessment.json'for p in [frame,power,physical,assembly]]
    f,p,a,s=[json.loads(x.read_text())for x in receipts]
    for r in [f,p,s]:verify(r['input_sha256']);verify(r['artifacts'])
    verify(a['input_sha256']);verify(a['source_input_sha256'])
    interface=json.loads(interface_receipt.read_text());verify(interface['input_sha256']);verify(interface['artifacts'])
    if not a['candidate_physical_checks_pass']or not p['main_rail_database_connectivity_pass']or not p['control_buffer_composition_proved']:raise ValueError('audited keeper and proved buffered parent required')
    if not interface['all_signal_pin_port_geometry_unchanged']or not interface['original_power_pin_ports_preserved']or not interface['same_size']or not interface['same_origin']:raise ValueError('original macro contacts must remain intact')
    if not f['assembly_frame_pass']or f['candidate_source_sha256']!=p['candidate_source_sha256']:raise ValueError('parent frame/source mismatch')
    view=f['macro_sources']['oscillator'];lef=Path(view['lef']);gds=assembly/'assembly.gds'
    # Export only the namespace-safe keeper DCO subtree for the new parent stream.
    l=k.Layout();l.read(str(gds));cell=l.cell(view['master'])
    if l.dbu!=0.001 or cell is None:raise ValueError('native DCO frame required')
    options=k.SaveLayoutOptions();options.select_cell(cell.cell_index());macro_gds=output/'keeper_dco.gds';l.write(str(macro_gds),options)
    pins,obs=rectangles(lef.read_text());mapping=ROOT/'build/timing450/pdk/sky130A/libs.tech/klayout/tech/sky130A.map'
    layers={}
    for line in mapping.read_text().splitlines():
        fields=line.split()
        if len(fields)==4 and re.fullmatch(r'(li1|met[1-5]|mcon|via[234]?)',fields[0])and 'VIA'in fields[1].split(','):layers[fields[0]]=tuple(map(int,fields[2:]))
    if len(layers)!=11:raise ValueError('complete conductor/cut layer map required')
    def region(boxes):
        r=k.Region()
        for box in boxes:r.insert(k.Box(*box))
        return r
    x,y,_,_=f['macro_bboxes_dbu']['oscillator'];additions=[];coverage=[]
    for layer,pair in sorted(layers.items()):
        idx=l.find_layer(*pair);actual=k.Region(cell.begin_shapes_rec(idx))if idx is not None else k.Region()
        missing=(actual-region(pins.get(layer,[]))-region(obs.get(layer,[]))).merged()
        pieces=list(missing.decompose_trapezoids_to_region().each())
        if any(poly.num_points()!=4 or poly.area()!=poly.bbox().area()for poly in pieces):raise ValueError('nonrectangular obstruction')
        boxes=[]
        for poly in pieces:
            b=poly.bbox();boxes.append((b.left,b.bottom,b.right,b.top));additions.append(dict(layer=layer,bbox_nm=[b.left+x,b.bottom+y,b.right+x,b.top+y]))
        if not (actual-region(pins.get(layer,[]))-region(obs.get(layer,[]))-region(boxes)).is_empty():raise ValueError('incomplete GDS coverage')
        coverage.append(dict(layer=layer,added_rectangles=len(boxes),added_area_um2=missing.area()*1e-6))
    if not additions:raise ValueError('expected new physical obstructions')
    for name in ['composition.json','placement_plan.json','diode_placement_plan.json']:
        if (power/name).exists():(output/name).write_bytes((power/name).read_bytes())
    detail=output/'obstructions.json';save(detail,dict(additions=additions,coverage=coverage))
    lines=[f'read_db {{{power/"power.odb"}}}','set_thread_count 4','set block [ord::get_db_block]','set tech [ord::get_db_tech]',f'set inst [$block findInst oscillator]',f'if {{[$inst getOrigin] ne {{{x} {y}}}}} {{error "DCO origin differs"}}','if {[$inst getOrient] ne {R0}} {error "DCO orientation differs"}']
    for row in additions:lines.append(f'odb::dbObstruction_create $block [$tech findLayer {row["layer"]}] '+ ' '.join(map(str,row['bbox_nm'])))
    lines.extend([f'write_db {{{output/"power.odb"}}}',f'write_def {{{output/"power.def"}}}',f'write_verilog -include_pwr_gnd {{{output/"powered.v"}}}'])
    for rail in ['VPWR','VGND']:lines.append(f'check_power_grid -net {rail} -error_file {{{output/(rail+"_errors.rpt")}}}')
    script=output/'augment.tcl';script.write_text('\n'.join(lines)+'\n')
    files=[Path(__file__).resolve(),Path(OPENROAD),interface_receipt,lef,gds,macro_gds,mapping,power/'power.odb',detail,script,*receipts]
    inputs={**p['input_sha256'],**{str(x):sha(x)for x in files}};save(output/'inputs.json',dict(input_sha256=inputs))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    with lease(4,8,deadline):execute([OPENROAD,'-no_init','-exit',script],output/'augment.log',deadline,8)
    log=(output/'augment.log').read_text()
    if '[ERROR'in log or not all(f'All shapes on net {rail} are connected.'in log for rail in ['VPWR','VGND']):raise ValueError('parent obstruction or rail check failed')
    verify(inputs);result=dict(p)
    result.update(input_sha256=inputs,artifacts={str(x):sha(x)for x in output.iterdir()if x.is_file()},added_keeper_obstructions=len(additions),keeper_routing_geometry_covered=True,
        analog_macro_GDS_unchanged=False,macro_interiors_unchanged=False,macro_GDS_and_abstract_pin_shapes_unchanged=False,placement_and_pg_only=False,
        original_parent_connections_and_placements_retained=True,original_native_abstract_contacts_retained=True,new_macro_power_accesses_not_required_for_existing_contacts=True,
        candidate_keeper_GDS=str(macro_gds),candidate_keeper_GDS_sha256=sha(macro_gds),keeper_private_cell_renames=s['private_cell_renames'],parent_reroute_required=True,
        parent_timing_and_control_response_qualified=False,antenna_qualified=False,release_ready=False)
    save(output/'assessment.json',result)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['frame','power','physical','assembly','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--interface-receipt',type=Path,required=True);a=p.parse_args();run(a.frame.resolve(),a.power.resolve(),a.physical.resolve(),a.interface_receipt.resolve(),a.assembly.resolve(),a.output.resolve())
