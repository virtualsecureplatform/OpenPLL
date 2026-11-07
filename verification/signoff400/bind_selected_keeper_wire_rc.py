"""Join keeper routed/extracted placements and verify every SPEF terminal binding."""
import argparse,json,re,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from compiled_charge import execute
from resources import lease
from join_prototype_physical_instances import dimensions,join
from bind_prototype_spef_pins_v2 import bind


def run(extraction,rc,output):
    er=extraction/'assessment.json';rr=rc/'assessment.json';e,r=[json.loads(p.read_text())for p in [er,rr]]
    for record in [e,r]:verify(record['input_sha256']);verify(record['artifacts'])
    raw=next(extraction.glob('*/capacitance.spice'));top=raw.parent.name
    cell='sky130_fd_sc_hd__einvp_1';cell_ext=raw.parent/(cell+'.ext');top_ext=raw.parent/(top+'.ext')
    dbs=[Path(p)for p in r['input_sha256']if p.endswith('.odb')]
    if len(dbs)!=1:raise ValueError('unique RCX database required')
    output.mkdir(parents=True,exist_ok=False);table=output/'placements.tsv';script=output/'query.tcl'
    script.write_text('read_db {'+str(dbs[0])+'}\nset block [ord::get_db_block]\nset f [open {'+str(table)+'} w]\nputs $f [join [list UNITS [$block getDbUnitsPerMicron]] "\t"]\nforeach inst [$block getInsts] {\n lassign [$inst getOrigin] x y\n set m [$inst getMaster]\n puts $f [join [list INST [$inst getName] [$m getName] [$inst getOrient] $x $y [$m getWidth] [$m getHeight]] "\t"]\n}\nclose $f\n')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';folder=Path(__file__).resolve().parent
    files=[Path(__file__).resolve(),er,rr,raw,cell_ext,top_ext,dbs[0],script,image,*[folder/n for n in ['join_prototype_physical_instances.py','bind_prototype_spef_pins_v2.py']]]
    pins={str(p):sha(p)for p in files}
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600
    with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,
        '/nix/store/qqz49dx8dpx4q9i5wriif091n7iaa0ld-openroad-2026-02-17/bin/openroad','-exit','-no_splash',script],output/'export.log',deadline,4)
    grid,controls=dimensions(cell_ext.read_text(),raw.read_text(),cell)
    mapping,scale=join(table.read_text(),top_ext.read_text(),grid)
    joinfile=output/'join.json';save(joinfile,dict(mapping=mapping))
    instance_map={re.sub(r'\\(.)',r'\1',row['routed_instance']):row['extracted_instance']for row in mapping}
    if len(instance_map)!=len(mapping):raise ValueError('ambiguous escaped instance names')
    artifacts={str(p):sha(p)for p in [table,joinfile]};results=[]
    for corner in ['nom','min','max']:
        parsed=rc/(corner+'.json');pins[str(parsed)]=sha(parsed)
        if r['artifacts'].get(str(parsed))!=pins[str(parsed)]:raise ValueError('RCX parsed view differs')
        result=bind(json.loads(parsed.read_text()),raw.read_text(),top,instance_map)
        target=output/(corner+'.binding.json');save(target,result);artifacts[str(target)]=sha(target)
        results.append(dict(corner=corner,networks=len(result['networks']),terminals=sum(len(n['terminals'])for n in result['networks']),failures=len(result['failures']),all_RC_terminals_bound_and_connected=result['all_RC_terminals_bound_and_connected']))
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
        magic_grid_um=str(grid),database_units_per_magic_unit=str(scale),primitive_controls=controls,
        exact_primitive_length_width_grid_match=True,all_instance_placements_match=True,matched_instances=len(mapping),
        all_RC_terminals_bound_and_connected=all(x['all_RC_terminals_bound_and_connected']for x in results),
        capacitance_scope_combination_validated=False,parent_loading_complete=False,selected=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--extraction',type=Path,required=True);p.add_argument('--rc',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.extraction.resolve(),a.rc.resolve(),a.output.resolve())
