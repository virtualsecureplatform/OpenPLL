"""Join exact digital database placement to its full-parent extracted terminals."""
import argparse,json,re,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from join_prototype_physical_instances import dimensions,join
from bind_prototype_spef_pins_v2 import bind
from extract_prototype_parent_spef_v2 import OPENROAD
from resources import lease
from compiled_charge_v2 import execute
TOP='IntegerPLL_ProgrammedCore'


def run(extraction,rc,output):
    er=extraction/'assessment.json';rr=rc/'assessment.json';e,r=[json.loads(p.read_text())for p in [er,rr]]
    for a in [e,r]:verify(a['input_sha256']);verify(a['artifacts'])
    layout=[p for p in r['input_sha256']if p.endswith('/assessment.json')and 'checked_filled_parent'in p]
    if len(layout)!=1 or e['input_sha256'].get(layout[0])!=r['input_sha256'][layout[0]]or not r['exact_digital_source_used_in_parent']:raise ValueError('same exact parent macro source required')
    dbs=[Path(p)for p in r['input_sha256']if p.endswith('/route.odb')]
    if len(dbs)!=1:raise ValueError('one checked digital database required')
    raw=next(extraction.glob('*/capacitance.spice'));ext=raw.parent/(TOP+'.ext');cell='sky130_fd_sc_hd__and2_1';cell_ext=raw.parent/(cell+'.ext')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{26});table=output/'placements.tsv';script=output/'query.tcl'
    script.write_text('read_db {'+str(dbs[0])+'}\nset f [open {'+str(table)+'} w]\nset block [ord::get_db_block]\nputs $f [join [list UNITS [$block getDbUnitsPerMicron]] "\\t"]\nforeach inst [$block getInsts] {\n lassign [$inst getOrigin] x y\n set m [$inst getMaster]\n puts $f [join [list INST [$inst getName] [$m getName] [$inst getOrient] $x $y [$m getWidth] [$m getHeight]] "\\t"]\n}\nclose $f\nexit\n')
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600
    with lease(1,8,deadline):execute([OPENROAD,'-no_init','-exit',script],output/'query.log',deadline,8)
    grid,controls=dimensions(cell_ext.read_text(),raw.read_text(),cell);mapping,scale=join(table.read_text(),ext.read_text(),grid);jf=output/'join.json';save(jf,dict(mapping=mapping));names={re.sub(r'\\(.)',r'\1',x['routed_instance']):x['extracted_instance']for x in mapping}
    folder=Path(__file__).resolve().parent;files=[er,rr,dbs[0],raw,ext,cell_ext,script,OPENROAD,Path(__file__).resolve(),folder/'join_prototype_physical_instances.py',folder/'bind_prototype_spef_pins_v2.py'];pins={str(p):sha(p)for p in files};artifacts={str(p):sha(p)for p in [table,jf]};results=[];text=raw.read_text()
    for corner in ['min','nom','max']:
        parsed=rc/(corner+'.json');pins[str(parsed)]=sha(parsed)
        if r['artifacts'].get(str(parsed))!=sha(parsed):raise ValueError('wire view changed')
        result=bind(json.loads(parsed.read_text()),text,TOP,names);target=output/(corner+'.binding.json');save(target,result);artifacts[str(target)]=sha(target);results.append(dict(corner=corner,networks=len(result['networks']),failures=len(result['failures']),all_RC_terminals_bound_and_connected=result['all_RC_terminals_bound_and_connected']))
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,matched_instances=len(mapping),magic_grid_um=str(grid),primitive_dimension_controls=controls,all_digital_wire_terminals_bound_inside_full_parent=all(x['all_RC_terminals_bound_and_connected']for x in results),wire_R_inserted=False,parent_loading_complete=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['extraction','rc','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['extraction','rc','output']))
