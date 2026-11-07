"""Stream a freshly rerouted keeper parent and verify every macro's source geometry."""
import argparse,json,time,sys
from pathlib import Path
from itertools import combinations
import klayout.db as k
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge import execute
sys.path.insert(0,str(ROOT/'verification/timing400'))
from stream_candidate_assembly_v9 import same_cell,STREAM
from check_compact_mapping import TECH,LEF


def run(frame,power,route,output):
    output.mkdir(parents=True,exist_ok=False)
    receipts=[p/'assessment.json'for p in [frame,power,route]];f,p,r=[json.loads(x.read_text())for x in receipts]
    for x in [f,p,r]:verify(x['input_sha256']);verify(x['artifacts'])
    if not r['buffered_control_macro_bindings_verified']or r['router_drc_violations']!=0:raise ValueError('passing fresh parent route required')
    for name in ['assessment.json','power.odb','composition.json']:
        if r['input_sha256'].get(str(power/name))!=sha(power/name):raise ValueError('route does not bind keeper power preparation')
    if not p['keeper_routing_geometry_covered']or not p['main_rail_database_connectivity_pass']:raise ValueError('keeper physical geometry not covered')
    if f['candidate_source_sha256']!=p['candidate_source_sha256']or p['candidate_source_sha256']!=r['candidate_source_sha256']:raise ValueError('logical candidate changed')
    order=['digital','oscillator','detector'];views=f['macro_sources'];names=[views[n]['master']for n in order]
    sources=[Path(views[n]['gds'])if n!='oscillator'else Path(p['candidate_keeper_GDS'])for n in order]
    if sha(sources[1])!=p['candidate_keeper_GDS_sha256']:raise ValueError('keeper macro changed')
    lefs=[Path(views[n]['lef'])for n in order];private=ROOT/'build/timing450/pdk/sky130A'
    maps=[private/'libs.tech/klayout/tech'/('sky130A.'+e)for e in ['lyt','lyp','map']]
    files=[Path(__file__).resolve(),Path(STREAM),Path(sys.executable),TECH,LEF,*receipts,*sources,*lefs,*maps,route/'route.def',route/'powered.v']
    pins={str(x):sha(x)for x in files};save(output/'inputs.json',dict(input_sha256=pins))
    layouts=[]
    for source,name in zip(sources,names):
        l=k.Layout();l.read(str(source))
        if l.cell(name)is None or any(c.is_ghost_cell()for c in l.each_cell()):raise ValueError('missing source macro geometry')
        layouts.append(l)
    duplicates=[]
    for i,j in combinations(range(3),2):
        for name in {c.name for c in layouts[i].each_cell()}&{c.name for c in layouts[j].each_cell()}:
            same_cell(layouts[i],layouts[i].cell(name),layouts[j],layouts[j].cell(name));duplicates.append(name)
    target=output/'assembly.gds';top='IntegerPLL_400MHz_PrototypeTop'
    command=[sys.executable,str(STREAM),'-o',str(target),'-t',top,'-T',str(maps[0]),'-P',str(maps[1]),'-M',str(maps[2]),'--conflict-resolution','OverwriteCell','-l',str(TECH),'-l',str(LEF)]
    for lef in lefs:command+=['-l',str(lef)]
    for gds in sources:command+=['-w',str(gds)]
    command.append(str(route/'route.def'))
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+600):execute(command,output/'stream.log',time.clock_gettime(time.CLOCK_BOOTTIME)+600,8)
    result=k.Layout();result.read(str(target));parent=result.cell(top)
    if parent is None or [c.name for c in result.top_cells()]!=[top]or any(c.is_ghost_cell()for c in result.each_cell()):raise ValueError('incomplete assembled GDS')
    actual={i.cell.name:(i.cplx_trans.mag,i.cplx_trans.angle,i.cplx_trans.is_mirror(),i.cplx_trans.disp.x,i.cplx_trans.disp.y)for i in parent.each_inst()if i.cell.name in names}
    wanted={views[n]['master']:(1,0,False,*f['macro_bboxes_dbu'][n][:2])for n in order}
    if actual!=wanted:raise ValueError('macro position changed')
    for source,name in zip(layouts,names):same_cell(source,source.cell(name),result,result.cell(name))
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(target):sha(target),str(output/'stream.log'):sha(output/'stream.log')},
        isolated_keeper_parent=True,fresh_parent_route_streamed=True,all_source_macro_geometry_and_labels_preserved=True,
        identical_duplicate_definitions_checked=len(duplicates),private_cell_renames=p['keeper_private_cell_renames'],
        route_powered_netlist=str(route/'powered.v'),macro_positions_unchanged=True,
        parent_DRC_LVS_antenna_density_power_and_model_qualified=False,selected=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['frame','power','route','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['frame','power','route','output']))
