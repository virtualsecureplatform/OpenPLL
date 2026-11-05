"""Bind isolated candidate SPEF to its freshly extracted cells using exact placement geometry."""
import argparse,json,os,re,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge import execute
from join_prototype_physical_instances import dimensions,join
from prototype_spef_v2 import parse
from build_prototype_DCO_rc import build

OPENROAD='/nix/store/qqz49dx8dpx4q9i5wriif091n7iaa0ld-openroad-2026-02-17/bin/openroad'


def run(candidate,extraction,output):
    receipt=candidate/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    er=extraction/'assessment.json';e=json.loads(er.read_text());verify(e['input_sha256']);verify(e['artifacts'])
    if not e['completed_native_extraction_verified_in_pinned_image']:raise ValueError('reviewed native extraction required')
    db=next(Path(p) for p in r['artifacts'] if p.endswith('.odb'));gds=next(Path(p) for p in r['artifacts'] if p.endswith('.gds'));top=gds.stem
    source_dir=Path(e['source_extraction_directory']);manifest=json.loads((source_dir/'input_manifest.json').read_text())
    if manifest['input_sha256'].get(str(gds))!=sha(gds):raise ValueError('candidate extraction GDS mismatch')
    folder=source_dir/top;source=folder/'capacitance.spice';cell='sky130_fd_sc_hd__nand2_8';cell_ext=folder/(cell+'.ext');top_ext=folder/(top+'.ext')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';output.mkdir(parents=True,exist_ok=False)
    script=output/'query.tcl';placements=output/'placements.tsv'
    script.write_text('read_db {'+str(db)+'}\nset block [ord::get_db_block]\nset f [open {'+str(placements)+'} w]\nputs $f [join [list UNITS [$block getDbUnitsPerMicron]] "\\t"]\nforeach inst [$block getInsts] {\n lassign [$inst getOrigin] x y\n set m [$inst getMaster]\n puts $f [join [list INST [$inst getName] [$m getName] [$inst getOrient] $x $y [$m getWidth] [$m getHeight]] "\\t"]\n}\nclose $f\nexit\n')
    pins={str(p):sha(p) for p in (receipt,er,db,gds,source,cell_ext,top_ext,image,script,Path(__file__).resolve())}
    for module in ('join_prototype_physical_instances.py','prototype_spef_v2.py','build_prototype_DCO_rc.py','bind_prototype_spef_pins_v2.py'):
        p=Path(__file__).with_name(module);pins[str(p)]=sha(p)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,OPENROAD,'-exit',script],output/'query.log',deadline,4)
    grid,controls=dimensions(cell_ext.read_text(),source.read_text(),cell)
    mapping,scale=join(placements.read_text(),top_ext.read_text(),grid)
    jf=output/'join.json';save(jf,dict(mapping=mapping,magic_grid_um=str(grid),primitive_controls=controls))
    names={re.sub(r'\\(.)',r'\1',x['routed_instance']):x['extracted_instance'] for x in mapping}
    flow=db.parents[1];results=[];artifacts={str(jf):sha(jf),str(placements):sha(placements)}
    for corner in ('nom','min','max'):
        spef=flow/'spef'/corner/(top+'.'+corner+'.spef');pins[str(spef)]=sha(spef)
        parsed=parse(spef.read_text());pf=output/(corner+'.json');save(pf,parsed)
        netlist,metrics=build(source.read_text(),top,parsed,names)
        target=output/(corner+'.spice');target.write_text(netlist)
        results.append(dict(interconnect_corner=corner,model=str(target),**metrics))
        artifacts.update({str(p):sha(p) for p in (pf,target)})
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
        exact_primitive_dimension_grid_verified=True,all_instance_placements_match=True,matched_instances=len(mapping),
        all_RC_terminals_bound_and_connected=True,cell_internal_and_wire_capacitance_scopes_separated=True,
        mirrored_couplings_counted_once=True,parent_loading_complete=False,device_geometry_review_complete=False,
        validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('candidate','extraction','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();run(a.candidate.resolve(),a.extraction.resolve(),a.output.resolve())
