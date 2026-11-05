"""Bind every parent SPEF terminal to exact placement and alias-proved LVS geometry."""
import argparse
from fractions import Fraction
import json
import os
from pathlib import Path
import re
import time
from common_v3 import ROOT,save,sha,verify
from join_prototype_physical_instances import dimensions,join,ORIENTATIONS
from bind_prototype_spef_pins_v2 import bind
from resources import lease
from compiled_charge import execute

OPENROAD=Path('/nix/store/qqz49dx8dpx4q9i5wriif091n7iaa0ld-openroad-2026-02-17/bin/openroad')
TOP='IntegerPLL_400MHz_PrototypeTop'

def join_parent(placements,extracted,grid):
    lines=placements.splitlines();standard=[lines[0]];macros=[]
    for line in lines[1:]:
        fields=line.split('\t')
        if len(fields)!=8:raise ValueError('exact database placement record required')
        (standard if fields[2].startswith('sky130_fd_sc_') else macros).append(line)
    mapping,scale=join('\n'.join(standard)+'\n',extracted,grid)
    if len(macros)!=3:raise ValueError('three explicit placed macros required')
    uses={}
    for line in extracted.splitlines():
        fields=line.split()
        if fields[:1]!=['use']:continue
        a,b,x,c,d,y=map(int,fields[3:9]);key=(fields[1],(a,b,c,d),Fraction(x)*scale,Fraction(y)*scale)
        uses.setdefault(key,[]).append(fields[2])
    for line in macros:
        _,name,master,orientation,x,y,_,_=line.split('\t')
        if orientation not in ORIENTATIONS:raise ValueError('unreviewed macro transform')
        found=uses.get((master,ORIENTATIONS[orientation],Fraction(x),Fraction(y)),[])
        if len(found)!=1:raise ValueError('macro does not have a unique exact extracted placement')
        mapping.append(dict(routed_instance=name,extracted_instance=found[0],master=master,x_dbu=int(x),y_dbu=int(y),orientation=orientation))
    if len({r['extracted_instance'] for r in mapping})!=len(mapping):raise ValueError('extracted instance join is not bijective')
    return mapping,scale

def run(spef,layout,lvs,output):
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    sr,lr,vr=[p/'assessment.json' for p in (spef,layout,lvs)]
    s,l,v=[json.loads(p.read_text()) for p in (sr,lr,vr)]
    for record in (s,l,v):verify(record['input_sha256']);verify(record['artifacts'])
    if not l['assembled_drc_pass'] or not v['assembled_lvs_pass'] or v['input_sha256'].get(str(lr))!=sha(lr) or s['input_sha256'].get(str(lr))!=sha(lr) or s['input_sha256'].get(str(vr))!=sha(vr):
        raise ValueError('one matching physical route and alias-proved LVS authority required')
    databases=[Path(p) for p in s['input_sha256'] if p.endswith('/route.odb')]
    models=[Path(p) for p in v['artifacts'] if p.endswith('/assembly_alias_normalized.spice')]
    if len(databases)!=1 or len(models)!=1:raise ValueError('one exact database and alias-normalized native hierarchy required')
    db,source=databases[0],models[0];text=source.read_text();cell='sky130_fd_sc_hd__nand2_8'
    cell_ext=layout/'extraction'/(cell+'.ext');top_ext=layout/'extraction'/(TOP+'.ext')
    grid,controls=dimensions(cell_ext.read_text(),text,cell)
    output.mkdir(parents=True,exist_ok=False);placements=output/'placements.tsv';script=output/'query.tcl'
    script.write_text('read_db {'+str(db)+'}\nset block [ord::get_db_block]\nset f [open {'+str(placements)+'} w]\nputs $f [join [list UNITS [$block getDbUnitsPerMicron]] "\\t"]\nforeach inst [$block getInsts] {\n lassign [$inst getOrigin] x y\n set m [$inst getMaster]\n puts $f [join [list INST [$inst getName] [$m getName] [$inst getOrient] $x $y [$m getWidth] [$m getHeight]] "\\t"]\n}\nclose $f\nexit\n')
    pins={str(p):sha(p) for p in (sr,lr,vr,db,source,cell_ext,top_ext,OPENROAD,script,Path(__file__).resolve(),Path(__file__).with_name('join_prototype_physical_instances.py'),Path(__file__).with_name('bind_prototype_spef_pins_v2.py'))}
    os.environ.update(OMP_NUM_THREADS='1',GOMAXPROCS='1',OPENBLAS_NUM_THREADS='1')
    with lease(1,4,deadline):execute([OPENROAD,'-no_init','-exit',script],output/'query.log',deadline,4)
    mapping,scale=join_parent(placements.read_text(),top_ext.read_text(),grid)
    jf=output/'join.json';save(jf,dict(mapping=mapping,magic_grid_um=str(grid),database_units_per_magic_unit=str(scale),primitive_dimension_controls=controls))
    names={re.sub(r'\\(.)',r'\1',r['routed_instance']):r['extracted_instance'] for r in mapping}
    results=[];artifacts={str(jf):sha(jf),str(placements):sha(placements)}
    for corner in ('min','nom','max'):
        path=spef/(corner+'.json')
        if s['artifacts'].get(str(path))!=sha(path):raise ValueError('parsed SPEF changed')
        pins[str(path)]=sha(path);result=bind(json.loads(path.read_text()),text,TOP,names)
        detail=output/(corner+'.binding.json');save(detail,result);artifacts[str(detail)]=sha(detail)
        results.append(dict(corner=corner,networks=len(result['networks']),failures=len(result['failures']),all_RC_terminals_bound_and_connected=result['all_RC_terminals_bound_and_connected']))
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,matched_placed_instances=len(mapping),
         exact_primitive_dimension_grid_verified=True,all_placed_instances_matched=True,
         all_RC_terminals_bound_and_connected=all(r['all_RC_terminals_bound_and_connected'] for r in results),
         logical_hierarchy_uses_proved_zero_R_child_port_alias=True,
         cell_internal_capacitance_not_included=True,parent_loading_complete=False,release_ready=False))
    if not all(r['all_RC_terminals_bound_and_connected'] for r in results):raise ValueError('parent SPEF binding nonpass; evidence preserved')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('spef','layout','lvs','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(*(getattr(args,n).resolve() for n in ('spef','layout','lvs','output')))
